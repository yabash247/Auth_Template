from django.contrib.auth import login, logout, get_user_model, get_backends
from ipware import get_client_ip
from rest_framework import generics, permissions, status, views, viewsets
from rest_framework.response import Response
import pyotp

from .models import User, LoginActivity, MFAMethod, BackupCode, MagicLink, EmailOTP, SMSOTP, WebAuthnCredential, AuthPolicy
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, JWTSerializer, ReAuthSerializer
from .tokens import email_verification_token, magic_link_token
from .utils import send_magic_link_email, get_required_methods

from allauth.account.models import EmailAddress, EmailConfirmation, EmailConfirmationHMAC
from django.template.loader import render_to_string
from allauth.account.views import ConfirmEmailView
from django.shortcuts import get_object_or_404, redirect
from rest_framework.views import APIView
from django.contrib.auth import authenticate

from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.timezone import now, timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from allauth.socialaccount.models import SocialAccount

# accounts/views.py
from django.db import transaction
from .serializers import (
    MagicRequestSerializer, MagicConsumeSerializer,
    EmailOTPRequestSerializer, EmailOTPVerifySerializer,
    SMSOTPRequestSerializer, SMSOTPVerifySerializer,
    TOTPConfirmSerializer, BackupCodesSerializer, BackupCodeVerifySerializer,
    WebAuthnBeginSerializer, WebAuthnCompleteSerializer,  AuthPolicySerializer
)
from .utils import (
    create_magic_link, send_magic_email,
    create_and_send_email_otp, create_and_send_sms_otp,
    generate_totp_secret, backup_codes_for_user
)
import secrets

User = get_user_model()

# ---------- Helpers ----------
def _log_login(user, request, ok=True, method="password", mfa_used=False):
    ip, _ = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")[:250]
    LoginActivity.objects.create(user=user, ip_address=ip, user_agent=ua, successful=ok, method=method, mfa_used=mfa_used)

# ---------- Registration & Email Verify ----------
class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    queryset = User.objects.all()

    def perform_create(self, serializer):
        user = serializer.save()
        print(f"👤 [REGISTER] Created user: {user.email}")

        from allauth.account.models import EmailAddress, EmailConfirmationHMAC
        from allauth.account.adapter import get_adapter

        # Ensure the EmailAddress object exists
        email_address, _ = EmailAddress.objects.get_or_create(user=user, email=user.email)
        email_address.verified = False
        email_address.primary = True
        email_address.save()

        # ✅ Create the confirmation manually (no deprecated method)
        confirmation = EmailConfirmationHMAC(email_address)

        # Use the custom adapter to send styled email with correct frontend URL
        adapter = get_adapter()
        adapter.send_confirmation_mail(self.request, confirmation, signup=True)

        print("📧 [REGISTER] Verification email sent using CustomAccountAdapter.")



class VerifyEmailView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(pk=uid)
        except UserModel.DoesNotExist:
            return Response({"detail": "Invalid user"}, status=400)
        if email_verification_token.check_token(user, token):
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])
            return Response({"detail": "Email verified"})
        return Response({"detail": "Invalid or expired token"}, status=400)
    
