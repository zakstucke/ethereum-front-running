import statistics
import time
import copy
import asyncio
from web3 import Web3
from datetime import timedelta
from django.utils import timezone

from dissertation.backend import settings
from dissertation.backend.utils import get_contract_info, run_ganache
from dissertation.backend.asyncio_utils import thread_wrapper
from dissertation.backend.test_utils import get_ganache_accounts
from dissertation.backend.net.net import create_net
from dissertation.backend.account.account import create_account
from dissertation.backend.contract.contract import create_contract
from dissertation.backend.tx.tx import create_tx, TX_SUCCESS, GAS_FAST, GAS_SLOW, GAS_AVERAGE


async def setup_env(net_name=None):
    if not net_name:
        net_name = "ETHEREUM_GOERLI"
    net = await create_net(settings.NETS[net_name])

    agent = await create_account(
        net, address=settings.AGENT_ADDRESS, private_key=settings.AGENT_PRIVATE_KEY
    )
    attacker = await create_account(
        net, address=settings.ATTACKER_ADDRESS, private_key=settings.ATTACKER_PRIVATE_KEY
    )

    return agent, attacker


def convert_params_to_attacker(params, attacker):
    # Convert contract parameters to my own addresses:

    new_params = []
    for param_name in params:
        old_value = params[param_name]
        # If param looks like an address, convert to own address, otherwise leave param unchanged:
        if Web3.isAddress(old_value):
            new_params.append(attacker.address)
        else:
            new_params.append(old_value)

    return new_params


async def fork_net(net):
    # Fork the current net with a new ganache forked net:

    # Use a sub port as ganache may already be running:
    port = settings.GANACHE_PORT + 1
    net_info = copy.deepcopy(settings.NETS["GANACHE"])
    net_info["url"] = "http://127.0.0.1:{}".format(port)
    net_info["chain_id"] = net.chain_id

    latest_block_num = (await net.latest_block)["number"]

    # Setting to instamine as want the simulation to run as fast as possible:
    run_ganache(
        fork_url=net.url,
        fork_block_num=latest_block_num,
        port=port,
        block_time=0,
        chain_id=net.chain_id,
    )
    sim_net = await create_net(net_info)

    return sim_net


# Now withdraw, but setup the attacker to be looking in the txpool for txs
async def attacker_displacement_loop(forked_net, attacker, contract, agent, experiment, attack_txs):
    net = attacker.net
    forked_attacker = await create_account(
        forked_net,
        address=attacker.address,
        private_key=attacker.private_key,
    )

    keep_looping = True

    # Is run in a wait() set to finish when another task finishes
    while keep_looping:
        # A generalised front runner that checks the mempool for txs it can take over and profit from
        pending_txs = await net.mempool
        for pending_tx in pending_txs:
            input = pending_tx["data"]
            from_address = pending_tx["from"]

            # Currently only want to look into the specific agent's transactions:
            if from_address.lower() == agent.address.lower():
                # XXX: (talk about this in critical eval as well) missing step here is not having to know the contract in advance
                function_called, params = contract.contract.decode_function_input(input)

                # Convert the params to the account
                # Do a simulation on testnet:
                sim_params = convert_params_to_attacker(params, forked_attacker)
                prev_balance = await forked_attacker.balance()
                # Simulate calling the function myself in different ways, and see if profit would be produced:
                data = contract.build_transacton_data(
                    function_called.fn_name,
                    *sim_params,
                    extra_tx_data={"from": forked_attacker.address}
                )
                # Remove the nonce as different account (TODO: should probably auto happen as part of Tx class)
                if "nonce" in data:
                    del data["nonce"]

                tx = await create_tx(forked_attacker, data=data)
                await tx.send()
                await tx.wait()
                tx_is_profitable = (
                    tx.status == TX_SUCCESS and await forked_attacker.balance() > prev_balance
                )

                print("IS PROF: {}".format(tx_is_profitable))
                # If a profitable tx, try and compete for real:
                if tx_is_profitable:
                    real_params = convert_params_to_attacker(params, attacker)
                    data = contract.build_transacton_data(
                        function_called.fn_name,
                        *real_params,
                        extra_tx_data={"from": attacker.address}
                    )
                    tx = await create_tx(attacker, data=data, gas_speed=GAS_FAST)

                    await tx.send()
                    # Initial pending log happens here, completion log in main script as this thread will be killed if the agent's tx returns first.
                    desc = "Displacing profitable tx with own information."
                    await tx.log_tx(description=desc, experiment=experiment)
                    attack_txs.append(tx)  # Need to wait for it in main thread instead

                    # If already found a tx to displace, don't keep searching anymore:
                    keep_looping = False

        # To make sure doesn't get stuck in infinite loop:
        await asyncio.sleep(0.01)

    # If makes it out, don't want to exit as that exists the wait loop, instead fake loop:
    while True:
        await asyncio.sleep(100)


