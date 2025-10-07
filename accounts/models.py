from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.utils.timezone import now

from .utils import notify_user

# accounts/serializers.py
from rest_framework import serializers

import logging
logger = logging.getLogger(__name__)

User = settings.AUTH_USER_MODEL

def default_expiry(seconds=300):
    return timezone.now() + timedelta(seconds=seconds)


# Optional phone number
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)
    
    
class User(AbstractUser):
    # Remove username, use email instead
    username = None
    email = models.EmailField(unique=True)

    # Verification
    is_email_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=32, blank=True, default="")
    is_phone_verified = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)

    # Account state
    is_locked = models.BooleanField(default=False)        # Temporary lock
    is_disabled = models.BooleanField(default=False)      # Manual disable
    is_soft_deleted = models.BooleanField(default=False)  # Soft delete marker
    deleted_at = models.DateTimeField(null=True, blank=True)

    is_suspended = models.BooleanField(default=False)  # user self-suspension
    suspended_at = models.DateTimeField(null=True, blank=True)
    pending_delete = models.BooleanField(default=False)  # scheduled deletion
    delete_requested_at = models.DateTimeField(null=True, blank=True)

    last_reauth_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
    
    def needs_reauth(self, minutes=10):
        """Require re-auth if last_reauth_at is too old or missing."""
        if not self.last_reauth_at:
            return True
        return timezone.now() - self.last_reauth_at > timedelta(minutes=minutes)

    # Account management helpers
    failed_attempts = models.IntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)

    def is_locked_out(self):
        return self.lockout_until and self.lockout_until > now()
        
        
    # 🔒 Lock
    def lock(self, by_admin=True):
        self.is_locked = True
        self.save(update_fields=["is_locked"])
        print(f"🔒 [TRACE] {self.email} locked (by_admin={by_admin})")
        notify_user(self, "locked", by_admin=by_admin)

    # 🔓 Unlock
    def unlock(self, by_admin=True):
        self.is_locked = False
        self.save(update_fields=["is_locked"])
        print(f"🔓 [TRACE] {self.email} unlocked (by_admin={by_admin})")
        notify_user(self, "unlocked", by_admin=by_admin)

    # ⛔ Disable
    def disable(self, by_admin=True):
        self.is_disabled = True
        self.save(update_fields=["is_disabled"])
        print(f"⛔ [TRACE] {self.email} disabled (by_admin={by_admin})")
        notify_user(self, "disabled", by_admin=by_admin)

    # ✅ Enable
    def enable(self, by_admin=True):
        self.is_disabled = False
        self.save(update_fields=["is_disabled"])
        print(f"✅ [TRACE] {self.email} enabled (by_admin={by_admin})")
        notify_user(self, "enabled", by_admin=by_admin)

    # 🗑️ Soft Delete
    def soft_delete(self, by_admin=True):
        from django.utils import timezone
        self.is_soft_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["is_soft_deleted", "deleted_at", "is_active"])
        print(f"🗑️ [TRACE] {self.email} soft deleted (by_admin={by_admin})")
        notify_user(self, "soft_deleted", by_admin=by_admin)

    # ♻️ Restore
    def restore(self, by_admin=True):
        self.is_soft_deleted = False
        self.deleted_at = None
        self.is_active = True
        self.save(update_fields=["is_soft_deleted", "deleted_at", "is_active"])
        print(f"♻️ [TRACE] {self.email} restored (by_admin={by_admin})")
        notify_user(self, "restored", by_admin=by_admin)

    # ⏸️ Suspend (always user-initiated)
    def suspend(self, by_admin=False):
        from django.utils import timezone
        self.is_suspended = True
        self.suspended_at = timezone.now()
        self.save(update_fields=["is_suspended", "suspended_at"])
        print(f"⏸️ [TRACE] {self.email} suspended self")
        notify_user(self, "suspended", by_admin=by_admin)

    # 🗑️ Request Delete (user only)
    def request_delete(self, by_admin=False):
        from django.utils import timezone
        self.pending_delete = True
        self.delete_requested_at = timezone.now()
        self.save(update_fields=["pending_delete", "delete_requested_at"])
        print(f"🗑️ [TRACE] {self.email} requested account deletion")
        notify_user(self, "delete_requested", by_admin=by_admin)

    # ↩️ Cancel Delete (user only)
    def cancel_delete(self, by_admin=False):
        self.pending_delete = False
        self.delete_requested_at = None
        self.save(update_fields=["pending_delete", "delete_requested_at"])
        print(f"↩️ [TRACE] {self.email} cancelled account deletion")
        notify_user(self, "delete_cancelled", by_admin=by_admin)

    # ☠️ Hard Delete
    def hard_delete(self, by_admin=True):
        print(f"☠️ [TRACE] {self.email} permanently deleted (by_admin={by_admin})")
        notify_user(self, "hard_deleted", by_admin=by_admin)
        super().delete()

class PasswordHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    password_hash = models.CharField(max_length=256)
    changed_at = models.DateTimeField(default=timezone.now)

class LoginActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=256, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    successful = models.BooleanField(default=True)
    method = models.CharField(max_length=32, default="password")  # password, otp, magic, social
    mfa_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} from {self.ip_address} at {self.timestamp}"

    def is_new_device_or_ip(user, ip, user_agent):
        last = LoginActivity.objects.filter(user=user, successful=True).order_by("-timestamp").first()
        if not last:
            return True
        changed = (last.ip_address != ip) or (last.user_agent != user_agent)
        print(f"🔍 [DEVICE CHECK] New IP/UA? {changed} (last={last.ip_address}, now={ip})")
        return changed


class MFAMethod(models.Model):
    T_TOTP = "TOTP"
    T_EMAIL = "EMAIL"
    T_SMS = "SMS"
    T_WEBAUTHN = "WEBAUTHN"
    TYPES = [(T_TOTP, "TOTP"), (T_EMAIL, "Email OTP"), (T_SMS, "SMS OTP"), (T_WEBAUTHN, "WebAuthn")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_methods")
    type = models.CharField(max_length=16, choices=TYPES)
    label = models.CharField(max_length=64, default="")
    secret = models.CharField(max_length=255, blank=True, default="")  # for TOTP/email otp seed
    enabled = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True)

class BackupCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="backup_codes")
    code_hash = models.CharField(max_length=128)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

class WebAuthnCredential(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="webauthn_credentials")
    credential_id = models.BinaryField()
    public_key = models.BinaryField()
    sign_count = models.IntegerField(default=0)
    label = models.CharField(max_length=64, default="Security Key")
    created_at = models.DateTimeField(default=timezone.now)

class APIToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=64)
    token_hash = models.CharField(max_length=128)
    scopes = models.JSONField(default=list)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

class Policy(models.Model):
    """Per-organization or global policy defining which auth methods are allowed/required.
    Attach via organizations.Membership or fallback to global default (singleton).
    """
    name = models.CharField(max_length=64, default="default")
    require_email_verification = models.BooleanField(default=False)
    require_mfa_for_staff = models.BooleanField(default=False)
    allow_password_login = models.BooleanField(default=True)
    allow_magic_link = models.BooleanField(default=True)
    allow_email_otp = models.BooleanField(default=True)
    allow_sms_otp = models.BooleanField(default=False)
    allow_totp = models.BooleanField(default=True)
    allow_webauthn = models.BooleanField(default=True)
    allow_social_login = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class LockoutPolicy(models.Model):
    name = models.CharField(max_length=64, default="default")
    active = models.BooleanField(default=True)

    threshold1 = models.IntegerField(default=3)
    wait1 = models.IntegerField(default=60)   # 1 min
    threshold2 = models.IntegerField(default=5)
    wait2 = models.IntegerField(default=300)  # 5 min
    threshold3 = models.IntegerField(default=8)
    wait3 = models.IntegerField(default=1800) # 30 min

    def __str__(self):
        return f"{self.name} Policy"


class MagicLink(models.Model):
    """
    Single-use magic link token for passwordless login.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="magic_links")
    token = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")

    def is_valid(self):
        valid = (not self.used) and (timezone.now() < self.expires_at)
        print(f"MagicLink.is_valid: token={self.token} used={self.used} expires_at={self.expires_at} now={timezone.now()} => {valid}")
        return valid

class EmailOTP(models.Model):
    """
    Short numeric code sent by email.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_otps")
    code = models.CharField(max_length=8, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    verified = models.BooleanField(default=False)
    purpose = models.CharField(max_length=32, default="login")  # login / reset / mfa

    def is_valid(self):
        valid = (not self.verified) and (timezone.now() < self.expires_at)
        print(f"EmailOTP.is_valid: code={self.code} verified={self.verified} expires_at={self.expires_at} now={timezone.now()} => {valid}")
        return valid

class SMSOTP(models.Model):
    """
    Short numeric code sent via SMS.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sms_otps")
    code = models.CharField(max_length=8, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    verified = models.BooleanField(default=False)
    phone = models.CharField(max_length=32, blank=True, default="")

    def is_valid(self):
        valid = (not self.verified) and (timezone.now() < self.expires_at)
        print(f"SMSOTP.is_valid: code={self.code} verified={self.verified} expires_at={self.expires_at} now={timezone.now()} => {valid}")
        return valid

class BackupCode(models.Model):
    """
    One-time backup codes for account recovery. Save hashed in prod.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="backup_codes")
    code = models.CharField(max_length=64, db_index=True)  # store hashed in real prod
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

