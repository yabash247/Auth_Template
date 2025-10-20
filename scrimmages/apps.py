# scrimmages/apps.py
from django.apps import AppConfig

class ScrimmagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scrimmages"

    def ready(self):
        # register signals
        from . import signals  # noqa
