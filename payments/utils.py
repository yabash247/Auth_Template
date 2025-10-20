# payments/utils.py
from decimal import Decimal
from django.utils import timezone
from .models import PaymentTransaction, CreditWallet
from notifications.models import Notification

from django.db import transaction as db_txn
import stripe
from django.conf import settings

from .models import PaymentTransaction, CreditWallet, CreditTransaction, BonusTier, OrganizerFee
from notifications.models import Notification

def process_auto_payment(user, amount, app_source, related_id, description="Auto payment"):
    """
    Attempt to auto-deduct credits. If insufficient, create a pending payment intent.
    Returns a dict describing what happened.
    """
    try:
        wallet, _ = CreditWallet.objects.get_or_create(user=user)
        if wallet.balance >= amount:
            # Deduct directly
            wallet.withdraw(amount, purpose=app_source)
            PaymentTransaction.objects.create(
                user=user,
                app_source=app_source,
                related_id=str(related_id),
                amount=amount,
                currency="USD",
                provider="credits",
                method="credits",
                status="succeeded",
                description=description,
                processed_at=timezone.now(),
            )
            Notification.objects.create(
                user=user,
                kind="payment",
                title=f"{app_source.title()} paid via credits",
                body=f"{amount} credits deducted automatically for {app_source}.",
            )
            return {"status": "paid", "method": "credits"}
        else:
            # Not enough balance, create payment intent
            txn = PaymentTransaction.objects.create(
                user=user,
                app_source=app_source,
                related_id=str(related_id),
                amount=amount,
                currency="USD",
                provider="stripe",
                method="card",
                status="pending",
                description=description,
            )
            Notification.objects.create(
                user=user,
                kind="payment",
                title=f"{app_source.title()} payment pending",
                body=f"Payment intent created for {amount} USD. Complete payment to confirm.",
            )
            return {"status": "pending", "transaction_id": str(txn.id)}
    except Exception as e:
        print(f"[AutoPay Error] {e}")
        Notification.objects.create(
            user=user,
            kind="payment",
            title="Auto-payment error",
            body=f"Payment could not be processed automatically: {e}",
        )
        return {"status": "error", "detail": str(e)}


def _apply_bonus(amount: Decimal) -> Decimal:
    tier = (BonusTier.objects
            .filter(active=True, min_amount__lte=amount)
            .order_by("-min_amount")
            .first())
    if not tier:
        return Decimal("0")
    bonus = (amount * (tier.bonus_percent / Decimal("100"))).quantize(Decimal("0.01"))
    return bonus

def process_topup_with_bonus(user, amount: Decimal, source="topup"):
    """Top up wallet and apply the highest matching bonus tier."""
    wallet, _ = CreditWallet.objects.get_or_create(user=user)
    bonus = _apply_bonus(amount)
    wallet.deposit(amount, source=source)
    if bonus > 0:
        wallet.deposit(bonus, source=f"bonus:{source}")
    return {"credited": str(amount), "bonus": str(bonus), "balance": str(wallet.balance)}

def process_auto_payment(user, amount: Decimal, app_source, related_id, description="Auto payment",
                         organizer=None, organizer_fee_percent: Decimal = Decimal("0"),
                         organizer_fee_flat: Decimal = Decimal("0"),
                         team_pay=False, charge_account=None):
    """
    Auto-deduct from wallet if possible; otherwise create pending card intent (stored as transaction).
    If team_pay=True, charge 'charge_account' user instead (typically organizer).
    For CREDIT payments, organizer fee is credited immediately.
    For CARD intents, organizer fee is recorded as pending OrganizerFee to be settled later.
    """
    payer = charge_account if (team_pay and charge_account) else user
    wallet, _ = CreditWallet.objects.get_or_create(user=payer)

    # compute optional organizer fee
    organizer_fee = Decimal("0")
    if organizer:
        percent_cut = (amount * (organizer_fee_percent / Decimal("100"))).quantize(Decimal("0.01"))
        organizer_fee = max(percent_cut, organizer_fee_flat)

    try:
        if wallet.balance >= amount:  # pay with credits
            with db_txn.atomic():
                wallet.withdraw(amount, purpose=app_source)
                PaymentTransaction.objects.create(
                    user=payer,
                    app_source=app_source,
                    related_id=str(related_id),
                    amount=amount,
                    currency="USD",
                    provider="credits",
                    method="credits",
                    status="succeeded",
                    description=description,
                    processed_at=timezone.now(),
                )
                # credit organizer immediately (net fee), if any
                if organizer and organizer_fee > 0:
                    o_wallet, _ = CreditWallet.objects.get_or_create(user=organizer)
                    o_wallet.deposit(organizer_fee, source=f"organizer_fee:{app_source}")
                    OrganizerFee.objects.create(
                        organizer=organizer, app_source=app_source,
                        related_id=str(related_id), amount=organizer_fee, status="succeeded"
                    )
            Notification.objects.create(
                user=payer,
                kind="payment",
                title=f"{app_source.title()} paid via credits",
                body=f"{amount} credits deducted automatically.",
            )
            if organizer and organizer_fee > 0:
                Notification.objects.create(
                    user=organizer,
                    kind="payment",
                    title="Organizer fee received",
                    body=f"You earned {organizer_fee} credits from a {app_source}.",
                )
            return {"status": "paid", "method": "credits", "organizer_fee": str(organizer_fee)}
        else:
            # create pending card intent (no external call here; you can attach Stripe PI separately)
            txn = PaymentTransaction.objects.create(
                user=payer,
                app_source=app_source,
                related_id=str(related_id),
                amount=amount,
                currency="USD",
                provider="stripe",
                method="card",
                status="pending",
                description=description,
            )
            # record pending organizer fee to settle on success
            if organizer and organizer_fee > 0:
                OrganizerFee.objects.create(
                    organizer=organizer, app_source=app_source,
                    related_id=str(related_id), amount=organizer_fee, status="pending"
                )
            Notification.objects.create(
                user=payer,
                kind="payment",
                title=f"{app_source.title()} payment pending",
                body=f"Payment intent created for {amount} USD. Complete payment to confirm.",
            )
            return {"status": "pending", "transaction_id": str(txn.id), "organizer_fee_pending": str(organizer_fee)}
    except Exception as e:
        Notification.objects.create(
            user=payer, kind="payment",
            title="Auto-payment error",
            body=f"Payment could not be processed automatically: {e}",
        )
        return {"status": "error", "detail": str(e)}