async def sim_displacement(experiment, use_flash, agent, attacker, contract_address=None):
    if not contract_address:
        contract_address = settings.DISPLACEMENT_ADDRESS

    net = agent.net

    con_info = get_contract_info("Displacement")
    abi = con_info["abi"]

    contract = await create_contract(net, abi=abi, address=contract_address)

    # Send 0.01 eth to contract:
    to_send_aes = 0.01
    tx_data = contract.build_transacton_data(
        "receiveFunds", extra_tx_data={"value": Web3.toWei(to_send_aes, "ether")}
    )
    tx = await create_tx(agent, tx_data)
    await tx.send()
    desc = "Agent sending initial {} ETH to holder contract.".format(to_send_aes)
    await tx.log_tx(description=desc, experiment=experiment)
    await tx.wait()
    await tx.log_tx(description=desc, experiment=experiment)

    # Fork the network with ganache:
    forked_net = await fork_net(agent.net)

    # Doesn't matter when flash being used:
    if not use_flash:
        await agent.net.wait_for_next_block()

    # Now run the attacker loop at the same time as trying to complete the tx:
    tx_data = contract.build_transacton_data("withdraw", extra_tx_data={"from": agent.address})
    if use_flash:
        desc = "Agent attempting to withdrawing from holder contract via MEV-geth/flashbots."
        tx = await create_tx(agent, tx_data, gas_speed=GAS_FAST)
        # Flash currently logs internally:
        await tx.send_flash(description=desc, experiment=experiment)
    else:
        desc = "Agent attempting to withdrawing from holder contract via traditional tx."
        tx = await create_tx(agent, tx_data, gas_speed=GAS_SLOW, dont_rebroadcast=True)
        await tx.send()
        await tx.log_tx(description=desc, experiment=experiment)
    # Wait for the tx to conclude but also run a second malicious actor that will steal the tx
    # Need to assign output to variable to force coroutine error
    print("Entering wait \n\n")
    attack_txs = []
    _ = await asyncio.wait(
        [
            tx.wait(assert_success_or_debug=False),
            attacker_displacement_loop(
                forked_net, attacker, contract, agent, experiment, attack_txs
            ),
        ],
        return_when=asyncio.FIRST_COMPLETED,
    )
    await tx.log_tx(description=desc, experiment=experiment)

    for tx in attack_txs:
        await tx.wait(assert_success_or_debug=False)
        await tx.log_tx(description=desc, experiment=experiment)


