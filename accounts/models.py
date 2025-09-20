from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.conf import settings

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
    username = None
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=32, blank=True, default="")
    is_phone_verified = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

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
