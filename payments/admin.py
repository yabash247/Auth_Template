from django.contrib import admin
from .models import (
    CoinPurchase,
    CreditWallet,
    CreditWalletTransaction,  # 🟩 Added new model
)


# ============================================================
# ✅ Coin Purchase Admin
# ============================================================
@admin.register(CoinPurchase)
class CoinPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "coin_amount", "amount_fiat", "exchange_rate", "currency", "provider", "created_at")
    search_fields = ("user__email",)
    list_filter = ("provider", "currency")


# ============================================================
# ✅ Credit Wallet Admin
# ============================================================
@admin.register(CreditWallet)
class CreditWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "total_spent", "total_earned", "last_updated")
    search_fields = ("user__email",)
    readonly_fields = ("last_updated",)
    ordering = ("-last_updated",)


# ============================================================
# ✅ Credit Wallet Transaction Admin
# ============================================================
@admin.register(CreditWalletTransaction)
class CreditWalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "wallet", "type", "amount", "provider", "status", "reference", "created_at")
    list_filter = ("type", "provider", "status")
    search_fields = ("user__email", "reference")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
