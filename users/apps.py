from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"

# Ensure Profile Auto-Creation Works
def ready(self):
        from . import signals