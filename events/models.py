from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Event(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="events")
    group = models.ForeignKey("groups.Group", null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    location_name = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=512, blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    is_public = models.BooleanField(default=True)
    tags = models.JSONField(default=list, blank=True)
    entry_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    auto_pay_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    organizer_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    organizer_fee_flat = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=[("draft","Draft"),("published","Published"),("cancelled","Cancelled")], default="published")

    class Meta:
        ordering = ["start"]

    def __str__(self):
        return f"{self.title} ({self.start:%Y-%m-%d})"


class RSVP(models.Model):
    STATUS_CHOICES = [
        ("interested", "Interested"),
        ("going", "Going"),
        ("checked_in", "Checked In"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_rsvps"
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="rsvps"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="interested")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "event")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} → {self.event.title} ({self.status})"