async def sandwich_attacker(agent, attacker, contract, experiment):
    net = agent.net

    for x in range(5):  # Run 5 times before giving up on finding something to sandwich
        pending_txs = await net.mempool
        for pending_tx in pending_txs:
            # Currently only want to look into the specific agent's transactions:
            if (
                pending_tx["from"].lower() == agent.address.lower()
                and pending_tx["to"].lower() == contract.address.lower()
            ):

                function_called, params = contract.contract.decode_function_input(
                    pending_tx["data"]
                )

                # Run sandwich when an agent runs a eth to token swap:
                if function_called.fn_name == "swapEthForTokens":
                    # Attacker buy tokens faster (with the same amount of orig tx):
                    buy_desc = "Attacker performing same action with high gas (will be included faster than agent)."
                    tx_data = contract.build_transacton_data(
                        "swapEthForTokens",
                        extra_tx_data={
                            "value": pending_tx["value"],
                            "from": attacker.address,
                        },
                    )
                    buy_tx = await create_tx(attacker, tx_data, gas_speed=GAS_FAST)
                    await buy_tx.send()
                    await buy_tx.log_tx(description=buy_desc, experiment=experiment)

                    # Attacker then sells tokens slowly:
                    sell_desc = "Attacker selling tokens back for ETH with low gas (will be included slower than agent)."
                    tx_data = contract.build_transacton_data(
                        "swapTokensForEth",
                        extra_tx_data={"from": attacker.address},
                    )
                    sell_tx = await create_tx(
                        attacker, tx_data, gas_speed=GAS_SLOW, dont_rebroadcast=True
                    )
                    await sell_tx.send()
                    await sell_tx.log_tx(description=sell_desc, experiment=experiment)

                    # Wait and log the two txs:
                    await buy_tx.wait()
                    await sell_tx.wait()
                    await buy_tx.log_tx(description=buy_desc, experiment=experiment)
                    await sell_tx.log_tx(description=sell_desc, experiment=experiment)

                    # Once found don't want to run again:
                    break

        await asyncio.sleep(0.1)  # Between checks


async def sim_sandwich(experiment, use_flash, agent, attacker, contract_address=None):
    if not contract_address:
        contract_address = settings.SANDWICH_ADDRESS

    net = agent.net

    con_info = get_contract_info("Sandwich")
    abi = con_info["abi"]

    contract = await create_contract(net, abi=abi, address=contract_address)

    # Should start at the beginning of a new block:
    # Doesn't matter when flash being used:
    if not use_flash:
        await agent.net.wait_for_next_block()

    # Agent buy tokens:
    eth_to_spend = 0.05  # Leads to about a +- 0.015 change for both
    desc = "Agent swapping {} ETH for tokens in pool contract.".format(eth_to_spend)
    tx_data = contract.build_transacton_data(
        "swapEthForTokens",
        extra_tx_data={"value": Web3.toWei(eth_to_spend, "ether"), "from": agent.address},
    )
    tx = await create_tx(agent, tx_data, gas_speed=GAS_AVERAGE, dont_rebroadcast=True)
    if use_flash:
        # Logs internally
        await tx.send_flash(description=desc, experiment=experiment)
    else:
        await tx.send()
        await tx.log_tx(description=desc, experiment=experiment)

    # Wait for the agent's tx to finish and run the sandwich_attacker
    _ = await asyncio.wait(
        [
            tx.wait(assert_success_or_debug=False),
            sandwich_attacker(agent, attacker, contract, experiment),
        ],
        return_when=asyncio.ALL_COMPLETED,
    )

    # Log the agent's tx outcome:
    await tx.log_tx(description=desc, experiment=experiment)

    # Agent then sells tokens:
    tx_data = contract.build_transacton_data(
        "swapTokensForEth",
        extra_tx_data={"from": agent.address},
    )
    tx_sell = await create_tx(agent, tx_data)
    await tx_sell.send()
    sell_desc = "Agent selling tokens back for ETH (cleanup for outcome comparison)."
    await tx_sell.log_tx(description=sell_desc, experiment=experiment)
    await tx_sell.wait()
    await tx_sell.log_tx(description=sell_desc, experiment=experiment)

    # print("AGENT ETH BALANCE: {}".format(await net.balance(agent.address)))
    # print("CONTRACT ETH BALANCE: {}".format(await net.balance(contract.address)))
    # print("TOKENS IN CONTRACT: {}".format(contract.call_function("POOL_TOKEN_BALANCE")))
    # print("AGENT TOKENS: {}".format(contract.call_function("AGENT_TOKEN_BALANCE")))
    # print("ATTACKER TOKENS: {}".format(contract.call_function("ATTACKER_TOKEN_BALANCE")))


