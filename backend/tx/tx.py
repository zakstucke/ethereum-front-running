import asyncio
import copy
import time
import random
from web3 import Web3
from web3.exceptions import TransactionNotFound, ContractLogicError
from hexbytes import HexBytes

from django.utils import timezone

import backend.settings as settings
from backend.asyncio_utils import sync_to_async
import backend.tx.pool as tx_pool_holder


GAS_SLOW = "slow"
GAS_AVERAGE = "average"
GAS_FAST = "fast"

TX_UNSENT = "unsent"
TX_SUCCESS = "success"
TX_REVERTED = "reverted"
TX_PENDING = "pending"
TX_CANCELLED = "cancelled"
TX_DROPPED = "dropped"


# Seems to be 10% online but set to 30% to be safe for now.
REBROADCAST_GAS_MIN_PERC_INCREASE = 30

# 21000 gas needed to send a normal send base currency tx
GAS_BASIC_TX = 21000
GAS_COMPLEX_FUNCTION_TX = 600000  # 600k should cover most function types
TX_MAX_GAS_LIMIT = (
    10000000  # From tests doesn't look like we use more than 3.5 mil, so do 10 to be safe
)


async def create_tx(
    account,
    data={},
    gas_speed=GAS_AVERAGE,
    simulate_low_gas=False,  # If set to true must be manually switched off when desired!
    ignore_reversion=False,
    assume_always_rebroadcastable=False,
    dont_rebroadcast=False,
    specific_gas=None,
):
    tx = Tx(
        account,
        data=data,
        gas_speed=gas_speed,
        simulate_low_gas=simulate_low_gas,
        ignore_reversion=ignore_reversion,
        assume_always_rebroadcastable=assume_always_rebroadcastable,
        dont_rebroadcast=dont_rebroadcast,
        specific_gas=specific_gas,
    )
    await tx.async_init()
    return tx


