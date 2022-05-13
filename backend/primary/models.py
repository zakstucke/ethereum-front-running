# from django.conf import settings
# from django.utils import timezone
# from unavailable.overrides import models
from django.db import models

class ExperimentLog(models.Model):
    name = models.CharField(max_length=256)
    initiate_time = models.DateTimeField()
    finished = models.BooleanField(default=False)

    # These are in wei:
    agent_start_balance = models.DecimalField(decimal_places=18, max_digits=50, default=0)
    attacker_start_balance = models.DecimalField(decimal_places=18, max_digits=50, default=0)

    # This are in ether
    agent_balance_change = models.DecimalField(decimal_places=18, max_digits=28, default=0)
    attacker_balance_change = models.DecimalField(decimal_places=18, max_digits=28, default=0)

    class Meta:
        verbose_name = "Experiment Log"
        verbose_name_plural = "Experiment Logs"

    def __str__(self):
        # Used to convert to charfield in the tx serializer so don't change
        return self.name