# ✅ Corrected version — works with frontend /verify-email/<key>/
class VerifyEmailKeyView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, key):
        print(f"🔐 [TRACE] Email verification requested for key: {key}")

        try:
            confirmation = EmailConfirmationHMAC.from_key(key)
            if not confirmation:
                print("⚠️ [TRACE] Invalid or expired confirmation key")
                return Response({"detail": "Invalid or expired verification link."}, status=status.HTTP_400_BAD_REQUEST)

            confirmation.confirm(request)
            user = confirmation.email_address.user
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])

            print(f"✅ [TRACE] Email verified for: {user.email}")
            return Response({"detail": "Email verified successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"💥 [ERROR] Verification failed: {e}")
            return Response({"detail": "Invalid or expired verification link."}, status=status.HTTP_400_BAD_REQUEST)


class CustomConfirmEmailView(ConfirmEmailView):
    """
    Override allauth confirm email to ensure email is marked verified.
    """

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)

        # Always ensure verified (extra safety)
        email_address = self.get_object()
        email_address.verified = True
        email_address.save()
        user = email_address.user
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        # Redirect to React frontend success page
        return redirect("/email-verified/")  # 👈 adjust path for your React app


    def get_object(self, queryset=None):
        key = self.kwargs["key"]
        return get_object_or_404(EmailConfirmation, key=key)


class ForgotPasswordView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"detail": "Email is required"}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't leak account existence
            return Response(
                {"detail": "If account exists, you will receive an email"},
                status=200,
            )

        # Generate token + uid
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Build frontend reset link
        frontend_url = getattr(settings, "FRONTEND_URL", "http://127.0.0.1:3000")
        reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"

        # Send email
        subject = "Reset your password"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
        text_body = f"Click the link below to reset your password:\n\n{reset_link}"
        html_body = f"""
            <p>Click the button below to reset your password:</p>
            <p><a href="{reset_link}" style="background:#1e90ff;color:#fff;padding:10px 20px;
               border-radius:5px;text-decoration:none;">Reset Password</a></p>
            <p>If the button doesn't work, copy and paste this link into your browser:<br>{reset_link}</p>
        """

        msg = EmailMultiAlternatives(subject, text_body, from_email, [email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()

        return Response(
            {"detail": "If account exists, you will receive an email"},
            status=200,
        )

class ResetPasswordView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not uidb64 or not token or not new_password:
            return Response(
                {"detail": "uid, token, and new_password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"detail": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate token
        if not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set new password & reset the must_change_password flag
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(views.APIView):
    """
    Allow authenticated users to change their password.
    Requires: current_password, new_password
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not current_password or not new_password:
            return Response(
                {"detail": "Both current_password and new_password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Re-authenticate
        reauth_user = authenticate(request=request, email=user.email, password=current_password)
        if reauth_user is None:
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update password
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


# --------------------------------------------
# Adaptive Auth Policy Mixin
# --------------------------------------------
class AdaptiveAuthMixin:
    """
    Provides per-action adaptive authentication enforcement.
    Use this in sensitive views like profile edit, delete account, etc.
    """

    def enforce_auth_policy(self, request, action):
        from .models import EmailOTP
        user = request.user
        required = get_required_methods(user, action)

        # --- Security Phrase ---
        if "security_phrase" in required:
            phrase = request.data.get("security_phrase")
            if not phrase or not hasattr(user, "security_phrase_policy"):
                return Response({"detail": "Security phrase required."}, status=403)
            if not user.security_phrase_policy.verify_phrase(phrase):
                return Response({"detail": "Invalid security phrase."}, status=403)

        # --- OTP (Email/SMS) ---
        if "otp" in required or "email_otp" in required:
            otp = request.data.get("otp")
            valid = (
                otp
                and EmailOTP.objects.filter(user=user, code=otp, verified=True).exists()
            )
            if not valid:
                return Response({"detail": "Valid OTP required."}, status=403)

        # --- Backup Code ---
        if "backup_code" in required:
            from .models import BackupCode
            code = request.data.get("backup_code")
            hit = BackupCode.objects.filter(user=user, code=code, used=False).first()
            if not hit:
                return Response({"detail": "Backup code invalid or used."}, status=403)
            hit.used = True
            hit.save(update_fields=["used"])

        # --- WebAuthn ---
        if "webauthn" in required and not user.webauthn_credentials.exists():
            return Response({"detail": "WebAuthn verification required."}, status=403)

        # --- Google OAuth ---
        if "google" in required and not user.socialaccount_set.filter(provider="google").exists():
            return Response({"detail": "Google authentication required."}, status=403)

        return None  # ✅ Passed all required checks


# --------------------------------------------
# Adaptive Multi-Step LoginView (with diagnostics)
# --------------------------------------------
class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        print("🔑 [TRACE] Login request received:", request.data)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        remember_me = request.data.get("remember_me", False)
        print(f"🔑 [TRACE] Remember me: {remember_me}")


        # ✅ Step 1: Basic account checks
        if user.is_disabled:
            return Response(
                {"detail": "Account is disabled. Contact support.", "required_methods": []},
                status=403,
            )

        if user.is_soft_deleted:
            return Response(
                {"detail": "Account is deleted. Contact support.", "required_methods": []},
                status=403,
            )

        if not user.is_email_verified:
            return Response(
                {"detail": "Email verification required.", "required_methods": []},
                status=403,
            )

        '''
        
        # 🔐 MFA check (optional)
        has_mfa = user.mfa_methods.filter(enabled=True).exists()
        if has_mfa and not request.data.get("mfa_ok"):
            return Response(
                {
                    "mfa_required": True,
                    "methods": list(
                        user.mfa_methods.filter(enabled=True).values_list("type", flat=True)
                    ),
                },
                status=200,
            )
        '''
        # --------------------------------------------
        # ✅ Step 2: Adaptive requirement discovery
        # --------------------------------------------
        required_methods = get_required_methods(user, "login")
        print(f"🔎 [TRACE] Required methods for login: {required_methods}")


        # ✅ Step 3: Enforce per-user requirements

        # --- Security Phrase ---
        if "security_phrase" in required_methods:
            phrase = request.data.get("security_phrase")
            if not phrase:
                print(f"🚫 [TRACE] Missing security_phrase for {user.email}")
                return Response(
                    {
                        "detail": "Security phrase required.",
                        "required_methods": ["password", "security_phrase"],
                    },
                    status=403,
                )

            if not hasattr(user, "security_phrase_policy") or not user.security_phrase_policy.verify_phrase(phrase):
                print(f"🚫 [TRACE] Invalid security phrase for {user.email}")
                return Response(
                    {
                        "detail": "Invalid security phrase.",
                        "required_methods": ["password", "security_phrase"],
                    },
                    status=403,
                )

        # Require Google OAuth if configured
        if "google" in required_methods and not user.socialaccount_set.filter(provider="google").exists():
            print(f"🚫 [TRACE] Google auth required for {user.email}")
            return Response(
                {
                    "detail": "Google authentication required.",
                    "required_methods": ["password", "google"],
                },
                status=403,
            )

        # If OTP required --- OTP Enforcement (email/sms/totp/otp unified) ---
        if any(m in required_methods for m in ["otp", "email_otp", "sms_otp", "totp"]):
            otp_code = request.data.get("otp")
            from .models import EmailOTP, SMSOTP

            # Try to validate either email or sms OTP
            valid_otp = False
            if otp_code:
                email_otp = EmailOTP.objects.filter(user=user, code=otp_code, verified=True).first()
                sms_otp = SMSOTP.objects.filter(user=user, code=otp_code, verified=True).first()
                if email_otp or sms_otp:
                    valid_otp = True

            if not valid_otp:
                print(f"🚫 [TRACE] OTP required for {user.email} but missing or invalid.")
                return Response(
                    {
                        "detail": "OTP required or invalid.",
                        "required_methods": ["password", "otp"],
                    },
                    status=403,
                )
            
            return Response(
                {"mfa_required": True, "methods": required_methods},
                status=200,
            )
        
        # ✅ Step 4: Successful login — generate JWT
        payload = JWTSerializer.for_user(user, remember_me=request.data.get("remember_me", False))
        print(f"✅ Successful login for {user.email} at {now()}")
        return Response(payload, status=200)





class LogoutView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # If client sends refresh to blacklist, dj-rest-auth/simplejwt will handle in their endpoints too
        logout(request)
        return Response(status=status.HTTP_205_RESET_CONTENT)

class MeView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

# ---------- Magic Link ----------

class MMagicLinkRequestView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "If account exists, you'll get a link"}, status=200)
        token = magic_link_token.make_token(user)
        send_magic_link_email(user, token)
        return Response({"detail": "If account exists, you'll get a link"}, status=200)

class MMagicLinkConsumeView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return Response({"detail": "Invalid user"}, status=400)
        if not magic_link_token.check_token(user, token):
            return Response({"detail": "Invalid or expired link"}, status=400)
        # Login & issue JWT
        payload = JWTSerializer.for_user(user)
        _log_login(user, request, ok=True, method="magic", mfa_used=False)
        return Response(payload)

class MagicLinkRequestView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # enforce_https(request)  # 🚨 HTTPS required (function not defined)
        email = request.data.get("email")
        # check_rate_limit(f"magic:{email}")  # 🚨 Rate-limit per email (function not defined)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            print(f"MagicLinkRequest: no account {email}")
            return Response({"detail": "If account exists, link sent."}, status=200)

        ml = create_magic_link(user, ttl_seconds=600, request=request)
        send_magic_email(user, ml)
        print(f"✅ [TRACE] Magic link created for {user.email}")
        return Response({"detail": "If account exists, link sent."}, status=200)


class MagicLinkConsumeView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # enforce_https(request)  # Removed: function not defined
        serializer = MagicConsumeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        try:
            ml = MagicLink.objects.select_related("user").get(token=token)
        except MagicLink.DoesNotExist:
            print("🚨 [MagicLink] Invalid token:", token)
            return Response({"detail": "Invalid or expired link"}, status=400)

        if not ml.is_valid():
            print("🚨 [MagicLink] Expired or already used:", token)
            return Response({"detail": "Invalid or expired link"}, status=400)

        user = ml.user
        # log_device_fingerprint(request, user)  # 🚨 Device/IP check (function not defined, removed)

        with transaction.atomic():
            ml.used = True
            ml.save(update_fields=["used"])
            print(f"✅ [TRACE] Magic link login success for {user.email}")
            payload = JWTSerializer.for_user(user)
            return Response(payload, status=200)



# ---------- TOTP (2FA) ----------
class TOTPSetupBeginView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Create or reuse a TOTP secret for provisioning
        import base64, os
        secret = base64.b32encode(os.urandom(10)).decode("utf-8").replace("=", "")
        method, _ = MFAMethod.objects.get_or_create(user=request.user, type=MFAMethod.T_TOTP, defaults={"secret": secret})
        if not method.secret:
            method.secret = secret
            method.save(update_fields=["secret"])
        # Provide otpauth uri
        issuer = "AuthTemplate"
        email = request.user.email
        uri = f"otpauth://totp/{issuer}:{email}?secret={method.secret}&issuer={issuer}&digits=6&period=30"
        return Response({"otpauth_uri": uri})

class TOTPConfirmView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get("code")
        try:
            method = MFAMethod.objects.get(user=request.user, type=MFAMethod.T_TOTP)
        except MFAMethod.DoesNotExist:
            return Response({"detail": "No TOTP method started"}, status=400)
        totp = pyotp.TOTP(method.secret)
        if not totp.verify(code, valid_window=1):
            return Response({"detail": "Invalid code"}, status=400)
        method.enabled = True
        method.save(update_fields=["enabled"])
        # Issue backup codes
        from .utils import generate_backup_codes, hash_token
        codes = generate_backup_codes()
        for c in codes:
            BackupCode.objects.create(user=request.user, code_hash=hash_token(c))
        return Response({"detail": "TOTP enabled", "backup_codes": codes})

class MFAVerifyView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Generic MFA verify after password login
        uid = request.data.get("uid")
        method_type = request.data.get("type")
        code = request.data.get("code")
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return Response({"detail": "Invalid user"}, status=400)

        if method_type == "TOTP":
            try:
                method = MFAMethod.objects.get(user=user, type=MFAMethod.T_TOTP, enabled=True)
            except MFAMethod.DoesNotExist:
                return Response({"detail": "TOTP not enabled"}, status=400)
            totp = pyotp.TOTP(method.secret)
            if not totp.verify(code, valid_window=1):
                _log_login(user, request, ok=False, method="password", mfa_used=True)
                return Response({"detail": "Invalid code"}, status=400)
        elif method_type == "BACKUP":
            from .utils import hash_token
            hashed = hash_token(code)
            hit = BackupCode.objects.filter(user=user, code_hash=hashed, used=False).first()
            if not hit:
                return Response({"detail": "Invalid backup code"}, status=400)
            hit.used = True
            hit.save(update_fields=["used"])
        else:
            return Response({"detail": "Unsupported MFA type"}, status=400)

        payload = JWTSerializer.for_user(user)
        _log_login(user, request, ok=True, method="password", mfa_used=True)
        return Response(payload)

# NOTE: WebAuthn endpoints would go here (register/authenticate begin/complete).
# For brevity they are scaffolded in README with library 'webauthn'.

class ResendVerificationEmailView(APIView):
    """
    API endpoint to resend email verification.
    - Works for logged-in users (no need to provide email).
    - Works for email-only input (logged-out users).
    """
    permission_classes = [permissions.AllowAny]

    def _send_verification_email(self, request, user, email):
        """
        Custom email sending that works even outside full Django context.
        Uses SMTP backend directly and allauth HMAC token for security.
        """
        try:
            email_address, _ = EmailAddress.objects.get_or_create(user=user, email=email)
            if email_address.verified:
                print(f"✅ [TRACE] Email already verified for {email}")
                return {"detail": "Email is already verified."}, status.HTTP_400_BAD_REQUEST

            # Generate confirmation key (works even without allauth request context)
            # inside _send_verification_email (ResendVerificationEmailView)
            confirmation = EmailConfirmationHMAC(email_address)

            print("🧭 [TRACE] FRONTEND_URL from settings:", getattr(settings, "FRONTEND_URL", None))
            frontend_url = getattr(settings, "FRONTEND_URL", "http://127.0.0.1:3000")
            verify_url = f"{frontend_url}/verify-email/{confirmation.key}"

            print(f"🔑 [TRACE] Generated confirmation link: {verify_url}")

            context = {
                "user": user,
                "user_email": user.email,
                "verify_url": verify_url,            # main alias
                "activate_url": verify_url,          # alias some templates use
                "verification_link": verify_url,     # another alias
                "site_name": getattr(settings, "SITE_NAME", "Auth Template"),
            }

            subject = f"Verify your email for {context['site_name']}"
            text_body = render_to_string("emails/verify_email.txt", context)
            html_body = render_to_string("emails/verify_email.html", context)

            print("📦 [TRACE] Email context data:", context)
            print("📄 [TRACE] Rendered text body:\n", text_body)
            print("📄 [TRACE] Rendered HTML body:\n", html_body)


            print(f"📨 [TRACE] Sending verification email to {email} via SMTP...")

            msg = EmailMultiAlternatives(
                subject,
                text_body,
                settings.DEFAULT_FROM_EMAIL,
                [email],
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)

            print(f"✅ [TRACE] Verification email successfully sent to {email}")
            return {"detail": f"Verification email sent to {email}"}, status.HTTP_200_OK

        except Exception as e:
            print(f"⚠️ [ERROR] Failed to send verification email: {e}")
            return {"detail": "Error sending verification email."}, status.HTTP_500_INTERNAL_SERVER_ERROR

    def post(self, request, *args, **kwargs):
        # 🧩 Case 1: Logged-in user
        if request.user.is_authenticated:
            print(f"👤 [TRACE] Authenticated user requested resend: {request.user.email}")
            email_address = EmailAddress.objects.filter(user=request.user, verified=False).first()

            if not email_address:
                print("⚠️ [TRACE] No unverified email found for logged-in user.")
                return Response(
                    {"detail": "No unverified email found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data, code = self._send_verification_email(request, request.user, email_address.email)
            return Response(data, status=code)

        # 🧩 Case 2: Email-only input (user not logged in)
        email = request.data.get("email")
        print(f"📧 [TRACE] Resend verification requested for email: {email}")

        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            print(f"👤 [TRACE] Found user for email: {email}")
        except User.DoesNotExist:
            print(f"⚠️ [TRACE] No user found for {email}, returning generic success message.")
            # Prevent email enumeration
            return Response(
                {"detail": "If this account exists, a verification email has been sent."},
                status=status.HTTP_200_OK,
            )

        data, code = self._send_verification_email(request, user, email)
        return Response(data, status=code)


class AccountLockView(AdaptiveAuthMixin, views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            user.lock()
            return Response({"detail": "User locked."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)

class AccountUnlockView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            user.unlock()
            return Response({"detail": "User unlocked."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)


class AccountDisableView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            user.disable()
            return Response({"detail": "User disabled."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)

class AccountEnableView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            user.enable()
            return Response({"detail": "User enabled."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)


class AccountSoftDeleteView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            user.soft_delete()
            return Response({"detail": "User soft deleted."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)

class AccountRestoreView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            user.restore()
            return Response({"detail": "User restored."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)

class AccountHardDeleteView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            user.hard_delete()
            return Response({"detail": "User permanently deleted."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)



# 🔹 Suspend account (user-initiated)
class SuspendAccountView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.needs_reauth(minutes=10):  # force reauth within last 10 minutes
            print(f"🚫 [TRACE] Re-auth required for {user.email} before suspension")
            return Response(
                {"detail": "Re-authentication required", "reauth_required": True},
                status=status.HTTP_403_FORBIDDEN,
            )
        user.suspend(by_admin=False)
        return Response({"detail": "Your account has been suspended."}, status=200)


# 🔹 Request delete (user-initiated)
class RequestDeleteAccountView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.needs_reauth(minutes=10):
            print(f"🚫 [TRACE] Re-auth required for {user.email} before delete request")
            return Response(
                {"detail": "Re-authentication required", "reauth_required": True},
                status=status.HTTP_403_FORBIDDEN,
            )
        user.request_delete(by_admin=False)
        return Response({"detail": "Account deletion requested. You can cancel before processing."}, status=200)


# 🔹 Cancel delete (user-initiated)
class CancelDeleteAccountView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not getattr(user, "pending_delete", False):
            return Response({"detail": "No delete request to cancel."}, status=400)
        user.cancel_delete(by_admin=False)
        return Response({"detail": "Account deletion cancelled."}, status=200)


# 🔹 Hard delete (user OR admin)
class HardDeleteAccountView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        email = user.email

        # Require re-auth within last 10 minutes
        if user.needs_reauth(minutes=10):
            print(f"🚫 [TRACE] Re-auth required for {user.email} before account deletion")
            return Response(
                {"detail": "Re-authentication required", "reauth_required": True},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        user.hard_delete(by_admin=False)
        return Response({"detail": f"Account {email} permanently deleted."}, status=200)



class ReAuthView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ReAuthSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.last_reauth_at = timezone.now()
        user.save(update_fields=["last_reauth_at"])

        print(f"🔐 [TRACE] User {user.email} re-authenticated at {user.last_reauth_at}")
        return Response({"detail": "Re-authentication successful"}, status=status.HTTP_200_OK)




# ---------------------
# Magic link
# ---------------------
class MagicLinkRequestView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MagicRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # don't leak existence
            print(f"MagicLinkRequest: email not found {email}")
            return Response({"detail": "If this account exists, a magic link has been sent."}, status=200)

        ml = create_magic_link(user, ttl_seconds=600, request=request)
        send_magic_email(user, ml)
        return Response({"detail": "If this account exists, a magic link has been sent."}, status=200)

class MagicLinkConsumeView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MagicConsumeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        try:
            ml = MagicLink.objects.select_related("user").get(token=token)
        except MagicLink.DoesNotExist:
            print("MagicLinkConsume: invalid token", token)
            return Response({"detail": "Invalid or expired link."}, status=400)

        if not ml.is_valid():
            print("MagicLinkConsume: token not valid or used", token)
            return Response({"detail": "Invalid or expired link."}, status=400)

        # mark as used & login
        with transaction.atomic():
            ml.used = True
            ml.save(update_fields=["used"])
            user = ml.user
            print(f"MagicLinkConsume: logging in user {user.email}")

            # 🔑 Fix: explicitly provide backend
            backend = get_backends()[0]  # usually ModelBackend
            login(request, user, backend=backend.__class__.__name__)
            
            # Return JWT or session info as needed. For example, use JWTSerializer.for_user:
            from .serializers import JWTSerializer
            payload = JWTSerializer.for_user(user)
            return Response(payload, status=200)

# ---------------------
# Email OTP
# ---------------------
class EmailOTPRequestView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailOTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        digits = serializer.validated_data["digits"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            print("EmailOTPRequest: user not found", email)
            # don't leak
            return Response({"detail":"If this account exists, you will receive an OTP."}, status=200)

        create_and_send_email_otp(user, ttl_seconds=300, digits=digits)
        return Response({"detail":"If this account exists, you will receive an OTP."}, status=200)

class EmailOTPVerifyView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            print("EmailOTPVerify: user not found", email)
            return Response({"detail":"Invalid code."}, status=400)
        otp = EmailOTP.objects.filter(user=user, code=code).order_by("-created_at").first()
        if not otp or not otp.is_valid():
            print("EmailOTPVerify: invalid or missing OTP", email, code)
            return Response({"detail":"Invalid or expired code."}, status=400)

        # mark verified
        otp.verified = True
        otp.save(update_fields=["verified"])
        print(f"EmailOTPVerify: success for {user.email}")
        from .serializers import JWTSerializer
        payload = JWTSerializer.for_user(user)
        return Response(payload, status=200)

# ---------------------
# SMS OTP
# ---------------------
class SMSOTPRequestView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SMSOTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        digits = serializer.validated_data["digits"]
        # attempt to find user by phone
        user = User.objects.filter(phone_number=phone).first()
        if user:
            create_and_send_sms_otp(user, phone=phone, ttl_seconds=300, digits=digits)
        print("SMSOTPRequest: requested for phone", phone)
        return Response({"detail": "If this phone is registered, an OTP will be sent."}, status=200)

class SMSOTPVerifyView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SMSOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]
        otp = SMSOTP.objects.filter(phone=phone, code=code).order_by("-created_at").first()
        if not otp or not otp.is_valid():
            print("SMSOTPVerify: invalid", phone, code)
            return Response({"detail":"Invalid or expired code."}, status=400)
        otp.verified = True
        otp.save(update_fields=["verified"])
        user = otp.user
        print(f"SMSOTPVerify: success for {user.email}")
        from .serializers import JWTSerializer
        payload = JWTSerializer.for_user(user)
        return Response(payload, status=200)

# ---------------------
# TOTP (authenticator apps)
# ---------------------
class TOTPSetupBeginView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # generate secret and return otpauth URL for QR code
        secret = generate_totp_secret()
        # store secret on user profile or MFAMethod (ensure encrypted in prod)
        request.user.mfa_methods.filter(type="TOTP").delete()
        from .models import MFAMethod
        m = MFAMethod.objects.create(user=request.user, type="TOTP", secret=secret, enabled=False, label="Authenticator app")
        otpauth_url = pyotp.totp.TOTP(secret).provisioning_uri(name=request.user.email, issuer_name=getattr(settings, "SITE_NAME", "MySite"))
        print(f"TOTPSetupBegin: secret for {request.user.email} secret={secret}")
        return Response({"secret": secret, "otpauth_url": otpauth_url}, status=200)

class TOTPConfirmView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TOTPConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]
        method = request.user.mfa_methods.filter(type="TOTP").first()
        if not method:
            print("TOTPConfirm: no totp method found for", request.user.email)
            return Response({"detail":"TOTP not setup."}, status=400)
        totp = pyotp.TOTP(method.secret)
        if not totp.verify(code):
            print("TOTPConfirm: invalid code for", request.user.email)
            return Response({"detail":"Invalid code."}, status=400)
        method.enabled = True
        method.save(update_fields=["enabled"])
        print("TOTPConfirm: enabled TOTP for", request.user.email)
        return Response({"detail":"TOTP enabled"}, status=200)

# ---------------------
# Backup codes
# ---------------------
class BackupCodesGenerateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BackupCodesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = serializer.validated_data["count"]
        codes = backup_codes_for_user(request.user, count)
        print(f"BackupCodesGenerate: created {len(codes)} for {request.user.email}")
        return Response({"codes": codes}, status=201)

class BackupCodeVerifyView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = BackupCodeVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]
        bc = BackupCode.objects.filter(code=code, used=False).first()
        if not bc:
            print("BackupCodeVerify: invalid", code)
            return Response({"detail":"Invalid backup code."}, status=400)
        bc.used = True
        bc.save(update_fields=["used"])
        print("BackupCodeVerify: success for user", bc.user.email)
        from .serializers import JWTSerializer
        payload = JWTSerializer.for_user(bc.user)
        return Response(payload, status=200)

# ---------------------
# WebAuthn / Passkeys (stubs)
# ---------------------
class WebAuthnRegisterBeginView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WebAuthnBeginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        label = serializer.validated_data.get("label", "")
        # TODO: integrate with python-fido2 or webauthn lib to build challenge & options
        challenge = secrets.token_urlsafe(16)
        # store challenge in session or DB
        request.session["webauthn_register_challenge"] = challenge
        print("WebAuthnRegisterBegin: challenge created for", request.user.email, "challenge:", challenge)
        return Response({"challenge": challenge, "rp": {"name": getattr(settings,"SITE_NAME","MySite")}}, status=200)

class WebAuthnRegisterCompleteView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WebAuthnCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data["credential"]
        # TODO: verify with library; here we only record stub
        WebAuthnCredential.objects.create(
            user=request.user,
            credential_id=b"stub",
            public_key=b"stub",
            sign_count=0,
            label=credential.get("label","device")
        )
        print("WebAuthnRegisterComplete: saved credential for", request.user.email)
        return Response({"detail":"WebAuthn registration complete"}, status=200)

class WebAuthnAuthBeginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Accept email to start auth
        email = request.data.get("email")
        user = User.objects.filter(email=email).first()
        if not user:
            print("WebAuthnAuthBegin: user not found", email)
            return Response({"detail":"If the account exists, challenge created."}, status=200)
        challenge = secrets.token_urlsafe(16)
        request.session["webauthn_auth_challenge"] = challenge
        print("WebAuthnAuthBegin: challenge for", email, challenge)
        return Response({"challenge": challenge}, status=200)

class WebAuthnAuthCompleteView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Validate attestation with lib in prod
        # For now accept and return JWT if matched
        email = request.data.get("email")
        user = User.objects.filter(email=email).first()
        if not user:
            print("WebAuthnAuthComplete: user missing", email)
            return Response({"detail":"Invalid"}, status=400)
        print("WebAuthnAuthComplete: success for", email)
        from .serializers import JWTSerializer
        return Response(JWTSerializer.for_user(user), status=200)


class AuthPolicyViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AuthPolicySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return AuthPolicy.objects.all()
        return AuthPolicy.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)



from .serializers import SecurityPhraseSerializer, SecurityPhraseUpdateSerializer

class SetSecurityPhraseView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SecurityPhraseSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Security phrase set successfully."}, status=200)


class UpdateSecurityPhraseView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SecurityPhraseUpdateSerializer

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(instance=None)
        return Response({"detail": "Security phrase updated successfully."}, status=200)




class LinkedAccountsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        accounts = SocialAccount.objects.filter(user=request.user)
        return Response([{"provider": a.provider, "uid": a.uid, "extra": a.extra_data} for a in accounts])

class UnlinkAccountView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, provider):
        SocialAccount.objects.filter(user=request.user, provider=provider).delete()
        return Response({"detail": f"{provider} account unlinked."})


class GoogleLoginJWTView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        account = SocialAccount.objects.filter(provider="google", user__email=email).first()
        if not account:
            return Response({"detail": "No linked Google account."}, status=400)
        user = account.user
        payload = JWTSerializer.for_user(user)
        return Response(payload, status=200)
