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
        fields = ["user", "balance", "last_updated"]
        read_only_fields = ["user", "last_updated"]


class CreditTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditTransaction
        fields = "__all__"





class TransactionHistorySerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    source = serializers.CharField()
    description = serializers.CharField()
    created_at = serializers.DateTimeField()
