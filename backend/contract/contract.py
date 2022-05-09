import json
import random
import time
from web3 import Web3

from backend.utils import format_address, prettify
from backend.tx.tx import create_tx, TX_SUCCESS, GAS_AVERAGE


async def create_contract(net, address=None, abi=None, abi_path=None, bytecode=None):
    contract = Contract(net, address=address, abi=abi, abi_path=abi_path, bytecode=bytecode)
    await contract.async_init()
    return contract


# NOTE: use await create_contract() to create accounts, has to use some async methods and __init__ doesn't allow this
class Contract:
    def __init__(self, net, address=None, abi=None, abi_path=None, bytecode=None):
        self.net = net

        # Parse the abi:
        assert abi or abi_path, "Must specify either an abi, or a file path to one with abi_path!"
        if abi:
            if type(abi) == str:
                self.abi = json.loads(abi)
            else:
                self.abi = abi
        else:
            with open(abi_path, "r") as file:
                self.abi = json.load(file)

        self.bytecode = bytecode

        if address:
            self.address = format_address(address)
            self.contract = self.net.sync_provider.eth.contract(address=self.address, abi=self.abi)
        else:
            assert (
                self.bytecode
            ), "Must include bytecode if the contract is undeployed (i.e. you didn't enter an address for the contract)"

            # Both of these will be setup like above after deployment
            self.address = None
            self.contract = self.net.sync_provider.eth.contract(
                abi=self.abi, bytecode=self.bytecode
            )

    async def async_init(self):
        pass

    def functions(self):
        function_info = {}
        for sec in self.abi:
            if sec["type"] == "function" and "anonymous" not in sec:
                function_info[sec["name"]] = {}

                def format_in_out(in_out):
                    if in_out["name"]:
                        formatted = "{}:{}".format(in_out["name"], in_out["type"])
                    else:
                        formatted = in_out["type"]

                    return formatted

                function_info[sec["name"]]["inputs"] = list(map(format_in_out, sec["inputs"]))
                function_info[sec["name"]]["outputs"] = list(map(format_in_out, sec["outputs"]))

        return prettify(function_info)

    def call_function(self, func_name, *args, **kwargs):
        func = getattr(self.contract.functions, func_name)
        res = func(*args, **kwargs).call({}, block_identifier="latest")
        return res

    def build_transacton_data(self, func_name, *args, extra_tx_data={}, **kwargs):
        func = getattr(self.contract.functions, func_name)

        initial_data = {
            # Will be calculated by us internally, but want web3 to think they're already there
            "gas": None,
            "maxFeePerGas": None,
            "maxPriorityFeePerGas": None,
        }

        data = func(*args, **kwargs).buildTransaction({**initial_data, **extra_tx_data})

        return data

    async def deploy_contract(self, account, *args, **kwargs):
        assert (
            self.bytecode and not self.address
        ), "Must include bytecode to deploy and not have already deployed! (i.e. no address)"

        data = self.contract.constructor(*args, **kwargs).buildTransaction(
            {
                # Will be calculated by us internally, but want web3 to think they're already there
                "gas": None,
                "maxFeePerGas": None,
                "maxPriorityFeePerGas": None,
            }
        )
        tx = await create_tx(account, data=data)

        await tx.send()
        await tx.wait()

        # Add the address of the newly deployed contract to the obj:
        self.address = tx.receipt.contractAddress
        self.contract = self.net.sync_provider.eth.contract(address=self.address, abi=self.abi)

        return tx
