from itertools import chain
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    CreditTransaction,
    CreditWalletTransaction,
    CoinPurchase,
    PaymentTransaction,
)
from .serializers import TransactionHistorySerializer


class TransactionHistoryViewSet(viewsets.ViewSet):
    """
    Unified transaction history for a user across all payment systems:
    - Credit transactions (spend / earn)
    - Fiat deposits & withdrawals
    - Coin purchases
    - App-based payments (scrimmages, events, memberships)
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user

        # 1️⃣ Credit Transactions (internal credit-based ledger)
        credit_txns = [
            {
                "id": f"credit-{t.id}",
                "type": "credit" if t.transaction_type == "credit" else "debit",
                "amount": t.amount,
                "currency": "CREDITS",
                "status": "succeeded",
                "source": t.source,
                "description": f"{t.transaction_type.title()} from {t.source}",
                "created_at": t.created_at,
            }
            for t in CreditTransaction.objects.filter(user=user)
        ]

        # 2️⃣ Wallet (Fiat Deposits / Withdrawals)
        wallet_txns = [
            {
                "id": f"wallet-{t.id}",
                "type": t.type,
                "amount": t.amount,
                "currency": "USD",
                "status": t.status,
                "source": t.provider,
                "description": f"Wallet {t.type.title()} via {t.provider}",
                "created_at": t.created_at,
            }
            for t in CreditWalletTransaction.objects.filter(user=user)
        ]

        # 3️⃣ Coin Purchases
        coin_txns = [
            {
                "id": f"coin-{t.id}",
                "type": "purchase",
                "amount": t.coin_amount,
                "currency": t.currency,
                "status": "succeeded",
                "source": t.provider,
                "description": f"Purchased {t.coin_amount} ProjectCoins",
                "created_at": t.created_at,
            }
            for t in CoinPurchase.objects.filter(user=user)
        ]

        # 4️⃣ Payment Transactions (Scrimmages, Events, Memberships)
        payment_txns = [
            {
                "id": f"payment-{t.id}",
                "type": t.app_source,
                "amount": t.amount,
                "currency": t.currency,
                "status": t.status,
                "source": t.provider,
                "description": f"{t.app_source.title()} payment ({t.method})",
                "created_at": t.created_at,
            }
            for t in PaymentTransaction.objects.filter(user=user)
        ]

        # 5️⃣ Combine all and sort chronologically
        combined = sorted(
            chain(credit_txns, wallet_txns, coin_txns, payment_txns),
            key=lambda x: x["created_at"],
            reverse=True,
        )

        return Response(TransactionHistorySerializer(combined, many=True).data)
