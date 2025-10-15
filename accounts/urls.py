# accounts/urls.py
from django.urls import path
from .views import (
    RegisterView, UnlinkAccountView, VerifyEmailView,
    ForgotPasswordView, ResetPasswordView,
    LoginView, LogoutView, MeView,
    MagicLinkRequestView, MagicLinkConsumeView,
    TOTPSetupBeginView, TOTPConfirmView, MFAVerifyView,
    ResendVerificationEmailView,  # 👈 resend email endpoint
    AccountLockView,  # 👈 import AccountLockView
    AccountUnlockView, AccountDisableView, AccountEnableView,
    AccountSoftDeleteView, AccountRestoreView, AccountHardDeleteView,
    SuspendAccountView, ReAuthView,
    RequestDeleteAccountView,LinkedAccountsView,
    CancelDeleteAccountView,
    HardDeleteAccountView, VerifyEmailKeyView
)

urlpatterns = [
    # Core registration 
    path("register/", RegisterView.as_view(), name="register"),
    path("social/accounts/", LinkedAccountsView.as_view(), name="linked-accounts"),
    path("social/unlink/<str:provider>/", UnlinkAccountView.as_view(), name="unlink-account"),

    # Login/Logout
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # Current user info
    path("me/", MeView.as_view(), name="me"),

    # Email flows
    path("email/verify/", VerifyEmailView.as_view(), name="email-verify"),
    path("resend-verification/", ResendVerificationEmailView.as_view(), name="resend-verification"),
    path("verify-email/<str:key>/", VerifyEmailKeyView.as_view(), name="verify-email-key"),

    # Password reset flows
    path("password/forgot/", ForgotPasswordView.as_view(), name="password-forgot"),
    path("password/reset/", ResetPasswordView.as_view(), name="password-reset"),

    # Passwordless magic links
    path("magic/request/", MagicLinkRequestView.as_view(), name="magic-request"),
    path("magic/consume/", MagicLinkConsumeView.as_view(), name="magic-consume"),

    # TOTP MFA
    path("mfa/totp/setup-begin/", TOTPSetupBeginView.as_view(), name="totp-setup-begin"),
    path("mfa/totp/confirm/", TOTPConfirmView.as_view(), name="totp-confirm"),
    path("mfa/verify/", MFAVerifyView.as_view(), name="mfa-verify"),
]


from .views import ChangePasswordView

urlpatterns += [
    path("password/change/", ChangePasswordView.as_view(), name="password-change"),
]


urlpatterns += [
    path("accounts/<int:user_id>/lock/", AccountLockView.as_view(), name="account-lock"),
    path("accounts/<int:user_id>/unlock/", AccountUnlockView.as_view(), name="account-unlock"),
    path("accounts/<int:user_id>/disable/", AccountDisableView.as_view(), name="account-disable"),
    path("accounts/<int:user_id>/enable/", AccountEnableView.as_view(), name="account-enable"),
    path("accounts/<int:user_id>/soft-delete/", AccountSoftDeleteView.as_view(), name="account-soft-delete"),
    path("accounts/<int:user_id>/restore/", AccountRestoreView.as_view(), name="account-restore"),
    path("accounts/<int:user_id>/hard-delete/", AccountHardDeleteView.as_view(), name="account-hard-delete"),
]

from .views_admin import unlock_user, AccountActionView  # 👈 import the view
urlpatterns += [
    path("unlock/", unlock_user, name="unlock-user"),
    path("accounts/<int:user_id>/<str:action>/", AccountActionView.as_view(), name="account-action"),

]



urlpatterns += [
    path("suspend/", SuspendAccountView.as_view(), name="account_suspend"),
    path("request-delete/", RequestDeleteAccountView.as_view(), name="account_request_delete"),
    path("cancel-delete/", CancelDeleteAccountView.as_view(), name="account_cancel_delete"),
    path("api/auth/reauth/", ReAuthView.as_view(), name="reauth"),
    path("delete/", HardDeleteAccountView.as_view(), name="account_delete"),
    
]

from .views import (
    MagicLinkRequestView, MagicLinkConsumeView,
    EmailOTPRequestView, EmailOTPVerifyView,
    SMSOTPRequestView, SMSOTPVerifyView,
    TOTPSetupBeginView, TOTPConfirmView,
    BackupCodesGenerateView, BackupCodeVerifyView,
    WebAuthnRegisterBeginView, WebAuthnRegisterCompleteView,
    WebAuthnAuthBeginView, WebAuthnAuthCompleteView
)

urlpatterns += [
    path("magic/request/", MagicLinkRequestView.as_view(), name="magic-request"),
    path("magic/consume/", MagicLinkConsumeView.as_view(), name="magic-consume"),

    path("otp/email/request/", EmailOTPRequestView.as_view(), name="email-otp-request"),
    path("otp/email/verify/", EmailOTPVerifyView.as_view(), name="email-otp-verify"),

    path("otp/sms/request/", SMSOTPRequestView.as_view(), name="sms-otp-request"),
    path("otp/sms/verify/", SMSOTPVerifyView.as_view(), name="sms-otp-verify"),

    path("mfa/totp/setup-begin/", TOTPSetupBeginView.as_view(), name="totp-setup-begin"),
    path("mfa/totp/confirm/", TOTPConfirmView.as_view(), name="totp-confirm"),

    path("mfa/backup-codes/generate/", BackupCodesGenerateView.as_view(), name="backup-codes-generate"),
    path("mfa/backup-codes/verify/", BackupCodeVerifyView.as_view(), name="backup-codes-verify"),

    path("webauthn/register/begin/", WebAuthnRegisterBeginView.as_view(), name="webauthn-register-begin"),
    path("webauthn/register/complete/", WebAuthnRegisterCompleteView.as_view(), name="webauthn-register-complete"),
    path("webauthn/auth/begin/", WebAuthnAuthBeginView.as_view(), name="webauthn-auth-begin"),
    path("webauthn/auth/complete/", WebAuthnAuthCompleteView.as_view(), name="webauthn-auth-complete"),
]


# urls.py
from .views import AuthPolicyViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"policies", AuthPolicyViewSet, basename="auth-policy")
urlpatterns += router.urls


from .views import SetSecurityPhraseView, UpdateSecurityPhraseView
urlpatterns += [
    # existing endpoints
    path("security-phrase/set/", SetSecurityPhraseView.as_view(), name="set_security_phrase"),
    path("security-phrase/update/", UpdateSecurityPhraseView.as_view(), name="update_security_phrase"),
]