async def sim_pga(experiment, use_flash, agent, attacker, contract_address=None):
    net = agent.net

    con_info = get_contract_info("Displacement")
    abi = con_info["abi"]
    bytecode = con_info["bytecode"]

    account_info = get_ganache_accounts()
    other_address = list(account_info.keys())[-1]
    other_account = await create_account(
        net, address=other_address, private_key=account_info[other_address]
    )

    # Deploy the contract (with a different account to not mess up the balance changes):
    contract = await create_contract(net, abi=abi, bytecode=bytecode)
    tx = await contract.deploy_contract(other_account, agent.address, attacker.address)
    assert tx.status == TX_SUCCESS, tx.status
    await tx.log_tx(
        description="Setup: other account deploying displacement contract for experiment.",
        experiment=experiment,
    )

    # Send 5 eth to contract:
    to_send_aes = 5
    tx_data = contract.build_transacton_data(
        "receiveFunds", extra_tx_data={"value": Web3.toWei(to_send_aes, "ether")}
    )
    tx = await create_tx(other_account, tx_data)
    await tx.send()
    desc = "Setup: other account sending initial {} ETH to holder contract.".format(to_send_aes)
    await tx.log_tx(description=desc, experiment=experiment)

    # Fund the agent and attacker:
    eth_to_fund = Web3.toWei("5", "ether")
    tx2_desc = "Setup: other account funding agent"
    tx2 = await create_tx(other_account, data={"to": agent.address, "value": eth_to_fund})
    await tx2.send()
    await tx2.log_tx(description=tx2_desc, experiment=experiment)

    tx3_desc = "Setup: other account funding attacker"
    tx3 = await create_tx(other_account, data={"to": attacker.address, "value": eth_to_fund})
    await tx3.send()
    await tx3.log_tx(description=tx3_desc, experiment=experiment)

    await tx.wait()
    await tx.log_tx(description=desc, experiment=experiment)
    await tx2.wait()
    await tx2.log_tx(description=tx2_desc, experiment=experiment)
    await tx3.wait()
    await tx3.log_tx(description=tx3_desc, experiment=experiment)

    # Update the start balances as the usual calc will now be wrong:
    experiment.agent_start_balance = await agent.balance()
    experiment.attacker_start_balance = await attacker.balance()

    # Should start at the beginning of a new block:
    # Doesn't matter when flash being used:
    if not use_flash:
        await agent.net.wait_for_next_block()

    # Send initial agent and attacker:
    agent_tx_data = contract.build_transacton_data(
        "withdraw", extra_tx_data={"from": agent.address}
    )
    agent_tx = await create_tx(agent, agent_tx_data, assume_always_rebroadcastable=True)
    await agent_tx.send()
    await agent_tx.log_tx(description="Agent attempting to withdraw.", experiment=experiment)

    attacker_tx_data = contract.build_transacton_data(
        "withdraw", extra_tx_data={"from": attacker.address}
    )
    attacker_tx = await create_tx(attacker, attacker_tx_data, assume_always_rebroadcastable=True)
    await attacker_tx.send()
    await attacker_tx.log_tx(description="Attacker attempting to withdraw.", experiment=experiment)

    agent_desc = "Agent rebroadcasting with higher gas."
    attacker_desc = "Attacker rebroadcasting with higher gas."
    for x in range(12):
        await agent_tx.rebroadcast_if_needed(compete_with=attacker_tx)
        await agent_tx.log_tx(
            as_new=True, description="{}: {}".format(x + 1, agent_desc), experiment=experiment
        )
        await attacker_tx.rebroadcast_if_needed(compete_with=agent_tx)
        await attacker_tx.log_tx(
            as_new=True, description="{}: {}".format(x + 1, attacker_desc), experiment=experiment
        )

    await agent_tx.wait(assert_success_or_debug=False)
    await agent_tx.log_tx(description=agent_desc, experiment=experiment)
    await attacker_tx.wait(assert_success_or_debug=False)
    await attacker_tx.log_tx(description=attacker_desc, experiment=experiment)
    assert agent_tx.status == TX_SUCCESS or attacker_tx.status == TX_SUCCESS, (
        agent_tx.status,
        attacker_tx.status,
    )


