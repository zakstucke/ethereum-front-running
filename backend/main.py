from backend.asyncio_utils import async_runner, thread_wrapper


@thread_wrapper
async def main():
    pass


async_runner(main())
