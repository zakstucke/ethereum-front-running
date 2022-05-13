import os
import django
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.settings"
django.setup()
from django.core.management import call_command
call_command("migrate")

from backend.asyncio_utils import async_runner, thread_wrapper
from backend.primary.sims import sim_displacement
from backend.utils import get_ganache_accounts, run_ganache
from backend.net.net import create_net
from backend.account.account import create_account
from backend.contract.contract import create_contract
from backend.tx.tx import TX_SUCCESS
from backend.utils import get_contract_info

import backend.settings as settings

@thread_wrapper
async def main():
        kill_ganache_func = run_ganache(block_time=3)

        net = await create_net(settings.NETS["GANACHE"])

        account_info = get_ganache_accounts()
        accounts = [
            await create_account(net, address=address, private_key=account_info[address])
            for address in account_info
        ]    
        agent = accounts[0]
        attacker = accounts[1]

        con_info = get_contract_info("Displacement")
        abi = con_info["abi"]
        bytecode = con_info["bytecode"]

        # Deploy the contract:
        contract = await create_contract(net, abi=abi, bytecode=bytecode)
        tx = await contract.deploy_contract(agent, agent.address, attacker.address)
        assert tx.status == TX_SUCCESS

        await sim_displacement(
            None, # No experiment in case DB not connected
            False,
            agent=agent,
            attacker=attacker,
            contract_address=contract.address,
        )


async_runner(main())
