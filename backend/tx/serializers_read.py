from web3 import Web3
from rest_framework import serializers

from django.contrib.auth import get_user_model

UserModel = get_user_model()


class DbTxSerializer(serializers.Serializer):
    pk = serializers.IntegerField()

    experiment_pk = serializers.SerializerMethodField()
    experiment_finished = serializers.SerializerMethodField()
    experiment_agent_balance_change = serializers.SerializerMethodField()
    experiment_attacker_balance_change = serializers.SerializerMethodField()

    description = serializers.CharField()
    experiment = serializers.CharField()

    priority_gas = serializers.SerializerMethodField()

    node_url = serializers.CharField()
    node_url = serializers.CharField()
    chain_id = serializers.IntegerField()
    account_address = serializers.CharField()
    status = serializers.CharField()
    gas_speed = serializers.CharField()
    data = serializers.JSONField()
    hash = serializers.CharField()
    receipt = serializers.JSONField()
    last_sent = serializers.DateTimeField()

    def get_priority_gas(self, tx_obj):
        if "maxPriorityFeePerGas" in tx_obj.data:
            gas = Web3.fromWei(tx_obj.data["maxPriorityFeePerGas"], "gwei")
        else:
            gas = 0

        return "{:.2f} Gwei".format(gas)

    def get_experiment_pk(self, tx_obj):
        if tx_obj.experiment:
            return tx_obj.experiment.pk
        return 0

    def get_experiment_finished(self, tx_obj):
        if tx_obj.experiment:
            return tx_obj.experiment.finished
        return False

    def get_experiment_agent_balance_change(self, tx_obj):
        if tx_obj.experiment:
            return tx_obj.experiment.agent_balance_change
        return 0

    def get_experiment_attacker_balance_change(self, tx_obj):
        if tx_obj.experiment:
            return tx_obj.experiment.attacker_balance_change
        return 0
