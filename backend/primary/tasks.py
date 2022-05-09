from backend.celery.config import logged_task

from web3 import Web3

from django.utils import timezone

from backend.utils import run_ganache
from backend.asyncio_utils import async_runner, thread_wrapper, sync_to_async
from backend.primary.sims import setup_env, sim_displacement, sim_sandwich, sim_pga
from backend.primary.models import ExperimentLog


async def execute_experiment(
    sim_routine,
    experiment,
    use_flash,
    agent=None,
    attacker=None,
    contract_address=None,
    net_name=None,
):
    try:
        if not agent or not attacker:
            agent, attacker = await setup_env(net_name=net_name)

        experiment.agent_start_balance = await agent.balance()
        experiment.attacker_start_balance = await attacker.balance()

        await sim_routine(experiment, use_flash, agent, attacker, contract_address=contract_address)

        agent_change = (await agent.balance()) - experiment.agent_start_balance
        agent_mul = 1 if agent_change >= 0 else -1
        attacker_change = (await attacker.balance()) - experiment.attacker_start_balance
        attacker_mul = 1 if attacker_change >= 0 else -1

        experiment.agent_balance_change = agent_mul * Web3.fromWei(abs(agent_change), "ether")
        experiment.attacker_balance_change = attacker_mul * Web3.fromWei(
            abs(attacker_change), "ether"
        )
    except Exception as e:
        raise e
    finally:
        # Even if errors still mark as finished to allow a rerun straight away
        experiment.finished = True
        await sync_to_async(experiment.save)()


@logged_task()
def run_displacement_task(self, logger, use_flash):
    if use_flash:
        send_type = "MEV-geth / Flashbots Auction"
    else:
        send_type = "Traditional"
    name = "Experiment started: Displacement - {}".format(send_type)
    experiment = ExperimentLog.objects.create(name=name, initiate_time=timezone.now())
    async_runner(thread_wrapper(execute_experiment)(sim_displacement, experiment, use_flash))


@logged_task()
def run_sandwich_task(self, logger, use_flash):
    if use_flash:
        send_type = "MEV-geth / Flashbots Auction"
    else:
        send_type = "Traditional"
    name = "Experiment started: Sandwich - {}".format(send_type)
    experiment = ExperimentLog.objects.create(name=name, initiate_time=timezone.now())
    async_runner(thread_wrapper(execute_experiment)(sim_sandwich, experiment, use_flash))


@logged_task()
def run_pga_task(self, logger, use_flash):
    if use_flash:
        send_type = "MEV-geth / Flashbots Auction"
    else:
        send_type = "Traditional"
    name = "Experiment started: Priority Gas Auction - {}".format(send_type)
    experiment = ExperimentLog.objects.create(name=name, initiate_time=timezone.now())

    kill_ganache = run_ganache(block_time=10)
    async_runner(
        thread_wrapper(execute_experiment)(sim_pga, experiment, use_flash, net_name="GANACHE")
    )
    kill_ganache()
