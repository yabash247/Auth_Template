from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid

User = settings.AUTH_USER_MODEL


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]
    PROVIDER_CHOICES = [
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("credits", "Credits"),
    ]
    METHOD_CHOICES = [
        ("card", "Card"),
        ("wallet", "Wallet"),
        ("credits", "Credits"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payment_transactions")
    app_source = models.CharField(max_length=50, blank=True)  # e.g. 'membership', 'scrimmages', 'events'
    related_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="card")
    provider_ref = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.app_source or 'general'} ({self.status})"


class CreditWallet(models.Model):
    """
    A simple token-based wallet system for users (like Fortnite V-Bucks).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.balance:.2f} credits"

    def deposit(self, amount: float, source="topup"):
        self.balance += amount
        self.save(update_fields=["balance"])
        CreditTransaction.objects.create(
            user=self.user, amount=amount, transaction_type="credit",
            source=source, balance_after=self.balance
        )

    def withdraw(self, amount: float, purpose="purchase"):
        if self.balance < amount:
            raise ValueError("Insufficient credits")
        self.balance -= amount
        self.save(update_fields=["balance"])
        CreditTransaction.objects.create(
            user=self.user, amount=amount, transaction_type="debit",
            source=purpose, balance_after=self.balance
        )


class CreditTransaction(models.Model):
    TRANSACTION_TYPE = [("credit", "Credit"), ("debit", "Debit")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="credit_transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    source = models.CharField(max_length=100, default="system")
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} {self.transaction_type} {self.amount} ({self.source})"



class BonusTier(models.Model):
    """Wallet bonus tiers: add bonus % on topups above a threshold."""
    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    bonus_percent = models.DecimalField(max_digits=5, decimal_places=2, help_text="e.g. 5.00 = +5%")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["min_amount"]

    def __str__(self):
        return f"≥ {self.min_amount} → +{self.bonus_percent}%"

class OrganizerFee(models.Model):
    """Track organizer earnings (created immediately for credit payments; can be pending for card)."""
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="organizer_fees")
    app_source = models.CharField(max_length=50)        # 'scrimmage' | 'event'
    related_id = models.CharField(max_length=100)       # id of scrimmage/event
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default="succeeded")  # 'succeeded' | 'pending'
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organizer} {self.app_source} {self.related_id} +{self.amount} ({self.status})"





class CoinPurchase(models.Model):
    """Tracks purchase and conversion rate at time of buying ProjectCoins."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coin_purchases")
    amount_fiat = models.DecimalField(max_digits=12, decimal_places=2)
    coin_amount = models.DecimalField(max_digits=12, decimal_places=2)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6)  # 1 coin = ? USD
    currency = models.CharField(max_length=10, default="USD")
    provider = models.CharField(max_length=20, default="stripe")  # or paypal
    transaction_ref = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.email} bought {self.coin_amount} Coins @ {self.exchange_rate} {self.currency}/coin"


class CreditWallet(models.Model):
    """Existing Wallet upgraded to handle Coins."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # in Coins
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def deposit(self, coins, reason="purchase"):
        self.balance += Decimal(coins)
        self.total_earned += Decimal(coins)
        self.save(update_fields=["balance", "total_earned", "last_updated"])
        return self.balance

    def spend(self, coins, reason="payment"):
        if self.balance < Decimal(coins):
            raise ValueError("Insufficient balance")
        self.balance -= Decimal(coins)
        self.total_spent += Decimal(coins)
        self.save(update_fields=["balance", "total_spent", "last_updated"])
        return self.balance

class PaymentLink(models.Model):
    scrimmage = models.ForeignKey("scrimmages.Scrimmage", on_delete=models.CASCADE, related_name="payment_links")
    wallet = models.ForeignKey("payments.CreditWallet", on_delete=models.CASCADE, related_name="scrimmage_links")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=[("pending","Pending"),("paid","Paid"),("refunded","Refunded")], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
