# from unavailable.overrides import admin

from backend.primary.models import ExperimentLog


@admin.register(ExperimentLog)
class ExperimentLogAdmin(admin.ModelAdmin):
    list_display = ["pk", "name", "initiate_time"]
