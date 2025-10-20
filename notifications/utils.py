# notifications/utils.py
from django.contrib.auth import get_user_model
from notifications.models import Notification
from django.utils import timezone

User = get_user_model()

def notify_admins(title: str, body: str):
    admins = User.objects.filter(is_staff=True, is_active=True)
    for admin in admins:
        Notification.objects.create(
            user=admin,
            title=title,
            message=body,
            created_at=timezone.now()
        )
