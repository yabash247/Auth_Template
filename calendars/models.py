from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class CalendarItem(models.Model):
    KIND_CHOICES = [("event", "Event"), ("personal", "Personal")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="calendar_items")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="personal")
    title = models.CharField(max_length=255)
    start = models.DateTimeField()
    end = models.DateTimeField()
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start"]

    def __str__(self):
        return f"{self.title} ({self.start:%Y-%m-%d})"
