from django.contrib import admin
from django_json_widget.widgets import JSONEditorWidget
from django.db import models
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, PasswordHistory, LoginActivity, MFAMethod,
    BackupCode, WebAuthnCredential, APIToken, Policy, LockoutPolicy,
    EmailOTP, SMSOTP, MagicLink
)

formfield_overrides = {
    models.JSONField: {"widget": JSONEditorWidget},
}

@admin.action(description="Unlock selected users")
def unlock_users(modeladmin, request, queryset):
    queryset.update(failed_attempts=0, lockout_until=None)

def lock_accounts(self, request, queryset):
        for user in queryset:
            user.lock()
        self.message_user(request, f"🔒 Locked {queryset.count()} user(s).")

def unlock_accounts(self, request, queryset):
    for user in queryset:
        user.unlock()
    self.message_user(request, f"🔓 Unlocked {queryset.count()} user(s).")

def soft_delete_accounts(self, request, queryset):
    for user in queryset:
        user.soft_delete()
    self.message_user(request, f"🗑️ Soft deleted {queryset.count()} user(s).")

def restore_accounts(self, request, queryset):
    for user in queryset:
        user.restore()
    self.message_user(request, f"♻️ Restored {queryset.count()} user(s).")

def hard_delete_accounts(self, request, queryset):
    count = queryset.count()
    for user in queryset:
        user_email = user.email
        user.hard_delete()
        print(f"💀 [TRACE] Admin hard deleted user {user_email}")
    self.message_user(request, f"💀 Permanently deleted {count} user(s).")

def disable_accounts(self, request, queryset):
        for user in queryset:
            user.disable()
        self.message_user(request, f"Disabled {queryset.count()} accounts.")

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = (
        "id",
        "email",
        "is_email_verified",
        "is_active",
        "is_staff",
        "is_locked",
        "is_disabled",
        #"is_soft_deleted",
        "pending_delete",
        #"failed_attempts",
        #"lockout_until",
        #"date_joined",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "is_email_verified",
        "is_locked",
        "is_soft_deleted",
        "pending_delete",
    )
    ordering = ("email",)
    search_fields = ("email",)

    # 👇 keep only one actions list (don’t override later)
    actions = [
        unlock_users,
        lock_accounts,
        soft_delete_accounts,
        restore_accounts,
        hard_delete_accounts,
        disable_accounts,
    ]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Status", {
            "fields": (
                "is_email_verified",
                "is_active",
                "is_locked",
                "is_disabled",
                "is_soft_deleted",
                "pending_delete",
                "failed_attempts",
                "lockout_until",
                "must_change_password",   # moved here instead of duplicate section
            )
        }),
        ("Personal info", {"fields": ("first_name", "last_name", "phone_number", "is_phone_verified")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "is_staff", "is_superuser"),
        }),
    )

    



@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "changed_at")

@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "timestamp", "ip_address", "successful", "method", "mfa_used")
    list_filter = ("successful", "method", "mfa_used")

@admin.register(MFAMethod)
class MFAMethodAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "enabled", "last_used_at")

@admin.register(BackupCode)
class BackupCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "used", "created_at")

@admin.register(WebAuthnCredential)
class WebAuthnCredentialAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "created_at", "sign_count")

@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "expires_at", "revoked_at")

@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = (
        "name", "require_email_verification", "require_mfa_for_staff",
        "allow_password_login", "allow_magic_link", "allow_totp", "allow_webauthn"
    )


# ✅ New admin for LockoutPolicy
@admin.register(LockoutPolicy)
class LockoutPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "name", "active",
        "threshold1", "wait1",
        "threshold2", "wait2",
        "threshold3", "wait3",
    )
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "used", "expires_at", "created_at")
    search_fields = ("user__email", "token")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user","code","verified","expires_at","created_at","purpose")
    search_fields = ("user__email","code")

@admin.register(SMSOTP)
class SMSOTPAdmin(admin.ModelAdmin):
    list_display = ("user","phone","code","verified","expires_at","created_at")
    search_fields = ("user__email","phone")


class BackupCodeAdmin(admin.ModelAdmin):
    list_display = ("user","code","used","created_at")
    search_fields = ("user__email","code")

class WebAuthnCredentialAdmin(admin.ModelAdmin):
    list_display = ("user","label","created_at","sign_count")
    search_fields = ("user__email","label")



from .models import AuthRequestLog
@admin.register(AuthRequestLog)
class AuthRequestLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "email", "phone", "ip", "success", "created_at")
    list_filter = ("action", "success", "created_at")
    search_fields = ("email", "phone", "user__email", "ip", "message")
    readonly_fields = ("created_at", "timestamp", "message")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False  # prevent manual insertions

    def has_change_permission(self, request, obj=None):
        return False  # make logs read-only

    def has_delete_permission(self, request, obj=None):
        return True  # admin can clear logs manually if needed

from django.contrib import admin
from .models import AuthPolicy


@admin.register(AuthPolicy)
class AuthPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_display",
        "scope",
        "is_mandatory",
        "is_active",
        "updated_at",
    )
    list_editable = ("is_mandatory", "is_active")
    list_filter = ("scope", "is_mandatory", "is_active")
    search_fields = ("user__email",)
    ordering = ("-updated_at",)

    readonly_fields = ("updated_at",)
    fieldsets = (
        ("General", {
            "fields": ("user", "scope", ("is_mandatory", "is_active"))
        }),
        ("Applicable Methods (Admin Defines Options)", {
            "fields": ("applicable_methods",),
            "description": "Admin-defined methods users can choose from (e.g. {'login': ['password','otp','phrase']})"
        }),
        ("Selected Methods (User Selection)", {
            "fields": ("selected_methods",),
            "description": "Subset of applicable methods selected by the user (ignored if mandatory=True)"
        }),
        ("Metadata", {
            "fields": ("updated_at",)
        }),
    )

    def user_display(self, obj):
        return obj.user.email if obj.user else "— GLOBAL —"
    user_display.short_description = "User"