def settle_organizer_fees_on_success(app_source: str, related_id: str):
    """Call from Stripe/PayPal webhooks after successful capture for card payments."""
    for fee in OrganizerFee.objects.filter(app_source=app_source, related_id=str(related_id), status="pending"):
        w, _ = CreditWallet.objects.get_or_create(user=fee.organizer)
        w.deposit(fee.amount, source=f"organizer_fee:{app_source}")
        fee.status = "succeeded"
        fee.save(update_fields=["status"])

def refund_transaction_credits(txn: PaymentTransaction, reason="refund"):
    """Refund a credits-based transaction."""
    wallet, _ = CreditWallet.objects.get_or_create(user=txn.user)
    wallet.deposit(txn.amount, source=f"refund:{reason}")
    txn.status = "refunded"
    txn.processed_at = timezone.now()
    txn.save(update_fields=["status", "processed_at"])
    Notification.objects.create(
        user=txn.user, kind="payment",
        title="Refund issued", body=f"{txn.amount} credits refunded ({reason})."
    )

def refund_transaction_stripe(txn: PaymentTransaction, reason="requested_by_customer"):
    """Attempt a Stripe refund using provider_ref (Stripe charge/PI/invoice id)."""
    stripe.api_key = settings.STRIPE_API_KEY
    try:
        # This assumes provider_ref is a charge or payment_intent (adjust as needed).
        stripe.Refund.create(payment_intent=txn.provider_ref, reason=reason)
        txn.status = "refunded"
        txn.processed_at = timezone.now()
        txn.save(update_fields=["status", "processed_at"])
        Notification.objects.create(
            user=txn.user, kind="payment",
            title="Refund issued", body=f"${txn.amount} refund initiated to your card."
        )
        return True
    except Exception as e:
        Notification.objects.create(
            user=txn.user, kind="payment",
            title="Refund failed", body=f"We could not process your refund automatically. {e}"
        )
        return False

def bulk_refund(app_source: str, related_id: str):
    """Refund all succeeded/pending transactions for an object (scrimmage/event). Credits via wallet; Stripe via API."""
    txns = PaymentTransaction.objects.filter(app_source=app_source, related_id=str(related_id),
                                             status__in=["succeeded", "pending"])
    results = []
    for t in txns:
        if t.provider == "credits" and t.status == "succeeded":
            refund_transaction_credits(t, reason=f"{app_source}_cancelled")
            results.append((t.id, "credits", "refunded"))
        elif t.provider == "stripe" and t.status in ["succeeded", "pending"] and t.provider_ref:
            ok = refund_transaction_stripe(t)
            results.append((t.id, "stripe", "refunded" if ok else "failed"))
    return results

def distribute_prize_pool(organizer, app_source: str, related_id: str, payouts: list[dict]):
    """
    payouts = [{"user_id": 1, "amount": "25.00"}, ...]
    Deposits credits into winners' wallets and records transactions.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    for p in payouts:
        winner = User.objects.filter(id=p["user_id"]).first()
        if not winner:
            continue
        amt = Decimal(str(p["amount"]))
        w, _ = CreditWallet.objects.get_or_create(user=winner)
        w.deposit(amt, source=f"prize:{app_source}")
        PaymentTransaction.objects.create(
            user=winner, app_source=app_source, related_id=str(related_id),
            amount=amt, currency="USD", provider="credits", method="credits",
            status="succeeded", description="Prize payout", processed_at=timezone.now()
        )
        Notification.objects.create(
            user=winner, kind="payment",
            title="Prize received", body=f"You received {amt} credits from {app_source}."
        )


def process_coin_payment(user, item_price_usd, discount_percent=5):
    wallet = user.wallet
    discounted = item_price_usd * (Decimal(100 - discount_percent) / 100)
    required_coins = discounted  # 1 Coin = 1 USD pegged
    if wallet.balance < required_coins:
        raise ValueError("Not enough coins")

    wallet.spend(required_coins, reason="membership_payment")
    return {
        "paid": required_coins,
        "discount_applied": discount_percent,
        "remaining_balance": wallet.balance
    }

def convert_to_fiat(user, coins):
    """Convert locked-in coin value to fiat based on purchase rate."""
    purchases = user.coin_purchases.order_by("-created_at")
    remaining = Decimal(coins)
    total_usd = Decimal(0)

    for p in purchases:
        if remaining <= 0:
            break
        chunk = min(remaining, p.coin_amount)
        total_usd += chunk * p.exchange_rate
        remaining -= chunk

    return total_usd
