import asyncio
import copy
from datetime import datetime
from web3 import Web3

from backend.asyncio_utils import sync_to_async
from backend.test_utils import TestCase, async_test
from backend.tx.tx import create_tx, TX_SUCCESS, TX_CANCELLED, GAS_BASIC_TX
from backend.tx.models import DbTx
from backend.account.account import create_account


class TransactionTests(TestCase):
    @async_test()
    async def test_01_send(self):

        # Do twice to test over 2 separate blocks:
        for x in range(2):
            account_1 = self.accounts[0]
            account_1_old_balance = await account_1.balance()
            account_2 = self.accounts[1]
            account_2_old_balance = await account_2.balance()

            # Send 0.1 ether from account_1 to account_2:
            data = {"to": account_2.address, "value": Web3.toWei(0.1, "ether")}
            tx = await create_tx(account_1, data)

            # Send and then wait for tx to complete:
            await tx.send()

            # Should create the DbTx object
            await tx.log_tx()

            db_tx_obj = await sync_to_async(DbTx.objects.get)(hash=tx.hash.hex())
            self.assertEqual(db_tx_obj.status, tx.status)

            # Confirm a second send attempt (which isn't cancel or rebroadcast) raises exception:
            with self.assertRaises(Exception):
                await tx.send()

            # Should now be pending in the pool:
            self.assertTrue(tx in tx.pool, tx.pool)

            await tx.wait()
            # Should update the DbTx object
            await tx.log_tx()

            # By default, wait should remove the tx from the pool:
            self.assertTrue(tx not in tx.pool, tx.pool)

            self.assertEqual(tx.status, TX_SUCCESS)

            # Log object should have been updated aswell:
            await sync_to_async(db_tx_obj.refresh_from_db)()
            self.assertEqual(db_tx_obj.status, TX_SUCCESS)

            self.assertEqual(type(tx.hash.hex()), str)
            self.assertEqual(type(tx.last_sent), datetime)

            # Confirm balance changes are accurate:
            acc_1_balance_change = await account_1.balance() - account_1_old_balance
            acc_2_balance_change = await account_2.balance() - account_2_old_balance
            cost = Web3.toWei(0.1, "ether") + tx.actual_cost()
            gain = Web3.toWei(0.1, "ether")
            self.assertEqual(cost * -1, acc_1_balance_change)
            self.assertEqual(gain, acc_2_balance_change)

    # Need not insta for same block
    @async_test(block_time=0.5)
    async def test_02_send_multiple_same_block(self):
        account_1 = self.accounts[0]
        account_1_old_balance = await account_1.balance()
        account_2 = self.accounts[1]
        account_2_old_balance = await account_2.balance()

        # Send 0.1 ether from account_1 to account_2 5 times:
        data = {"to": account_2.address, "value": Web3.toWei(0.1, "ether")}
        txs = []
        for x in range(5):
            tx = await create_tx(account_1, data)
            await tx.send()
            txs.append(tx)

        self.assertEqual(len(tx.pool), 5)

        # Wait for all to complete:
        for tx in txs:
            await tx.wait()
            self.assertEqual(tx.status, TX_SUCCESS)

        # Confirm balance changes make sense:
        # Confirm balance changes are accurate:
        acc_1_balance_change = await account_1.balance() - account_1_old_balance
        acc_2_balance_change = await account_2.balance() - account_2_old_balance
        cost = Web3.toWei(0.1, "ether") * 5 + sum([tx.actual_cost() for tx in txs])
        gain = Web3.toWei(0.1, "ether") * 5
        self.assertEqual(cost * -1, acc_1_balance_change)
        self.assertEqual(gain, acc_2_balance_change)

        # Confirm can happen in 2 blocks (not trying for all in one as maybe hit boundary and in 2 blocks)
        # Put in a set and therefore should only be one item as all the same:
        blocks = set(tx.receipt.blockNumber for tx in txs)
        self.assertTrue(len(blocks) <= 2, blocks)

    @async_test()
    async def test_03_send_and_rebroadcast(self):
        account_1 = self.accounts[0]
        account_2 = self.accounts[1]

        original_nonce = account_1.nonce

        # Send 0.1 ether from account_1 to account_2 5 times:
        # Send the third tx with too low gas price, forcing a rebroadcast
        data = {"to": account_2.address, "value": Web3.toWei(0.1, "ether")}
        txs = []
        for x in range(5):
            if x == 2:
                tx = await create_tx(account_1, data, simulate_low_gas=True)
                await tx.send()
                tx.simulate_low_gas = False
                dodgy_tx_hash = tx.hash
                dodgy_tx_last_sent = tx.last_sent
                dodgy_tx_data = copy.deepcopy(tx.data)
            else:
                tx = await create_tx(account_1, data)
                await tx.send()
            txs.append(tx)

        # Wait for all to complete:
        for index, tx in enumerate(txs):
            await tx.wait()

            self.assertEqual(tx.status, TX_SUCCESS)

            # Should have multiple txs in tx_attempts:
            if index == 2:
                self.assertEqual(len(tx.tx_attempts), 2)
                print(tx.tx_attempts)
                self.assertEqual(tx.tx_attempts[0]["data"], dodgy_tx_data)
                self.assertEqual(tx.tx_attempts[0]["hash"], dodgy_tx_hash)
                self.assertEqual(tx.tx_attempts[0]["sent"], dodgy_tx_last_sent)
                self.assertEqual(tx.tx_attempts[0]["is_cancel"], False)
            else:
                self.assertEqual(len(tx.tx_attempts), 1)

            self.assertEqual(tx.tx_attempts[-1]["data"], tx.data)
            self.assertEqual(tx.tx_attempts[-1]["hash"], tx.hash)
            self.assertEqual(tx.tx_attempts[-1]["sent"], tx.last_sent)
            self.assertEqual(tx.tx_attempts[-1]["is_cancel"], False)

        # Despite rebroadcasting tx, nonce should have only increased by 5:
        self.assertEqual(original_nonce + 5, account_1.nonce)

    # Need non insta to have time to cancel:
    @async_test(block_time=0.5)
    async def test_04_cancel(self):
        account_1 = self.accounts[0]
        account_1_old_balance = await account_1.balance()
        account_2 = self.accounts[1]
        account_2_old_balance = await account_2.balance()

        original_nonce = account_1.nonce

        # Send 0.1 ether, but cancel:
        data = {"to": account_2.address, "value": Web3.toWei(0.1, "ether")}
        tx = await create_tx(account_1, data)

        await tx.send()
        await tx.cancel()
        await tx.wait(assert_success_or_debug=False)

        self.assertEqual(tx.status, TX_CANCELLED)
        self.assertEqual(len(tx.tx_attempts), 2)
        self.assertEqual(tx.tx_attempts[-1]["data"], tx.data)
        self.assertEqual(tx.tx_attempts[-1]["hash"], tx.hash)
        self.assertEqual(tx.tx_attempts[-1]["sent"], tx.last_sent)
        self.assertEqual(tx.tx_attempts[-1]["is_cancel"], True)

        # Account nonce should still increase by one:
        self.assertEqual(account_1.nonce, original_nonce + 1)

        # account_1 balance should have changed by the fees only:
        account_1_change = account_1_old_balance - await account_1.balance()
        self.assertEqual(account_1_change, tx.actual_cost())
        # account_2 balance shouldn't change:
        self.assertEqual(account_2_old_balance, await account_2.balance())

    # # Not insta as need time to rebroadcast:
    # @async_test(block_time=0.5)
    # async def test_05_tx_succeeds_with_rebroadcasts(self):
    #     account_1 = self.accounts[0]
    #     account_2 = self.accounts[1]

    #     # Will rebroadcast each loop, one of the txs will succeed:
    #     data = {"to": account_2.address, "value": Web3.toWei(0.01, "ether")}

    #     tx = await create_tx(account_1, data, assume_always_rebroadcastable=True)
    #     await tx.send()
    #     await tx.wait()
    #     self.assertEqual(tx.status, TX_SUCCESS)

    # Not insta as want some the account txs in the same block:
    # @async_test(block_time=1)
    # async def test_06_tx_multiple_accounts(self):
    #     account_1 = self.accounts[0]

    #     # Create 10 subaccounts:

    #     subs = []

    #     # TODO at some point still need to sort this out, seems like ganache just dies after 60 transactions or so
    #     for x in range(29):
    #         wallet = self.net.create_new_wallet()
    #         subs.append(
    #             await create_account(
    #                 self.net, address=wallet["address"], private_key=wallet["private_key"]
    #             )
    #         )

    #     # Send matic to each one:
    #     txs = []
    #     for sub in subs:
    #         tx = await create_tx(
    #             account_1,
    #             data={"to": sub.address, "value": Web3.toWei(1, "ether")},
    #             specific_gas=GAS_BASIC_TX,
    #         )
    #         await tx.send()
    #         txs.append(tx)
    #     await asyncio.wait([tx.wait() for tx in txs])

    #     # Send the matic back from each one:
    #     txs = []
    #     for sub in subs:
    #         tx = await create_tx(
    #             sub,
    #             data={"to": account_1.address, "value": Web3.toWei(0.5, "ether")},
    #             specific_gas=GAS_BASIC_TX,
    #         )
    #         await tx.send()
    #         txs.append(tx)
    #     await asyncio.wait([tx.wait() for tx in txs])
