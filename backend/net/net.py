import statistics
import asyncio
import aiohttp
import random
from asyncache import cached as async_cached
from cachetools import TTLCache
from web3 import Web3
from web3.middleware import async_geth_poa_middleware, geth_poa_middleware
from web3.exceptions import ExtraDataLengthError
from web3.eth import AsyncEth
from web3.net import AsyncNet
from web3.geth import Geth, AsyncGethTxPool
from eth_account.account import Account
from flashbots.flashbots import flashbot

import backend.settings as settings
from backend.utils import format_address, fee_history_formatter, handle_errors
from backend.tx.tx import GAS_SLOW, GAS_AVERAGE, GAS_FAST
import backend.tx.pool
import backend.net.sessions


async def create_net(net_info):
    net = Net(net_info)
    await net.async_init()
    return net


# NOTE: use await create_net() to create accounts, has to use some async methods and __init__ doesn't allow this
class Net:
    def __init__(self, net_info):
        self.name = net_info["name"]
        self.url = net_info["url"]
        self.chain_id = net_info["chain_id"]
        self.scan_url = net_info["scan_url"]
        self.session = None  # Gets added during async_init
        self.provider = None  # Gets added during async_init

        # To use for methods not provided by the async version:
        # Use websocket version if available:
        if net_info["ws"]:
            self.sync_url = net_info["ws"]
        else:
            self.sync_url = self.url
        self.sync_provider = Web3(Web3.HTTPProvider(self.sync_url))

        # Add in the flashbots middleware needed if available for the net:
        self.flashbots_enabled = False
        if net_info["flashbots_url"]:
            self.flashbots_enabled = True
            flashbot(
                self.sync_provider,
                Account.from_key(settings.FLASHBOTS_SIGNATURE_PRIVATE_KEY),
                net_info["flashbots_url"],
            )

    async def async_init(self):
        # Configuring the aiohttp session:
        connector = aiohttp.TCPConnector(
            limit=settings.MAX_ASYNC_REQUESTS
        )  # Maxiumum 100 connections/simultaneous requests
        timeout = aiohttp.ClientTimeout(
            total=None,  # Unlimited for the whole request
            connect=settings.REQUEST_TIMEOUT_SECS,  # Max secs to get connection from pool.
            sock_connect=settings.REQUEST_TIMEOUT_SECS,  # Max secs to connect to peer for new connection.
            sock_read=settings.REQUEST_TIMEOUT_SECS,  # Max secs to read data from peer
        )
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        backend.net.sessions.SESSIONS.append(self.session)

        underlying_async_provider = Web3.AsyncHTTPProvider(
            self.url, request_kwargs={"timeout": settings.REQUEST_TIMEOUT_SECS}
        )
        # Injecting our custom session into the async provider:
        await underlying_async_provider.cache_async_session(self.session)
        self.provider = Web3(
            underlying_async_provider,
            # TODO at some point these should be automatically added for async:
            modules={
                "eth": (AsyncEth,),
                "net": (AsyncNet,),
                "geth": (Geth, {"txpool": (AsyncGethTxPool,)}),
            },
            middlewares=[],
        )

        # Check to see if base fee can be calculated:
        try:
            await self.base_fee()
        except (ExtraDataLengthError, ValueError):
            # Some chains require the following middleware:
            self.provider.middleware_onion.inject(async_geth_poa_middleware, layer=0)
            # self.sync_provider.middleware_onion.inject(geth_poa_middleware, layer=0)
            # Should now not error:
            await self.base_fee()

    @property
    async def pending_block(self):
        return await self.provider.eth.get_block("pending")

    @property
    async def latest_block(self):
        return await self.provider.eth.get_block("latest")

    async def wait_for_next_block(self):
        current_block_num = (await self.latest_block)["number"]

        while current_block_num == (await self.latest_block)["number"]:
            print("Waiting for next block...")
            await asyncio.sleep(0.5)

    async def get_block_num_at_time(self, dt):
        req = await self.session.get(
            self.scan_url,
            params={
                "module": "block",
                "action": "getblocknobytime",
                "timestamp": str(int(dt.timestamp())),  # Needs without the decimal
                "closest": "after",
                "apikey": settings.ETHERSCAN_API_KEY,
            },
            headers=settings.ETHERSCAN_HEADERS,
        )

        out = await req.json()
        return out["result"]

    @property
    async def mempool(self):
        pool = backend.tx.pool.TX_POOL
        txs_info = []
        for tx_info in pool:
            txs_info.append(tx_info.data)

        # Ideal method but not supported by infura, only works with ganache or own node:
        # info = (await self.provider.geth.txpool.content())["pending"]
        # txs_info = []
        # for id1 in info:
        #     for id2 in info[id1]:
        #         tx_info = dict(info[id1][id2])  # Converting from attrdict
        #         # To work with the hacky version
        #         tx_info["data"] = tx_info["input"]
        #         txs_info.append(tx_info)

        return txs_info

    def create_new_wallet(self):
        wallet = self.sync_provider.eth.account.create(str(random.random()))
        return {"address": wallet.address, "private_key": wallet.key}

    @handle_errors
    def estimate_gas(self, data):
        return self.sync_provider.eth.estimate_gas(data)

    @async_cached(TTLCache(1024, 1))  # Cache for 1 second (maxSize, ttl)
    async def base_fee(self):
        # Returns the base fee for current pending block:
        res = await self.pending_block
        return res.baseFeePerGas

    # TODO: block scanning logic should probably happen in a different thread if lots of txs, not worried enough about speed yet enough to do so.
    @async_cached(TTLCache(1024, 1))  # Cache for 1 second (maxSize, ttl)
    async def max_priority_fees(self):
        num_historical_blocks = 20
        slow_percentile = 1
        average_percentile = 50
        fast_percentile = 90
        info = fee_history_formatter(
            await self.provider.eth.fee_history(
                num_historical_blocks,
                "pending",
                [slow_percentile, average_percentile, fast_percentile],
            )
        )

        slow = map(lambda block: block["priorityFeePerGas"][0], info)
        average = map(lambda block: block["priorityFeePerGas"][1], info)
        fast = map(lambda block: block["priorityFeePerGas"][2], info)

        return {
            GAS_SLOW: int(statistics.mean(slow)),
            GAS_AVERAGE: int(statistics.mean(average)),
            GAS_FAST: int(statistics.mean(fast)),
        }

    async def balance(self, address, block="latest"):
        format_address(address)

        if block == "latest":
            block = self.sync_provider.eth.default_block
        else:
            # Confirm int block:
            block = int(block)

        balance = await self.provider.eth.get_balance(address, block_identifier=block)

        return balance