async def sim_sybil(base_agent, tx_data, number_of_agents, eth_to_fund):
    agents = []

    # Spwan the agents:
    for x in range(number_of_agents):
        wallet_info = base_agent.net.create_new_wallet()
        agents.append(
            await create_account(
                base_agent.net,
                address=wallet_info["address"],
                private_key=wallet_info["private_key"],
            )
        )

    # Fund the new wallets:
    txs = []
    for agent in agents:
        txs.append(await create_tx(base_agent, {"to": agent.address, "value": eth_to_fund}))
    await asyncio.wait([tx.send() for tx in txs])
    await asyncio.wait([tx.wait() for tx in txs])

    # Execute the distributed attack:
    txs = []
    for agent in agents:
        tx_data_personal = copy.deepcopy(tx_data)
        tx_data_personal["from"] = agent.address
        txs.append(await create_tx(agent, tx_data_personal))
    await asyncio.wait([tx.send() for tx in txs])
    await asyncio.wait([tx.wait() for tx in txs])


@thread_wrapper
async def get_balances():
    # Returns [[time, balance]] for the past hour
    # balance values for start and end, plus after any transactions

    agent, attacker = await setup_env()

    # get the txs over the last hour:
    start_time = timezone.now() - timedelta(hours=1)
    start_block_num = await agent.net.get_block_num_at_time(start_time)
    end_block = await agent.net.latest_block
    end_block_num = end_block["number"]

    data = []
    for acc in [agent, attacker]:
        user_data = []
        txs_data = await acc.transaction_history(start_block_num, end_block_num)
        # Record start of hour:
        start_balance = Web3.fromWei(await acc.balance(block=start_block_num), "ether")
        user_data.append([start_time.timestamp(), start_balance])

        # Record after each tx:
        for tx in txs_data:
            assert int(tx["blockNumber"]) >= int(start_block_num), (
                tx["blockNumber"],
                start_block_num,
            )
            bal = Web3.fromWei(await acc.balance(block=tx["blockNumber"]), "ether")
            user_data.append([tx["timeStamp"], bal])
        # Record end balance also:
        end_balance = Web3.fromWei(await acc.balance(), "ether")
        user_data.append([timezone.now().timestamp(), end_balance])
        data.append(user_data)

    return data


async def metrics():
    results = {"fork_time": None, "sim_time": None, "total_time": None}
    kill_ganache = run_ganache(block_time=1)
    net = await create_net(settings.NETS["GANACHE"])

    account_info = get_ganache_accounts()
    agent = await create_account(
        net,
        address=list(account_info.keys())[0],
        private_key=account_info[list(account_info.keys())[0]],
    )
    attacker = await create_account(
        net,
        address=list(account_info.keys())[1],
        private_key=account_info[list(account_info.keys())[1]],
    )

    con_info = get_contract_info("Displacement")
    abi = con_info["abi"]
    bytecode = con_info["bytecode"]

    # Deploy the contract:
    contract = await create_contract(net, abi=abi, bytecode=bytecode)
    tx = await contract.deploy_contract(agent, agent.address, attacker.address)
    assert tx.status, TX_SUCCESS

    # Setup agent tx to then simulate:
    to_send_aes = 0.01
    tx_data = contract.build_transacton_data(
        "receiveFunds", extra_tx_data={"value": Web3.toWei(to_send_aes, "ether")}
    )
    tx = await create_tx(agent, tx_data)
    await tx.send() and await tx.wait()
    await net.wait_for_next_block()

    before_fork = time.time()
    forked_net = await fork_net(net)
    forked_attacker = await create_account(
        forked_net,
        address=attacker.address,
        private_key=attacker.private_key,
    )
    after_fork = time.time()
    results["fork_time"] = after_fork - before_fork

    sim_time = []
    for x in range(10):
        before_sim = time.time()
        contract.net = forked_net
        tx_data = contract.build_transacton_data(
            "receiveFunds", extra_tx_data={"value": Web3.toWei(to_send_aes, "ether")}
        )
        tx = await create_tx(forked_attacker, tx_data)
        await tx.send()
        await tx.wait()
        after_sim = time.time()
        sim_time.append(after_sim - before_sim)

    kill_ganache()

    results["sim_time"] = statistics.mean(sim_time)
    results["total_time"] = results["fork_time"] + results["sim_time"]

    return results
