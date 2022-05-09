from web3 import Web3

from django.utils import timezone

from backend.utils import get_contract_info
from backend.asyncio_utils import sync_to_async
from backend.test_utils import TestCase, async_test
from backend.contract.contract import create_contract
from backend.tx.tx import TX_SUCCESS, create_tx
from backend.primary.sims import sim_displacement, sim_sandwich, sim_pga
from backend.primary.models import ExperimentLog
from backend.primary.tasks import execute_experiment


@sync_to_async
def create_experiment(name):
    experiment = ExperimentLog.objects.create(name=name, initiate_time=timezone.now())
    return experiment


class SimTests(TestCase):
    # Needs to be long so the attacker has time to check:
    @async_test(block_time=5)
    async def test_01_displacement(self):
        agent = self.accounts[0]
        attacker = self.accounts[1]

        con_info = get_contract_info("Displacement")
        abi = con_info["abi"]
        bytecode = con_info["bytecode"]

        # Deploy the contract:
        contract = await create_contract(self.net, abi=abi, bytecode=bytecode)
        tx = await contract.deploy_contract(agent, agent.address, attacker.address)
        self.assertEqual(tx.status, TX_SUCCESS)

        experiment = await create_experiment("Displacement")
        await execute_experiment(
            sim_displacement,
            experiment,
            False,
            agent=agent,
            attacker=attacker,
            contract_address=contract.address,
        )

        print("Agent change: {}".format(experiment.agent_balance_change))
        print("Attacker change: {}".format(experiment.attacker_balance_change))

        # Attacker should have successfully nabbed the cash:
        self.assertGreater(0, experiment.agent_balance_change)
        self.assertGreater(experiment.attacker_balance_change, 0)

    @async_test(block_time=2)
    async def test_02_sandwich(self):
        agent = self.accounts[0]
        attacker = self.accounts[1]

        con_info = get_contract_info("Sandwich")
        abi = con_info["abi"]
        bytecode = con_info["bytecode"]

        # Deploy the contract:
        contract = await create_contract(self.net, abi=abi, bytecode=bytecode)
        tx = await contract.deploy_contract(agent, agent.address, attacker.address)
        self.assertEqual(tx.status, TX_SUCCESS)

        # Initially fund with 0.5 eth:
        tx_data = contract.build_transacton_data(
            "receiveFunds",
            extra_tx_data={"value": Web3.toWei(0.5, "ether"), "from": agent.address},
        )
        tx = await create_tx(agent, tx_data)
        await tx.send() and await tx.wait()

        experiment = await create_experiment("Displacement")
        await execute_experiment(
            sim_sandwich,
            experiment,
            False,
            agent=agent,
            attacker=attacker,
            contract_address=contract.address,
        )

        print("Agent change: {}".format(experiment.agent_balance_change))
        print("Attacker change: {}".format(experiment.attacker_balance_change))

        # Attacker should have successfully nabbed the cash:
        self.assertGreater(0, experiment.agent_balance_change)
        self.assertGreater(experiment.attacker_balance_change, 0)

    @async_test(block_time=5)
    async def test_03_pga(self):
        agent = self.accounts[0]
        attacker = self.accounts[1]

        experiment = await create_experiment("Priority Gas Auction")
        await execute_experiment(
            sim_pga,
            experiment,
            False,
            agent=agent,
            attacker=attacker,
        )

        print("Agent change: {}".format(experiment.agent_balance_change))
        print("Attacker change: {}".format(experiment.attacker_balance_change))

        # One of them should have nabbed the cash:
        self.assertTrue(
            experiment.agent_balance_change > 0 or experiment.attacker_balance_change > 0,
            (experiment.agent_balance_change, experiment.attacker_balance_change),
        )
