# from unavailable.overrides import admin
from django.contrib import admin

from backend.tx.models import DbTx


@admin.register(DbTx)
class DbTxAdmin(admin.ModelAdmin):
    list_display = ["pk", "account_address", "chain_id", "status", "gas_speed", "last_sent"]
