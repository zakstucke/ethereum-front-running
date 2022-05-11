import json
import subprocess
import os
import time
import socket
import pprint
import aiohttp
from getpass import getpass
from web3 import Web3
from eth_account.account import Account as EthAccount
from functools import wraps

import backend.settings as settings

GANACHE_PATH = os.path.join(settings.PROJECT_DIR, "node_modules", ".bin", "ganache")
GANACHE_KEYS_PATH = os.path.join(settings.PROJECT_DIR, "process_data", "ganache_keys.json")


def get_contract_info(contract_name):
    with open(os.path.join(settings.CONTRACT_PATH, "{}.json".format(contract_name)), "r") as file:
        info = json.load(file)
        return info


# Handles some common rpc errors that should be ignored and retried:
def handle_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        i = 0
        while True:
            try:
                return func(*args, **kwargs)
            except (ValueError, aiohttp.client_exceptions.ClientOSError) as e:
                print("HANDLED ERROR")
                message = str(e)
                print(message)

                if i > 5:
                    raise e

            i += 1

    return wrapper


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def kill_process_on_port(port):
    while is_port_in_use(port):
        # Keep on trying to kill until it succeeds:
        os.system("fuser -k {}/tcp".format(port))
        time.sleep(0.2)


def run_ganache(
    fork_url=False,
    fork_cache=True,
    fork_block_num=None,
    chain_id=settings.GANACHE_CHAIN_ID,
    port=settings.GANACHE_PORT,
    block_time=0,  # 1 second. NOTE: if setting to more than 0 (i.e. not insta, seems to drop transactions occasionally and can't be relied upon when trying to push through a lot of transactions)
    instamine_type="strict",
    unlocked_accounts=[],  # Can be used to send transactions from existing addresses
    verbose=False,
):
    # Quit ganache if it was previously running:

    if is_port_in_use(port):
        kill_process_on_port(port)

    command = [
        GANACHE_PATH,
        "--chain.chainId='{}'".format(chain_id),
        "--port='{}'".format(port),
        "--wallet.accountKeysPath='{}'".format(GANACHE_KEYS_PATH),
        "--wallet.defaultBalance='1000000'",
        "--chain.asyncRequestProcessing=true",
        "--miner.blockGasLimit='1000000000000'",
    ]

    if block_time > 0:
        command.append("--miner.blockTime='{}'".format(block_time))
    else:
        command.append("--miner.instamine='{}'".format(instamine_type))

    if fork_url:
        command.append("--fork.url='{}'".format(fork_url))
        if fork_block_num:
            command.append("--fork.blockNumber='{}'".format(fork_block_num))

    if unlocked_accounts:
        for account in unlocked_accounts:
            command.append("--unlock='{}'".format(account))

    if not fork_cache:
        command.append("--fork.disableCache")
        command.append("--fork.deleteCache")

    if verbose:
        command.append("--logging.verbose")

    ganache_log_path = os.path.join(settings.PROJECT_DIR, "process_data", "ganache_log.txt")
    ganache_err_path = os.path.join(settings.PROJECT_DIR, "process_data", "ganache_err.txt")

    # Runs ganache as a non-blocking subprocess, logs stdout and errors to files in process_data:
    # NOTE: currently overwriting each run, may be beneficial to solve this in some way at some point.
    with open(ganache_log_path, "w") as out, open(ganache_err_path, "w") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err)

    # Wait for port to start listening:
    timeout = 5
    start = time.time()
    while not is_port_in_use(port):
        time.sleep(0.01)
        time_taken = time.time() - start
        if time_taken > timeout:
            raise Exception("Ganache did not start within {} seconds".format(timeout))

    # Returned to allow the process to be ended later on:
    def kill_ganache():
        process.kill()

    return kill_ganache


def fee_history_formatter(fee_history):

    num_blocks = len(fee_history.baseFeePerGas)
    oldest_block = fee_history.oldestBlock

    blocks = []
    for index, block_num in enumerate(range(oldest_block, oldest_block + num_blocks - 1)):
        blocks.append(
            {
                "block": block_num,
                "baseFeePerGas": fee_history.baseFeePerGas[index],
                "gasUsedRatio": fee_history.gasUsedRatio[index],
                "priorityFeePerGas": fee_history.reward[index],
            }
        )

    return blocks


def get_ganache_accounts():
    with open(GANACHE_KEYS_PATH, "r") as file:
        info = json.load(file)

    # This is actually a dict with the address as key and value as private key:
    return info["private_keys"]


def encrypt_account(to_json=True, private_key=None, passphrase=None, iterations=None):
    # Will get from command line if not supplied:
    if not private_key:
        private_key = getpass("Private key: ")
    if not passphrase:
        passphrase = getpass("Password: ")

    account = EthAccount.from_key(private_key)
    res = account.encrypt(passphrase, iterations=iterations)
    if to_json:
        return json.dumps(res)
    return res


def format_address(address):
    address = Web3.toChecksumAddress(address)
    assert Web3.isAddress(address), "Not a valid address! Entered: {}".format(address)
    return address


def prettify(json_string):
    return pprint.PrettyPrinter(indent=2).pformat(json_string)
