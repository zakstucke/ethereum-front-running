from backend.utils import get_contract_info
from backend.test_utils import TestCase, async_test
from backend.contract.contract import create_contract
from backend.tx.tx import TX_SUCCESS, TX_REVERTED, create_tx


class ContractTests(TestCase):
    @async_test()
    async def test_01_deploy_contract(self):
        account = self.accounts[0]

        con_info = get_contract_info("TestContract")
        abi = con_info["abi"]
        bytecode = con_info["bytecode"]

        # Deploy the contract:
        contract = await create_contract(self.net, abi=abi, bytecode=bytecode)
        tx = await contract.deploy_contract(account)

        self.assertEqual(tx.status, TX_SUCCESS)
        self.assertEqual(contract.address, tx.receipt.contractAddress)

        # Confirm we can now retrieve and interact with the contract from the node as new:
        address = contract.address
        contract = await create_contract(self.net, abi=abi, address=address)

        # Set the contract number:
        current_num = contract.call_function("retrieve")
        new_num = current_num + 7

        tx_data = contract.build_transacton_data("store", new_num)
        tx = await create_tx(account, data=tx_data)
        await tx.send() and await tx.wait()

        # Retrieve what was just set to the contract:
        self.assertEqual(contract.call_function("retrieve"), new_num)

    @async_test()
    async def test_02_revert(self):
        account = self.accounts[0]

        original_nonce = account.nonce

        con_info = get_contract_info("TestContract")
        abi = con_info["abi"]
        bytecode = con_info["bytecode"]

        # Deploy a contract:
        contract = await create_contract(self.net, abi=abi, bytecode=bytecode)
        await contract.deploy_contract(account)

        # This contract requires store num to not be 999, therefore should revert:
        # Store a number 10 times, on the 5th try set to 999 so will revert but all others should succeed:
        txs = []
        for x in range(10):
            if x == 4:
                tx_data = contract.build_transacton_data("store", 999)
                tx = await create_tx(account, data=tx_data, ignore_reversion=True)
            else:
                tx_data = contract.build_transacton_data("store", x)
                tx = await create_tx(account, data=tx_data)

            await tx.send()
            txs.append(tx)

        for index, tx in enumerate(txs):
            await tx.wait(assert_success_or_debug=False)
            if index != 4:
                self.assertEqual(tx.status, TX_SUCCESS)
            else:
                self.assertEqual(tx.status, TX_REVERTED)
                self.assertTrue(
                    tx.reversion_reason().startswith(
                        "{'message': 'VM Exception while processing transaction: revert Cannot be 999!'"
                    ),
                    tx.reversion_reason(),
                )

        # Should have 11 nonces, 10 for the txs (revert uses the same nonce) and one for the deploy
        self.assertEqual(original_nonce + 11, account.nonce)

    # Not insta as need time to resend tx with data that won't revert with higher gas:
    @async_test(block_time=0.5)
    async def test_03_two_tries_same_nonce_first_would_revert_second_succeeds(self):
        account_1 = self.accounts[0]

        con_info = get_contract_info("TestContract")
        abi = con_info["abi"]
        bytecode = con_info["bytecode"]

        # This contract will revert if store(999) is attempted
        contract = await create_contract(self.net, abi=abi, bytecode=bytecode)
        await contract.deploy_contract(account_1)

        # Send with value of 999, will fail
        tx_data = contract.build_transacton_data("store", 999)
        tx = await create_tx(account_1, data=tx_data, ignore_reversion=True)
        await tx.send()

        # Sending a second time with value of 1 so should succeed:
        second_data = contract.build_transacton_data("store", 1)
        tx.data["data"] = second_data["data"]
        tx.assume_always_rebroadcastable = True
        await tx.rebroadcast_if_needed()
        tx.assume_always_rebroadcastable = False
        await tx.wait()

        self.assertEqual(len(tx.tx_attempts), 2)

        # Other way around should revert as second has higher priority
        tx_data = contract.build_transacton_data("store", 1)
        tx = await create_tx(account_1, data=tx_data, ignore_reversion=True)
        await tx.send()

        # Sending a second time with value of 999 so should fail:
        second_data = contract.build_transacton_data("store", 999)
        tx.data["data"] = second_data["data"]
        tx.assume_always_rebroadcastable = True
        await tx.rebroadcast_if_needed()
        tx.assume_always_rebroadcastable = False
        await tx.wait(assert_success_or_debug=False)

        self.assertEqual(len(tx.tx_attempts), 2)
        self.assertEqual(tx.status, TX_REVERTED)
