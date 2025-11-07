# payments/views_transactions.py
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.conf import settings
from decimal import Decimal
from .models import PaymentTransaction, CreditWallet, CreditTransaction
from .serializers import (
    PaymentTransactionSerializer,
    CreditWalletSerializer,
    CreditTransactionSerializer
)
from notifications.models import Notification

# payments/views_transactions.py  (append new actions)
from rest_framework.decorators import action
from .utils import (
    process_topup_with_bonus, bulk_refund, distribute_prize_pool
)
from decimal import Decimal


class PaymentTransactionViewSet(viewsets.ModelViewSet):
    """
    Handles general payment operations and custom on-demand charges.
    """
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PaymentTransaction.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def create_intent(self, request):
        """
        Create an on-demand one-time payment intent.
        Example use: scrimmage entry, event ticket, donation.
        """
        user = request.user
        amount = Decimal(request.data.get("amount", "0"))
        currency = request.data.get("currency", "USD").upper()
        description = request.data.get("description", "")
        app_source = request.data.get("app_source", "general")
        related_id = request.data.get("related_id", "")

        if amount <= 0:
            return Response({"detail": "Invalid amount"}, status=400)

        txn = PaymentTransaction.objects.create(
            user=user,
            app_source=app_source,
            related_id=related_id,
            amount=amount,
            currency=currency,
            provider="stripe",  # default provider for simplicity
            method="card",
            status="pending",
            description=description
        )

        Notification.objects.create(
            user=user,
            kind="payment",
            title="Payment intent created",
            body=f"A new payment intent for {amount} {currency} has been created.",
        )
        return Response(PaymentTransactionSerializer(txn).data, status=201)
    
    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def refund_group(self, request):
        """
        Admin: refund all transactions linked to a scrimmage/event.
        body: { "app_source": "scrimmage"|"event", "related_id": "<id>" }
        """
        app_source = request.data.get("app_source")
        related_id = request.data.get("related_id")
        if app_source not in ["scrimmage", "event"] or not related_id:
            return Response({"detail": "Invalid payload"}, status=400)
        results = bulk_refund(app_source, related_id)
        return Response({"results": results})

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def prize_payouts(self, request):
        """
        Admin/Organizer: distribute prize pool.
        body: { "app_source": "scrimmage"|"event", "related_id": "<id>", "payouts":[{"user_id":1,"amount":"25.00"}, ...] }
        """
        app_source = request.data.get("app_source")
        related_id = request.data.get("related_id")
        payouts = request.data.get("payouts", [])
        distribute_prize_pool(request.user, app_source, related_id, payouts)
        return Response({"detail": "Payouts distributed"})



class CreditWalletViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_wallet(self, user):
        wallet, _ = CreditWallet.objects.get_or_create(user=user)
        return wallet

    @action(detail=False, methods=["get"])
    def balance(self, request):
        wallet = self.get_wallet(request.user)
        return Response(CreditWalletSerializer(wallet).data)

    @action(detail=False, methods=["post"])
    def topup(self, request):
        """
        Add credits to the user's wallet (simulate Stripe/PayPal purchase).
        """
        user = request.user
        amount = Decimal(request.data.get("amount", "0"))
        if amount <= 0:
            return Response({"detail": "Invalid amount"}, status=400)

        wallet = self.get_wallet(user)
        wallet.deposit(amount, source="topup")

        Notification.objects.create(
            user=user,
            kind="payment",
            title="Credits added",
            body=f"{amount} credits have been added to your wallet."
        )
        return Response({"balance": str(wallet.balance)})

    @action(detail=False, methods=["post"])
    def spend(self, request):
        """
        Spend credits for purchases (scrimmages, tickets, etc.)
        """
        user = request.user
        amount = Decimal(request.data.get("amount", "0"))
        purpose = request.data.get("purpose", "purchase")

        wallet = self.get_wallet(user)
        try:
            wallet.withdraw(amount, purpose=purpose)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        Notification.objects.create(
            user=user,
            kind="payment",
            title="Credits spent",
            body=f"You spent {amount} credits for {purpose}."
        )
        return Response({"balance": str(wallet.balance)})

    @action(detail=False, methods=["get"])
    def history(self, request):
        txns = CreditTransaction.objects.filter(user=request.user).order_by("-created_at")
        return Response(CreditTransactionSerializer(txns, many=True).data)
    
    @action(detail=False, methods=["post"])
    def topup_with_bonus(self, request):
        amount = Decimal(request.data.get("amount", "0"))
        if amount <= 0:
            return Response({"detail": "Invalid amount"}, status=400)
        result = process_topup_with_bonus(request.user, amount)
        return Response(result, status=200)

    # 🟩 Add after topup_with_bonus()
    @action(detail=False, methods=["post"])
    def add_credits(self, request):
        """
        Add fiat-purchased credits to wallet (after payment confirmation).
        body: { "amount": "20.00", "provider": "stripe", "reference": "pi_12345" }
        """
        from .utils import add_credits
        amount = Decimal(request.data.get("amount", "0"))
        provider = request.data.get("provider", "stripe")
        reference = request.data.get("reference")
        if amount <= 0:
            return Response({"detail": "Invalid amount"}, status=400)
        result = add_credits(request.user, amount, provider, reference)
        return Response(result, status=200)

    @action(detail=False, methods=["post"])
    def withdraw_credits(self, request):
        """
        Request fiat withdrawal from wallet.
        body: { "amount": "50.00", "provider": "paypal" }
        """
        from .utils import withdraw_credits
        amount = Decimal(request.data.get("amount", "0"))
        provider = request.data.get("provider", "paypal")
        if amount <= 0:
            return Response({"detail": "Invalid amount"}, status=400)
        try:
            result = withdraw_credits(request.user, amount, provider)
            return Response(result, status=200)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)


import stripe
from rest_framework.views import APIView

class BuyCoinsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        stripe.api_key = settings.STRIPE_API_KEY
        amount_usd = request.data.get("amount", 0)
        if not amount_usd or float(amount_usd) <= 0:
            return Response({"detail": "Invalid amount"}, status=400)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"ProjectCoins ({amount_usd} USD worth)"},
                    "unit_amount": int(float(amount_usd) * 100),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{settings.FRONTEND_URL}/wallet/success",
            cancel_url=f"{settings.FRONTEND_URL}/wallet/cancel",
            metadata={
                "user_id": str(request.user.id),
                "purpose": "coin_purchase",
            },
        )
        return Response({"checkout_url": session.url})
