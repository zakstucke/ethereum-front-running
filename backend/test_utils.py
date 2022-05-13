from django.conf import settings as base_settings
from django.core.management import call_command

# from unavailable.test_utils import TransactionTestCase
from rest_framework.test import APITransactionTestCase as TransactionTestCase

from backend import tx
import backend.settings as settings
from backend.utils import get_ganache_accounts, run_ganache
from backend.net.net import create_net
from backend.account.account import create_account
from backend.asyncio_utils import async_runner, thread_wrapper


def async_test(*ganache_args, non_ganache_endpoint=False, **ganache_kwargs):
    def decorator(coro):
        def wrapper(self):
            async def main():
                await self.asyncSetUp(
                    *ganache_args, non_ganache_endpoint=non_ganache_endpoint, **ganache_kwargs
                )
                await thread_wrapper(coro)(self)
                await self.asyncTearDown()

            return async_runner(main())

        return wrapper

    return decorator


class TestCase(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        # Setting connections to force close and using the modified sync_to_async function in asyncio_utils prevents hanging connections that stop the test db from deleting
        base_settings.DATABASES["default"]["CONN_MAX_AGE"] = 0
        super().setUpClass()

    @classmethod
    def setUpTestData(cls):
        print("Flushing db from any other test suites...")
        call_command("flush", interactive=False)

        # Custom command to setup tests:
        call_command("populate_test_db")        

    async def asyncSetUp(self, *ganache_args, non_ganache_endpoint=False, **ganache_kwargs):

        self.kill_ganache_func = None

        if not non_ganache_endpoint:
            # Launch ganache for the test with specified parameters:
            self.kill_ganache_func = run_ganache(*ganache_args, **ganache_kwargs)

            # Setup the net and accounts that are available for use:
            self.net = await create_net(settings.NETS["GANACHE"])

            account_info = get_ganache_accounts()
            self.accounts = [
                await create_account(self.net, address=address, private_key=account_info[address])
                for address in account_info
            ]
        else:
            self.net = await create_net(non_ganache_endpoint)

        # Aesthetics
        print("\n")

    async def asyncTearDown(self):
        # Empty the tx pool:
        tx.TX_POOL = []

        # Kill the ganache instance if it was running:
        if self.kill_ganache_func:
            self.kill_ganache_func()

        # Aesthetics
        print("")
