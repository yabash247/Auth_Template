from django.contrib import admin
from .models import CoinPurchase, CreditWallet

@admin.register(CoinPurchase)
class CoinPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "coin_amount", "amount_fiat", "exchange_rate", "created_at")
    search_fields = ("user__email",)
    list_filter = ("provider", "currency")

@admin.register(CreditWallet)
class CreditWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "total_spent", "total_earned", "last_updated")
    search_fields = ("user__email",)
