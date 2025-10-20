from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Notification(models.Model):
    KIND_CHOICES = [
        ("payment", "Payment"),
        ("message", "Message"),
        ("scrimmage", "Scrimmage"),
        ("event", "Event"),
        ("system", "System"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default="system")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.kind}] {self.title}"
