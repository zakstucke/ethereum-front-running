import os
import json
from web3 import Web3
from decouple import Config, RepositoryEnv
from getpass import getpass
from eth_account.account import Account

PROJECT_DIR = "."

ENV = Config(RepositoryEnv(os.path.join(PROJECT_DIR, "private", "env")))

STORE_PASSWORD = ENV("STORE_PASSWORD", default=None)

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.forms",
    "django.contrib.staticfiles",
    "rest_framework",
    "backend.net",
    "backend.account",
    "backend.tx",
    "backend.contract",
    "backend.primary",
]

DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': "default"
    }
}

def get_store_pass():
    global STORE_PASSWORD

    if not STORE_PASSWORD:
        STORE_PASSWORD = getpass("Store password: ")

    return STORE_PASSWORD

# After implementing a private environment file and encrypting an agent and attcker account, replace the below lines:
AGENT_PRIVATE_KEY = ""
AGENT_ADDRESS = ""
ATTACKER_PRIVATE_KEY = ""
ATTACKER_ADDRESS = ""
# AGENT_PRIVATE_KEY = Account.decrypt(ENV("AGENT"), get_store_pass()).hex()
# AGENT_ADDRESS = Web3.toChecksumAddress(json.loads(ENV("AGENT"))["address"])
# ATTACKER_PRIVATE_KEY = Account.decrypt(ENV("ATTACKER"), get_store_pass()).hex()
# ATTACKER_ADDRESS = Web3.toChecksumAddress(json.loads(ENV("ATTACKER"))["address"])

REQUEST_TIMEOUT_SECS = 100
MAX_ASYNC_REQUESTS = 100

ETHERSCAN_API_KEY = "2ZKVF135V16PM5YKE6XKDSAXXV547PQQ7S"
ETHERSCAN_HEADERS = {"Content-Type": "application/json", "User-Agent": ""}

GANACHE_CHAIN_ID = 1337
GANACHE_PORT = 8545

CONTRACT_PATH = os.path.join(
    PROJECT_DIR, "bin", "dissertation", "backend", "sol_files"
)

DISPLACEMENT_ADDRESS = "0xd5a3D9Ea4198b98efaD0128aC31252c7dCC57076"
SANDWICH_ADDRESS = "0xAf4F68594c2812E3fb407027D216105eB46f82Ed"

NETS = {
    "ETHEREUM_MAINNET": {
        "name": "ETHEREUM_MAINNET",
        "url": "https://mainnet.infura.io/v3/{}".format(ENV("INFURA_ID")),
        "chain_id": 1,
        "ws": None,
        "flashbots_url": "https://relay.flashbots.net",
        "scan_url": "https://api.etherscan.io/api",
    },
    "ETHEREUM_GOERLI": {
        "name": "ETHEREUM_GOERLI",
        "url": "https://goerli.infura.io/v3/{}".format(ENV("INFURA_ID")),
        "chain_id": 5,
        "ws": None,
        "flashbots_url": "https://relay-goerli.flashbots.net",
        "scan_url": "https://api-goerli.etherscan.io/api",
    },
    "POLYGON_MAINNET": {
        "name": "POLYGON_MAINNET",
        # "url": "https://polygon-mainnet.infura.io/v3/{}".format(ENV("INFURA_ID")),
        "url": "https://polygon-rpc.com",
        "chain_id": 137,
        "ws": None,
        "flashbots_url": "http://bor.txrelay.marlin.org",
        "scan_url": None,
    },
    "POLYGON_TESTNET": {
        "name": "POLYGON_TESTNET",
        "url": "https://polygon-mumbai.infura.io/v3/{}".format(ENV("INFURA_ID")),
        "chain_id": 80001,
        "ws": None,
        "flashbots_url": None,
        "scan_url": None,
    },
    "GANACHE": {
        "name": "GANACHE",
        "url": "http://127.0.0.1:{}".format(GANACHE_PORT),
        "chain_id": GANACHE_CHAIN_ID,
        "ws": None,
        "flashbots_url": None,
        "scan_url": None,
    },
}

# Don't worry not sensitive, used as an id when relaying bundles to build reputation.
# This account will never actually store real funds
FLASHBOTS_SIGNATURE_PRIVATE_KEY = (
    "0xc4c5b9e8b09731835d30cd1bcc81ca1ac909fed8953759092b4d34b9845093ca"
)
