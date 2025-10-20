# payments/views_webhooks.py
import json, stripe, requests
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import PaymentTransaction, CoinPurchase, CreditWallet
from notifications.models import Notification
from membership.models import Membership, MembershipPlan
from membership.views import extend_period
from decimal import Decimal

# 🔹 Stripe Webhook
class StripeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        stripe.api_key = settings.STRIPE_API_KEY
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except Exception as e:
            return Response({"detail": f"Invalid Stripe payload: {e}"}, status=400)

        event_type = event.get("type", "")
        data = event["data"]["object"]
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_id = metadata.get("plan_id")

        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(id=user_id).first() if user_id else None
        plan = MembershipPlan.objects.filter(id=plan_id).first() if plan_id else None

        provider_ref = data.get("id") or data.get("payment_intent") or data.get("invoice")

        if event_type in ("checkout.session.completed", "payment_intent.succeeded", "invoice.paid"):
            PaymentTransaction.objects.create(
                user=user, app_source="membership",
                related_id=str(plan_id),
                amount=plan.price if plan else 0,
                currency=plan.currency if plan else "USD",
                provider="stripe", method="card",
                provider_ref=provider_ref, status="succeeded",
                processed_at=timezone.now()
            )

            if user and plan:
                membership = (
                    Membership.objects.filter(user=user, plan=plan).order_by("-started_at").first()
                    or Membership.objects.create(
                        user=user, plan=plan, status="active",
                        started_at=timezone.now(), current_period_end=timezone.now()
                    )
                )
                extend_period(membership)
                Notification.objects.create(
                    user=user, kind="payment",
                    title="Stripe payment successful",
                    body=f"Your {plan.name} plan was renewed successfully.",
                    url="/memberships"
                )

        elif event_type in ("invoice.payment_failed", "payment_intent.payment_failed"):
            if user:
                PaymentTransaction.objects.create(
                    user=user, app_source="membership", related_id=str(plan_id),
                    amount=(data.get("amount_due") or 0) / 100,
                    currency=(data.get("currency") or "USD").upper(),
                    provider="stripe", method="card",
                    provider_ref=provider_ref, status="failed"
                )
                Notification.objects.create(
                    user=user, kind="payment",
                    title="Stripe payment failed",
                    body="Your payment could not be processed. Please update billing info.",
                    url="/billing"
                )

        # Handle Coin Purchases
        if event["type"] in ("checkout.session.completed", "payment_intent.succeeded"):
            data = event["data"]["object"]
            metadata = data.get("metadata", {})
            user_id = metadata.get("user_id")
            purpose = metadata.get("purpose")  # 'coin_purchase' or 'membership_payment'

            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(id=user_id).first()

            if not user:
                return Response({"detail": "User not found"}, status=400)

            amount_usd = Decimal(data["amount_total"]) / 100
            currency = data.get("currency", "usd").upper()
            rate = Decimal(1)  # 1 USD = 1 Coin (static peg)

            if purpose == "coin_purchase":
                coins = amount_usd / rate
                cp = CoinPurchase.objects.create(
                    user=user,
                    amount_fiat=amount_usd,
                    coin_amount=coins,
                    exchange_rate=rate,
                    currency=currency,
                    provider="stripe",
                    transaction_ref=data.get("id"),
                )

                wallet, _ = CreditWallet.objects.get_or_create(user=user)
                wallet.deposit(coins, reason="purchase_coin")

                Notification.objects.create(
                    user=user,
                    kind="wallet",
                    title="Coin Purchase Successful",
                    body=f"You purchased {coins} ProjectCoins worth {amount_usd} {currency}.",
                    url="/wallet",
                )


        return Response({"received": True})
