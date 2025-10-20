# payments/views_test_webhook.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
from .models import PaymentTransaction
from notifications.models import Notification
from membership.models import Membership, MembershipPlan
from membership.views import extend_period

class TestWebhookView(APIView):
    """
    Simulate Stripe/PayPal webhook for local dev without external calls.
    Accessible only to superusers or staff.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        user = request.user
        provider = request.data.get("provider", "stripe")
        plan_id = request.data.get("plan_id")
        plan = MembershipPlan.objects.filter(id=plan_id).first()
        amount = plan.price if plan else 10.00

        PaymentTransaction.objects.create(
            user=user, app_source="membership", related_id=str(plan_id),
            amount=amount, currency="USD", provider=provider,
            method="card", provider_ref="TEST12345", status="succeeded",
            processed_at=timezone.now()
        )

        if plan:
            membership = (
                Membership.objects.filter(user=user, plan=plan).first()
                or Membership.objects.create(user=user, plan=plan, status="active", started_at=timezone.now())
            )
            extend_period(membership)

        Notification.objects.create(
            user=user,
            kind="payment",
            title="Test Payment Success",
            body=f"Simulated {provider.capitalize()} payment for {plan.name if plan else 'Test Plan'}.",
            url="/memberships"
        )

        return Response({"detail": f"Test {provider} payment simulated for user {user.email}."})
