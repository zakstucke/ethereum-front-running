from backend.primary.views import GetTxs, RunSimulation, GetBalances


URLS = {
    "GET_TXS": {"URL": "get-txs", "CLASS_VIEW": GetTxs},
    "RUN_SIMULATION": {"URL": "run-simulation", "CLASS_VIEW": RunSimulation},
    "BALANCES": {"URL": "balances", "CLASS_VIEW": GetBalances},
}
