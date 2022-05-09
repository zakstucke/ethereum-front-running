import asyncio
from functools import wraps
from asgiref.sync import async_to_sync, SyncToAsync

from django.db import close_old_connections
import backend.net.sessions

# instanstiated in async_runner_internals()
PROGRAM_ACTIVE = None


# FROM DJANGO-CHANNELS, don't need anything else from the package so copying here
class ModifiedSyncToAsync(SyncToAsync):
    """
    SyncToAsync version that cleans up old database connections when it exits.
    """

    def thread_handler(self, loop, *args, **kwargs):
        close_old_connections()
        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            close_old_connections()


sync_to_async = ModifiedSyncToAsync


# Runs a task or list of tasks, along with other task injections, returns the result or a list of results
def async_runner(task_or_tasks):
    from backend.tx.tx_monitor import transaction_monitor

    if type(task_or_tasks) == list:
        tasks = task_or_tasks
    else:
        tasks = [task_or_tasks]

    num_requested_tasks = len(tasks)

    tasks.append(transaction_monitor())

    results = async_runner_internals(tasks)

    # Return the value of the requested tasks if they exist:
    if results and len(results) >= num_requested_tasks:
        task_results = results[:num_requested_tasks]
    else:
        task_results = [None for x in range(num_requested_tasks)]

    if len(task_results) == 1:
        return task_results[0]
    return task_results


# Sets up the event loop and runs whatever tasks supplied concurrently:
def async_runner_internals(tasks):
    global PROGRAM_ACTIVE

    @async_to_sync
    async def handler():
        try:
            results = await asyncio.gather(*tasks)
        finally:
            # Make sure no sessions left open:
            for session in backend.net.sessions.SESSIONS:
                await session.close()
            backend.net.sessions.SESSIONS = []
        return results

    try:
        PROGRAM_ACTIVE = True
        results = handler()
    except asyncio.exceptions.CancelledError:
        results = None

    return results


# Handles errors to cancel all running threads and show the error:
def thread_wrapper(func):
    @wraps(func)
    async def wrapped(*args, **kwargs):
        global PROGRAM_ACTIVE

        try:
            result = await func(*args, **kwargs)
        except Exception as e:
            for task in asyncio.all_tasks():
                task.cancel()
            raise e
        finally:
            PROGRAM_ACTIVE = False

        return result

    return wrapped


# Loops the function indefinitely, until the main thread finishes or a thread errors
def indefinite_worker_wrapper(func):
    @wraps(func)
    @thread_wrapper
    async def wrapped(*args, **kwargs):
        global PROGRAM_ACTIVE

        while PROGRAM_ACTIVE:
            await func(*args, **kwargs)

    return wrapped
