from backend.overrides import admin

from backend.tx.models import DbTx


@admin.register(DbTx)
class DbTxAdmin(admin.ModelAdmin):
    list_display = ["pk", "account_address", "chain_id", "status", "gas_speed", "last_sent"]