class Tx:
    def __init__(
        self,
        account,
        data={},
        gas_speed=GAS_AVERAGE,
        simulate_low_gas=False,  # If set to true must be manually switched off when desired!
        ignore_reversion=False,
        assume_always_rebroadcastable=False,
        dont_rebroadcast=False,
        specific_gas=None,
    ):
        self.account = account
        self.net = account.net
        self.data = copy.deepcopy(data)  # Make a copy in case reusing data obj
        self.gas_speed = gas_speed

        # If set to True purposely will set too low tx fees for the transaction
        # Used during testing to force a rebroadcast:
        self.simulate_low_gas = simulate_low_gas

        # Used when testing a reversion of a contract (would normally likely error before)
        self.ignore_reversion = ignore_reversion
        # Used when testing to test edge cases of rebroadcast
        self.assume_always_rebroadcastable = assume_always_rebroadcastable
        self.dont_rebroadcast = dont_rebroadcast
        self.specific_gas = specific_gas

        # Will all start being populated after send()
        self.status = TX_UNSENT
        self.signed_data = None
        self.hash = None
        self.receipt = None
        self.last_sent = None

        # Record all tx attempts so the transaction monitor can see if any of them have been successful
        self.tx_attempts = []
        self.tx_flash_attempts = []
        self.flash_last_block_number = None  # Used to know when there is no longer a chance of the flashbots attempts suceeding

        self.db_tx = None  # Will be populated by log_tx

    async def async_init(self):
        # Add in preset values for things we can work out if not manually entered:
        if "chainId" not in self.data:
            self.data["chainId"] = self.net.chain_id

        # Specify gas values for the tx:
        gas_info = await self.calc_gas_info(is_init=True, specific_gas=self.specific_gas)

        # Add the gas info to the data:
        self.data = {**self.data, **gas_info}

    @property
    def pool(self):
        return tx_pool_holder.TX_POOL

    async def log_tx(self, as_new=False, description="", experiment=None):
        assert self.status != TX_UNSENT, "Tx must have been sent to log"
        from backend.tx.models import DbTx

        # Convert any hexbyte objects to hex in the receipt:
        receipt = None
        if self.receipt:
            receipt = {}
            for key in self.receipt:
                val = self.receipt[key]
                if type(val) == HexBytes:
                    receipt[key] = val.hex()
                else:
                    receipt[key] = val

        # Cannot save bytes to db:
        data = copy.deepcopy(self.data)
        for key in data:
            if type(data[key]) == bytes:
                data[key] = data[key].decode("utf8")

        new_data = {
            "description": description,
            "experiment": experiment,
            "node_url": self.net.url,
            "chain_id": self.net.chain_id,
            "account_address": self.account.address,
            "status": self.status,
            "gas_speed": self.gas_speed,
            "nonce": self.account.nonce,
            "data": data,
            "hash": self.hash.hex() if self.hash else "",
            "receipt": receipt,
            "last_sent": self.last_sent,
        }

        @sync_to_async
        def interact_with_orm():
            # Create or update:
            if not self.db_tx:
                self.db_tx = DbTx.objects.create(**new_data)
            elif as_new:
                # Mark old as dropped and save new:
                self.db_tx.status = TX_DROPPED
                self.db_tx.save()
                self.db_tx = DbTx.objects.create(**new_data)
            else:
                for key in new_data:
                    setattr(self.db_tx, key, new_data[key])
                self.db_tx.save()

        await interact_with_orm()

    async def calc_gas_info(self, is_init=False, is_cancel=False, specific_gas=None):
        assert not (is_init and is_cancel), "Cannot be inital tx and cancel together!"

        # Only want to check the initial data, if calling for a rebroadcast then some gas values will already be in self.data:
        if is_init:
            for key in [
                "gasPrice",
                "gas",
                "maxFeePerGas",
                "maxPriorityFeePerGas",
                "baseFeePerGas",
            ]:
                assert (
                    key not in self.data or not self.data[key]
                ), "'{}' already in tx data! These values should be calculated automatically here.".format(
                    key
                )

                # Could be parsed in with None value, remove entirely so doesn't impact calcs
                if key in self.data:
                    del self.data[key]

        gas_info = {}

        if specific_gas:
            gas_info["gas"] = specific_gas
        elif is_init:
            gas_info["gas"] = GAS_BASIC_TX

            # Use 5 times the estimated gas to be safe, up to a hard limit of 300,000 to prevent something crazy
            # E.g. simple tx 21,000, simple deploy, 53,000.
            try:
                estimated_gas = self.net.estimate_gas(self.data)
            except ContractLogicError as e:
                # This runs function locally, so will error if reverts, but may want reversion to go through (e.g. tests)
                if self.ignore_reversion:
                    estimated_gas = TX_MAX_GAS_LIMIT
                else:
                    raise e

            # Capping gas at 300,000 otherwise doing 150% of the gas estimate:
            gas_info["gas"] = min(int(estimated_gas * 1.5), TX_MAX_GAS_LIMIT)
        elif is_cancel:
            # Is a simple send tx so just use the base gas required
            gas_info["gas"] = GAS_BASIC_TX
        else:
            # If a rebroadcast, use the current gas as shouldn't have changed:
            assert "gas" in self.data
            gas_info["gas"] = self.data["gas"]

        # TODO ganache doesn't currently support feeHistory, is priority 2 on github and looks like will be sorted soon.
        if self.net.name == settings.NETS["GANACHE"]["name"]:
            max_priority_fee = await self.net.provider.eth.max_priority_fee
            if self.gas_speed == GAS_SLOW:
                max_priority_fee = int(max_priority_fee * 0.8)
            elif self.gas_speed == GAS_FAST:
                max_priority_fee = int(max_priority_fee * 1.3)
        else:
            max_priority_fee_options = await self.net.max_priority_fees()
            max_priority_fee = max_priority_fee_options[self.gas_speed]

        base_fee = await self.net.base_fee()

        # 2* means tx will be marketable for at least 6 consecutive 100% blocks from the current base fee calc:
        # https://www.blocknative.com/blog/eip-1559-fees

        # Used during testing to force a rebroadcast:
        if self.simulate_low_gas:
            gas_info["maxFeePerGas"] = 0
            gas_info["maxPriorityFeePerGas"] = 0
        else:
            gas_info["maxFeePerGas"] = (2 * base_fee) + max_priority_fee
            gas_info["maxPriorityFeePerGas"] = max_priority_fee

        return gas_info

    def create_flash_bundle(self):
        tx_data = [self.data]

        self.account.nonce += 1  # Update the nonce as tx should be sent

        if self.data["gas"] < 42000:
            tx_data.append(
                {
                    # Add the extra miner value, or the new calculations if higher:
                    "maxFeePerGas": Web3.toWei(100, "gwei"),
                    "maxPriorityFeePerGas": Web3.toWei(100, "gwei"),
                    "gas": GAS_BASIC_TX,
                    "nonce": self.account.nonce,
                    "chainId": self.net.chain_id,
                    "to": self.account.address,
                    "value": 0,
                }
            )
            # Update again as adding another transaction:
            self.account.nonce += 1

        bundle = [
            {
                "signed_transaction": self.net.sync_provider.eth.account.sign_transaction(
                    data, self.account.private_key
                ).rawTransaction
            }
            for data in tx_data
        ]

        # Confirm all the tx_data should succeed by running a simulation:
        # sim = self.net.sync_provider.flashbots.simulate(
        #     bundle, block_tag=self.net.sync_provider.eth.block_number
        # )
        # assert (
        #     "bundleHash" in sim and sim["bundleHash"]
        # ), "Something wrong with the bundle, simulation: {}".format(sim)

        return bundle, tx_data

    async def send_flash(self, description=None, experiment=None):
        assert self.net.flashbots_enabled

        bundle, tx_data = self.create_flash_bundle()

        # send bundle to be executed in the next 5 blocks
        block = self.net.sync_provider.eth.block_number

        self.last_sent = timezone.now()
        self.status = TX_PENDING
        await self.log_tx(description=description, experiment=experiment)

        one_accepted = False
        no_of_block_attempts = 10
        print("Sending flash...")
        for x in range(no_of_block_attempts):
            try:
                block_num = block + x
                attempt = self.net.sync_provider.flashbots.send_bundle(
                    bundle, target_block_number=block_num
                )
                self.tx_flash_attempts.append(attempt.bundle)
                self.flash_last_block_number = block_num
                one_accepted = True
            except ValueError as e:
                print(e)

        assert one_accepted, "Flashbots rejected all {} block requests.".format(
            no_of_block_attempts
        )

    async def send(
        self,
        is_cancel=False,
        is_rebroadcast=False,
    ):
        """
        Returns True if Web3.py successfully sends the tx
        Returns False if the tx is rejected, i.e. is a rebroadcast and the original tx has just been successful
        """

        if "nonce" not in self.data:
            self.data["nonce"] = self.account.nonce
            self.account.nonce += 1  # Update the nonce as the tx has been sent

        # Prevent accidentally sending twice:
        if self.last_sent and not is_cancel and not is_rebroadcast:
            raise Exception(
                "Can only run send() twice if the second is specified as a cancel or a rebroadcast!"
            )

        if self.account.private_key:
            # Will not be a private key if an unlocked account using ganache (works with send_transaction directly)
            self.signed_data = self.net.sync_provider.eth.account.sign_transaction(
                self.data, self.account.private_key
            )

        try:
            if self.account.private_key:
                self.hash = await self.net.provider.eth.send_raw_transaction(
                    self.signed_data.rawTransaction
                )
            else:
                # Will not be a private key if an unlocked account using ganache (works with send_transaction directly)
                self.hash = await self.net.provider.eth.send_transaction(self.data)
            # print("success!!")
            # print(self.hash.hex())
        except ValueError as e:
            # print("ERRROR!!!!")
            # print(e)
            if len(e.args) and type(e.args[0]) == dict and "message" in e.args[0]:
                message = e.args[0]["message"].lower()
                if (
                    message.startswith("the tx doesn't have the correct nonce")
                    or message.startswith(  # ganache specific that seems similar
                        "transaction can't be replaced, mining has already started"
                    )
                    or message.startswith("nonce too low")
                ):
                    # Allow failure if is a rebroadcast and says wrong nonce, means the prev tx must have succeeded
                    assert (
                        is_rebroadcast
                    ), "tx wrong nonce even even though wasn't rebroadcast! Error: {}".format(e)
                    print("THINK TX SUCCEEDED WHILST ATTEMPTING REBROADCAST")
                    return False

            # Otherwise raise the error:
            raise e

        self.status = TX_PENDING
        self.last_sent = timezone.now()

        # Nonce should stay the same if it's a rebroadcast (i.e. second send of a tx) or cancel (which is still infact a specific type of rebroadcast)
        if not is_rebroadcast and not is_cancel:
            # TODO think the best way to agnosticise all of this is just to do when nonce isn't provided, if nonce provided then should be assumed to be a repeat
            # Add to the pool to monitor:
            tx_pool_holder.TX_POOL.append(self)

        # Add the current transaction information to the tx_attempts pool of the tx:
        self.tx_attempts.append(
            {
                "sent": self.last_sent,
                "data": copy.deepcopy(self.data),
                "hash": self.hash,
                "is_cancel": is_cancel,
            }
        )

        return True

    def calc_rebroadcast_priority_fee(self, ideal_priority_fee):
        assert "maxPriorityFeePerGas" in self.data, "Tx should have already happened!"
        min_priority_fee = int(
            self.data["maxPriorityFeePerGas"] * (1 + (REBROADCAST_GAS_MIN_PERC_INCREASE / 100))
        )
        return max(ideal_priority_fee, min_priority_fee)

    async def cancel(self):
        assert self.status == TX_PENDING, self.status

        # Send through a insignificant tx as small as possible with higher fees to cancel the original tx:

        gas_info = await self.calc_gas_info(is_cancel=True)

        # Rebroadcasts have to be specifically higher than the last
        new_max_priority_fee = self.calc_rebroadcast_priority_fee(gas_info["maxPriorityFeePerGas"])
        extra_rebroadcast_fees = new_max_priority_fee - gas_info["maxPriorityFeePerGas"]

        self.data = {
            # Add the extra miner value, or the new calculations if higher:
            "maxFeePerGas": gas_info["maxFeePerGas"] + extra_rebroadcast_fees,
            "maxPriorityFeePerGas": new_max_priority_fee,
            "gas": gas_info["gas"],
            "nonce": self.data["nonce"],  # Same nonce as original
            "chainId": self.net.chain_id,
            "to": self.account.address,
            "value": 0,
        }

        # Attempt the cancellation, note, may not work, transaction monitor will set TX_SUCCESS or TX_CANCELLED depending on which tx gets filled first.
        cancel_sent_successfully = await self.send(is_cancel=True)
        return cancel_sent_successfully

    async def wait(self, remove_from_pool=True, assert_success_or_debug=True):
        # Wait for the tx to complete, fail or revert
        assert self in self.pool or len(self.tx_flash_attempts) > 0

        # TODO should migrate the wait func of flashbots into the normal tx monitor as the approach does change very little

        if len(self.tx_flash_attempts) > 0:
            # Currently flash txs are handled in a separate way, don't want to pollute the prev infrastructure
            found = False
            while (
                self.net.sync_provider.eth.block_number <= self.flash_last_block_number
                and not found
            ):
                for bundle in self.tx_flash_attempts:
                    # The first tx in the bundle should be the actual tx, if there is a second then it was just
                    # a filler tx to get the gas up to 42000
                    tx_data = bundle[0]
                    try:
                        # If this succeeds the transaction has completed successfully!
                        tx_receipt = await self.account.net.provider.eth.get_transaction_receipt(
                            tx_data["hash"].hex()
                        )
                        self.hash = tx_data["hash"]
                        self.receipt = tx_receipt

                        # Check to see if the tx was reverted:
                        if tx_receipt["status"] == 1:
                            self.status = TX_SUCCESS
                        else:
                            self.status = TX_REVERTED

                        found = True
                        break
                    except TransactionNotFound:
                        pass

            if not found:
                self.status = TX_DROPPED
        else:
            while True:
                for tx in self.pool:
                    if tx == self:
                        if tx.status != TX_PENDING:
                            if remove_from_pool:
                                self.pool.remove(self)

                            if assert_success_or_debug:
                                self.assert_success_or_debug()

                            return
                await asyncio.sleep(0.1)

    def actual_cost(self):
        assert self.status == TX_SUCCESS or self.status == TX_CANCELLED, self.status

        return self.receipt.gasUsed * self.receipt.effectiveGasPrice

    def assert_success_or_debug(self):
        if self.status == TX_SUCCESS:
            return True

        reason = "n/a"
        if self.status == TX_REVERTED:
            reason = self.reversion_reason()

        raise Exception("Status: {}. Reason: {}".format(self.status, reason))

    def reversion_reason(self):
        assert self.status == TX_REVERTED, self.status

        # Replay the transaction locally:
        try:
            self.net.sync_provider.eth.call(self.data, self.receipt.blockNumber)
        except Exception as e:
            return str(e)

        return "Not sure. Tx succeeds locally!"

    async def rebroadcast_if_needed(self, dropped=False, compete_with=None):
        if self.dont_rebroadcast:
            return

        new_gas_info = await self.calc_gas_info()

        # Compete with a specific tx:
        if compete_with:
            # Adding 35% to their fees TODO: should be way lower in practice or need random
            # Rebroadcasts have to be specifically higher than the last
            new_max_priority_fee = self.calc_rebroadcast_priority_fee(
                int(
                    compete_with.data["maxPriorityFeePerGas"]
                    + (compete_with.data["maxPriorityFeePerGas"] * (0.35 + (random.random() / 10)))
                )
            )
        else:
            # Rebroadcasts have to be specifically higher than the last
            new_max_priority_fee = self.calc_rebroadcast_priority_fee(
                new_gas_info["maxPriorityFeePerGas"]
            )

        extra_rebroadcast_fees = new_max_priority_fee - new_gas_info["maxPriorityFeePerGas"]

        rebroadcast = False
        # If it's been dropped then definitely rebroadcast:
        if dropped:
            rebroadcast = True
        else:
            for gas_key in new_gas_info:
                assert gas_key in self.data, self.data

                if new_gas_info[gas_key] > self.data[gas_key]:
                    rebroadcast = True
                    break

        if self.assume_always_rebroadcastable:
            time.sleep(
                0.1
            )  # During tests don't want it to go too wild (intentially using sync sleep!)

        if rebroadcast or self.assume_always_rebroadcastable:
            print("REBROADCASTING")
            # Update the gas information in self.data:
            self.data["maxFeePerGas"] = new_gas_info["maxFeePerGas"] + extra_rebroadcast_fees
            self.data["maxPriorityFeePerGas"] = new_max_priority_fee
            self.data["gas"] = new_gas_info["gas"]

            await self.send(is_rebroadcast=True)
        else:
            print("NOT REBROADCASTING")
