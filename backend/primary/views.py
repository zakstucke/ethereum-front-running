import asyncio

from django.conf import settings as base_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.user import permissions

from backend.asyncio_utils import async_runner, thread_wrapper
from backend.primary.serializers_write import RunSimulationSerializer
from backend.primary.sims import get_balances
from backend.tx.serializers_read import DbTxSerializer
from backend.tx.models import DbTx


UserModel = get_user_model()


@thread_wrapper
async def test_async():
    await asyncio.sleep(1)

    return timezone.now().strftime("%H:%M:%S")


class GetTxs(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, format=None):
        data = {"accepted": True, "txs": []}

        # Return the most 30 objects:
        objs = DbTx.objects.all().order_by("-pk")
        for obj in objs[:30]:
            data["txs"].append(DbTxSerializer(obj).data)

        return Response(data, status=status.HTTP_200_OK)


class RunSimulation(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, format=None):
        serializer = RunSimulationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"accepted": True, "response": "Initiated!"}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"accepted": False, "errors": serializer.errors}, status=status.HTTP_200_OK
            )


class GetBalances(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, format=None):

        balance_graph = {
            "type": base_settings.SAFE_SHARED_CONFIG["GRAPH_TYPES"]["SCATTER"],
            "config": {
                "data": async_runner(get_balances()),
                "title": "Account Balances (Last Hour)",
                "xLabel": "Time",
                "xDataType": "utc",
                "yLabel": "Balance",
                "lines": True,
                "lineType": "straight",
                "dataLabels": ["Agent", "Attacker"],
                "colors": ["#198754", "#ff0000"],
            },
        }

        return Response(
            {
                "accepted": True,
                "data": [balance_graph],
            }
        )
