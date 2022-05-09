import json
import uuid
import requests

from django.utils import timezone

import backend.settings as settings
from backend.utils import format_address, handle_errors


async def create_account(*args, **kwargs):
    account = Account(*args, **kwargs)
    await account.async_init()
    return account


# NOTE: use await create_account() to create accounts, has to use some async methods and __init__ doesn't allow this
class Account:
    def __init__(self, net, address=None, store=None, private_key=None, passphrase=None):
        # DO NOT USE PRIVATE KEY METHOD! Just allowing for testing with test nets where there are no security risks!

        self.pk = uuid.uuid4().hex
        self.net = net

        # Either use a store to include private key, or just pass the address:
        if store:
            self.address = json.loads(store)["address"]

            # Get the passphrase from the commandline if not already entered:
            if not passphrase:
                passphrase = settings.get_store_pass()

            self.private_key = self.net.sync_provider.eth.account.decrypt(store, passphrase).hex()
        else:
            assert address, "Must specify address if not using store!"
            self.address = address

            if private_key:
                self.private_key = private_key
            else:
                self.private_key = None

        self.address = format_address(self.address)

        # Where pending tx's are recorded, allows resending failed txs and resetting self.nonce accordingly.
        self.tx_pool = []

    async def async_init(self):
        # Will need to update this every time we try to send a tx:
        self.nonce = await self.get_tx_count()

    @handle_errors
    async def get_tx_count(self):
        return await self.net.provider.eth.get_transaction_count(self.address)

    async def transaction_history(self, start_block_num, end_block_num):
        assert (
            self.net.scan_url
        ), "{} does not currently have a scan_url attribute (connection to etherscan)."

        # TODO, if more than 10000 then will need to paginate
        req = await self.net.session.get(
            self.net.scan_url,
            params={
                "module": "account",
                "action": "txlist",
                "address": self.address,
                "startblock": int(start_block_num),
                "endblock": int(end_block_num),
                "page": "1",
                "offset": "10000",  # The max allowed
                "sort": "asc",
                "apikey": settings.ETHERSCAN_API_KEY,
            },
            headers=settings.ETHERSCAN_HEADERS,
        )

        out = await req.json()

        txs = out["result"]

        return txs

    async def balance(self, block="latest"):
        return await self.net.balance(self.address, block=block)
