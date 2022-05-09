from rest_framework import serializers
from datetime import timedelta

from django.utils import timezone

from backend.primary.tasks import (
    run_displacement_task,
    run_sandwich_task,
    run_pga_task,
)
from backend.tx.models import DbTx
from backend.primary.models import ExperimentLog
from backend.tx.tx import GAS_AVERAGE, TX_SUCCESS, TX_PENDING, TX_REVERTED

displacement_sim_type = "displacement"
sandwich_sim_type = "sandwich"
pga_sim_type = "pga"
traditional = "traditional"
with_flash = "mev"


class RunSimulationSerializer(serializers.Serializer):

    sim_type = serializers.ChoiceField(
        choices=[
            [displacement_sim_type, "Displacement"],
            [sandwich_sim_type, "Sandwich"],
            [pga_sim_type, "Priority Gas Auction (Ganache)"],
        ]
    )
    execution_type = serializers.ChoiceField(
        choices=[[traditional, "Traditional"], [with_flash, "Flashbots Auction/MEV-geth"]]
    )

    def validate(self, data):
        # Make sure experiment not running:
        try:
            experiment = ExperimentLog.objects.latest("initiate_time")
            # Allow if experiment finished or it's been at least 3 mins as something must have gone wrong
            if not experiment.finished and timezone.now() - experiment.initiate_time < timedelta(
                minutes=3
            ):
                raise serializers.ValidationError(
                    "An experiment is already running! Try again in a few minutes."
                )
        except ExperimentLog.DoesNotExist:
            pass

        if data["sim_type"] == pga_sim_type and data["execution_type"] == with_flash:
            raise serializers.ValidationError(
                "PGA can only be run traditionally. With MEV-geth, parties have no visibility into the other's transactions before they're mined."
            )

        return data

    def save(self):

        if self.validated_data["sim_type"] == displacement_sim_type:
            if self.validated_data["execution_type"] == traditional:
                run_displacement_task.delay(False)
            else:
                run_displacement_task.delay(True)
        elif self.validated_data["sim_type"] == sandwich_sim_type:
            if self.validated_data["execution_type"] == traditional:
                run_sandwich_task.delay(False)
            else:
                run_sandwich_task.delay(True)
        elif self.validated_data["sim_type"] == pga_sim_type:
            run_pga_task.delay(False)
        else:
            raise Exception()
