from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class MembershipPlan(models.Model):
    INTERVAL_CHOICES = [("month", "Monthly"), ("year", "Yearly")]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, default="month")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.interval})"


class Membership(models.Model):
    STATUS = [
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("inactive", "Inactive"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    plan = models.ForeignKey(MembershipPlan, on_delete=models.CASCADE, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS, default="active")
    started_at = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    next_due_date = models.DateTimeField(null=True, blank=True)
    next_due_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    auto_renew = models.BooleanField(default=True)
    external_ref = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.user} - {self.plan.name}"


class Payment(models.Model):
    STATUS = [("succeeded", "Succeeded"), ("failed", "Failed"), ("pending", "Pending")]
    METHOD = [("card", "Card"), ("wallet", "Wallet")]
    PROVIDER = [("stripe", "Stripe"), ("paypal", "PayPal")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    membership = models.ForeignKey(Membership, null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    method = models.CharField(max_length=20, choices=METHOD, default="card")
    provider = models.CharField(max_length=20, choices=PROVIDER, default="stripe")
    provider_ref = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- NEW cross-app links (nullable) ---
    event = models.ForeignKey("events.Event", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    league = models.ForeignKey("leagues.League", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    scrimmage = models.ForeignKey("scrimmages.Scrimmage", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.provider} ({self.status})"