class WebAuthnCredential(models.Model):
    """
    Minimal WebAuthn credential container (adapt later for lib usage).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="webauthn_credentials")
    credential_id = models.BinaryField()
    public_key = models.BinaryField()
    sign_count = models.IntegerField(default=0)
    label = models.CharField(max_length=64, default="Security Key")
    created_at = models.DateTimeField(default=timezone.now)


class AuthRequestLog(models.Model):
    """
    Tracks all authentication-related requests:
    OTPs, Magic Links, SMS, TOTP, etc.
    Used for rate-limiting, auditing, and security alerts.
    """

    ACTION_CHOICES = [
        ("magic_link", "Magic Link"),
        ("email_otp", "Email OTP"),
        ("sms_otp", "SMS OTP"),
        ("totp", "TOTP Verification"),
        ("backup_code", "Backup Code Use"),
        ("webauthn", "WebAuthn/Passkey"),
        ("login_attempt", "Login Attempt"),
        ("password_reset", "Password Reset"),
        ("unknown", "Unknown"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="auth_requests",
    )
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, default="unknown")

    success = models.BooleanField(default=True)
    message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["ip"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        who = self.user.email if self.user else self.email or self.phone
        return f"[{self.action}] {who or 'Anonymous'} @ {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class MagicRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class MagicConsumeSerializer(serializers.Serializer):
    token = serializers.CharField()

class EmailOTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    digits = serializers.IntegerField(default=6, min_value=4, max_value=8)

class EmailOTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()

class SMSOTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField()
    digits = serializers.IntegerField(default=6, min_value=4, max_value=8)

class SMSOTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField()

class TOTPSetupBeginSerializer(serializers.Serializer):
    # returns secret & otpauth_url
    pass

class TOTPConfirmSerializer(serializers.Serializer):
    code = serializers.CharField()

class BackupCodesSerializer(serializers.Serializer):
    count = serializers.IntegerField(default=10, min_value=1, max_value=50)

class BackupCodeVerifySerializer(serializers.Serializer):
    code = serializers.CharField()

# WebAuthn serializers (stubs)
class WebAuthnBeginSerializer(serializers.Serializer):
    label = serializers.CharField(required=False, default="")

class WebAuthnCompleteSerializer(serializers.Serializer):
    credential = serializers.DictField()


# --------------------------------------------
# Adaptive Authentication Policy
# --------------------------------------------
# --------------------------------------------
# Adaptive Authentication Policy (Extended)
# --------------------------------------------
class AuthPolicy(models.Model):
    SCOPE_CHOICES = [
        ("global", "Global (Admin Default)"),
        ("user", "User Specific"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auth_policies",
        null=True,
        blank=True,
    )
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default="user")
    is_mandatory = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # ✅ Admin defines available methods for each action
    applicable_methods = models.JSONField(default=dict)  # {"login": ["password", "otp", "phrase"]}
    # ✅ User chooses subset if allowed
    selected_methods = models.JSONField(default=dict)    # {"login": ["password", "phrase"]}

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "scope"],
                name="unique_user_auth_policy"
            )
        ]

    def get_methods_for(self, action):
        """Return methods enforced for this action."""
        if self.is_mandatory:
            return self.applicable_methods.get(action, [])
        return self.selected_methods.get(action, [])

    def __str__(self):
        return f"AuthPolicy ({self.scope}) for {self.user or 'GLOBAL'}"


class SecurityPhrase(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_phrase_policy"
    )
    phrase_hash = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    def set_phrase(self, phrase):
        """Hash and save the phrase securely."""
        from django.contrib.auth.hashers import make_password
        self.phrase_hash = make_password(phrase)
        self.save()

    def verify_phrase(self, phrase):
        """Check user’s input phrase."""
        from django.contrib.auth.hashers import check_password
        return check_password(phrase, self.phrase_hash)

    def __str__(self):
        return f"SecurityPhrase for {self.user.email}"
