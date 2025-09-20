from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, PasswordHistory, LoginActivity, MFAMethod,
    BackupCode, WebAuthnCredential, APIToken, Policy
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ("email", "is_email_verified", "is_active", "is_staff", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "is_email_verified")
    ordering = ("email",)
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone_number", "is_phone_verified")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Verification", {"fields": ("is_email_verified", "must_change_password")}),
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
