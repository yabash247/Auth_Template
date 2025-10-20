from django.contrib import admin
from .models import MembershipPlan, Membership, Payment

@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "interval", "is_active")
    list_filter = ("is_active", "interval")

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "started_at", "next_due_date", "auto_renew")
    list_filter = ("status", "auto_renew")
    search_fields = ("user__email", "plan__name")

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "currency", "status", "provider", "created_at", "event", "league", "scrimmage")
    list_filter = ("status", "provider", "currency")
    search_fields = ("user__email", "provider_ref", "event__title", "league__name", "scrimmage__title")

