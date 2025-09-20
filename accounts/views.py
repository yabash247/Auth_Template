from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django_otp import devices_for_user
from ipware import get_client_ip
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
import pyotp, secrets

from .models import User, LoginActivity, MFAMethod, BackupCode
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, JWTSerializer
from .tokens import email_verification_token, magic_link_token, password_reset_token
from .utils import send_verification_email, send_password_reset_email, send_magic_link_email, generate_backup_codes
from .policy import resolve_policy

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
        # Send email verification token
        token = email_verification_token.make_token(user)
        send_verification_email(user, token)

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

# ---------- Password flows ----------
class ForgotPasswordView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "If account exists, you will receive an email"}, status=200)
        token = password_reset_token.make_token(user)
        send_password_reset_email(user, token)
        return Response({"detail": "If account exists, you will receive an email"}, status=200)

class ResetPasswordView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return Response({"detail": "Invalid user"}, status=400)
        if not password_reset_token.check_token(user, token):
            return Response({"detail": "Invalid or expired token"}, status=400)
        user.set_password(new_password)
        user.must_change_password = False
        user.save()
        return Response({"detail": "Password reset successful"})

# ---------- Login / JWT issuance (with policy & optional MFA step) ----------
class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Basic authenticate
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Check policy (example: require email verification)
        policy = resolve_policy(user, org_id=request.data.get("org_id"))
        if policy.require_email_verification and not user.is_email_verified:
            return Response({"detail": "Email verification required"}, status=403)

        # If MFA is enabled for user, require step-up unless already satisfied
        has_mfa = user.mfa_methods.filter(enabled=True).exists()
        if has_mfa and not request.data.get("mfa_ok"):
            # Signal to client to perform MFA
            _log_login(user, request, ok=False, method="password", mfa_used=False)
            return Response({"mfa_required": True, "methods": list(user.mfa_methods.filter(enabled=True).values_list("type", flat=True))}, status=200)

        # Issue tokens
        payload = JWTSerializer.for_user(user)
        login(request, user)  # Optional session
        _log_login(user, request, ok=True, method="password", mfa_used=has_mfa)
        return Response(payload)

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
class MagicLinkRequestView(views.APIView):
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

class MagicLinkConsumeView(views.APIView):
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
