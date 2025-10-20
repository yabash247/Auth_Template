from rest_framework import serializers
from .models import PaymentTransaction, CreditWallet, CreditTransaction


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = "__all__"
        read_only_fields = ["id", "status", "created_at", "processed_at"]


class CreditWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditWallet
        fields = ["user", "balance", "updated_at"]
        read_only_fields = ["user", "updated_at"]


class CreditTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditTransaction
        fields = "__all__"
