import asyncio
from datetime import timedelta
from web3.exceptions import TransactionNotFound

from django.utils import timezone

from backend.asyncio_utils import indefinite_worker_wrapper
from backend.tx.tx import TX_SUCCESS, TX_PENDING, TX_CANCELLED, TX_REVERTED
import backend.tx.pool as tx_pool_holder


@indefinite_worker_wrapper
async def transaction_monitor():
    pending_txs = [tx for tx in tx_pool_holder.TX_POOL if tx.status == TX_PENDING]
    # Order the transactions by nonce:
    pending_txs = sorted(pending_txs, key=lambda tx: tx.data["nonce"])

    # Need to also separate by account:
    account_pks = set()
    for tx in pending_txs:
        account_pks.add(tx.account.pk)

    pending_txs_by_account = []
    for pk in list(account_pks):
        account_txs = [tx for tx in pending_txs if tx.account.pk == pk]
        pending_txs_by_account.append(account_txs)

    for account_pending_txs in pending_txs_by_account:
        for tx in account_pending_txs:
            # Check if any of the attempts have succeeded:
            at_least_one_hash_found = False
            tx_receipt_found = False
            # Putting tx_attempts inside list to prevent looping through new txs added to the pool (through e.g. a rebroadcast) in the same loop
            for index, tx_attempt in enumerate(list(tx.tx_attempts)):
                print(
                    "Checking tx for account: {}, nonce: {}, attempt: {}...".format(
                        tx.account.address, tx.data["nonce"], index
                    )
                )
                try:
                    info = await tx.account.net.provider.eth.get_transaction(
                        tx_attempt["hash"].hex()
                    )
                    print("Found tx hash!")
                    at_least_one_hash_found = True
                except TransactionNotFound:
                    info = None

                if info:
                    try:
                        # If this succeeds the transaction has completed successfully!
                        tx_receipt = await tx.account.net.provider.eth.get_transaction_receipt(
                            tx_attempt["hash"].hex()
                        )
                        tx_receipt_found = True

                        # Set the final value to the tx object:
                        tx.data = tx_attempt["data"]
                        tx.hash = tx_attempt["hash"]
                        tx.receipt = tx_receipt

                        # Check to see if the tx was reverted:
                        if tx_receipt["status"] == 1:
                            print("tx nonce: {} succeeded!".format(tx.data["nonce"]))

                            if tx_attempt["is_cancel"]:
                                tx.status = TX_CANCELLED
                            else:
                                tx.status = TX_SUCCESS

                        else:
                            print("tx nonce: {} reverted!".format(tx.data["nonce"]))
                            tx.status = TX_REVERTED

                        # Break from looping through the tx_attempts as one has succeeded
                        break

                    except TransactionNotFound:
                        print("tx nonce: {} receipt not yet found.".format(tx.data["nonce"]))

            print(at_least_one_hash_found, tx_receipt_found)
            if not at_least_one_hash_found:
                # Because of rebroadcast functionality, shouldn't disappear.
                # If the most recent tx is not in the pool within 10 seconds, tx must have been dropped:
                if tx.tx_attempts[-1]["sent"] < timezone.now() - timedelta(seconds=10):
                    # Resend the tx:
                    await tx.rebroadcast_if_needed(dropped=True)
            elif not tx_receipt_found:
                # Normal check to see if the tx needs rebroadcasting with a new gas price if now too low:
                await tx.rebroadcast_if_needed()

    await asyncio.sleep(0.5)
