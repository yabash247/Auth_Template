# payments/views_webhooks_paypal.py
import json, requests
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import PaymentTransaction
from notifications.models import Notification
from membership.models import Membership, MembershipPlan
from membership.views import extend_period


def verify_paypal_signature(request_body, headers):
    verify_url = (
        "https://api-m.paypal.com/v1/notifications/verify-webhook-signature"
        if settings.PAYPAL_ENVIRONMENT == "live"
        else "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature"
    )
    payload = {
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO"),
        "cert_url": headers.get("PAYPAL-CERT-URL"),
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"),
        "webhook_id": settings.PAYPAL_WEBHOOK_ID,
        "webhook_event": json.loads(request_body),
    }
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET)
    response = requests.post(verify_url, json=payload, auth=auth)
    return response.json().get("verification_status") == "SUCCESS"


class PayPalWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        body = request.body.decode("utf-8")
        if not verify_paypal_signature(body, request.headers):
            return Response({"detail": "Invalid webhook signature"}, status=400)

        data = json.loads(body or "{}")
        event_type = data.get("event_type")
        resource = data.get("resource", {})

        custom_id = resource.get("custom_id") or resource.get("billing_agreement_id", "")
        user_id, _, plan_id = custom_id.partition(":")
        provider_ref = resource.get("id") or resource.get("sale_id")
        amount_data = resource.get("amount", {})
        amount = amount_data.get("value") or amount_data.get("total") or 0
        currency = amount_data.get("currency_code") or "USD"

        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(id=user_id).first() if user_id else None
        plan = MembershipPlan.objects.filter(id=plan_id).first() if plan_id else None

        if event_type in ("PAYMENT.SALE.COMPLETED", "BILLING.SUBSCRIPTION.RENEWED"):
            PaymentTransaction.objects.create(
                user=user, app_source="membership", related_id=str(plan_id),
                amount=amount, currency=currency,
                provider="paypal", method="wallet",
                provider_ref=provider_ref, status="succeeded",
                processed_at=timezone.now()
            )
            if user and plan:
                membership = (
                    Membership.objects.filter(user=user, plan=plan).order_by("-started_at").first()
                    or Membership.objects.create(
                        user=user, plan=plan, status="active", started_at=timezone.now(),
                        current_period_end=timezone.now()
                    )
                )
                extend_period(membership)
                Notification.objects.create(
                    user=user, kind="payment",
                    title="PayPal payment successful",
                    body=f"Your {plan.name} plan was renewed successfully via PayPal.",
                    url="/memberships"
                )

        elif event_type in ("PAYMENT.SALE.DENIED", "BILLING.SUBSCRIPTION.SUSPENDED"):
            if user:
                Notification.objects.create(
                    user=user, kind="payment",
                    title="PayPal payment issue",
                    body="Your subscription payment failed or was suspended.",
                    url="/billing"
                )

        return Response({"received": True})
