from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import (
    UserProfile, MembershipPlan, Membership, Payment,
    Group, GroupMember, Event, RSVP, CalendarItem,
    Notification, MessageThread, Message
)

User = get_user_model()

# ---- Inlines tied to User ----
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fk_name = "user"
    extra = 0

class MembershipInline(admin.TabularInline):
    model = Membership
    fk_name = "user"
    extra = 0

class PaymentInline(admin.TabularInline):
    model = Payment
    fk_name = "user"
    extra = 0

# Replace default User admin with inlines (works for custom user too)
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline, MembershipInline, PaymentInline]

# ---- Group admin with members inline ----
class GroupMemberInline(admin.TabularInline):
    model = GroupMember
    extra = 0

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_public", "created_at")
    inlines = [GroupMemberInline]
    prepopulated_fields = {"slug": ("name",)}

# ---- The rest ----
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "verified", "visibility", "created_at")
    search_fields = ("user__username", "display_name", "location")

@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "currency", "interval", "is_active")

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "current_period_end", "auto_renew")
    list_filter = ("status", "plan__interval")

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "membership", "amount", "currency", "status", "method", "provider", "created_at")
    list_filter = ("status", "provider", "method")
    search_fields = ("user__username", "provider_ref")

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "host", "start", "end", "is_public", "group")
    list_filter = ("is_public", "group")

@admin.register(RSVP)
class RSVPAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "status", "created_at")
    list_filter = ("status",)

@admin.register(CalendarItem)
class CalendarItemAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "title", "start", "end", "created_at")
    list_filter = ("kind",)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "title", "is_read", "created_at")
    list_filter = ("kind", "is_read")

@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "updated_at")
    filter_horizontal = ("participants",)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at")
    search_fields = ("sender__username", "body")
