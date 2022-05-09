# from django.conf import settings
# from django.utils import timezone
from backend.overrides import models

# from solo.models import SingletonModel

from backend.primary.models import ExperimentLog
from backend.tx.tx import (
    GAS_SLOW,
    GAS_AVERAGE,
    GAS_FAST,
    TX_SUCCESS,
    TX_REVERTED,
    TX_PENDING,
    TX_CANCELLED,
    TX_DROPPED,
)

GAS_SPEEDS = [GAS_SLOW, GAS_AVERAGE, GAS_FAST]
# Not allowing unsent to be logged
TX_STATUSES = [TX_SUCCESS, TX_REVERTED, TX_PENDING, TX_CANCELLED, TX_DROPPED]


class DbTx(models.Model):
    description = models.CharField(max_length=1024, default="", blank=True)
    experiment = models.ForeignKey(
        ExperimentLog, on_delete=models.CASCADE, related_name="txs", null=True
    )

    node_url = models.CharField(max_length=1024)
    chain_id = models.PositiveIntegerField()
    account_address = models.CharField(max_length=1024)

    status = models.CharField(
        choices=[[status, status.title()] for status in TX_STATUSES],
        default=TX_PENDING,
        max_length=256,
    )
    gas_speed = models.CharField(
        choices=[[speed, speed.title()] for speed in GAS_SPEEDS], max_length=256
    )
    nonce = models.PositiveIntegerField(default=1)
    data = models.JSONField()
    hash = models.CharField(
        max_length=1024
    )  # Should always have been sent by the time it's logged so should have a hash

    receipt = models.JSONField(null=True)
    last_sent = models.DateTimeField(null=True)

    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
