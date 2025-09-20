from django.urls import path
from .views import (
    RegisterView, VerifyEmailView,
    ForgotPasswordView, ResetPasswordView,
    LoginView, LogoutView, MeView,
    MagicLinkRequestView, MagicLinkConsumeView,
    TOTPSetupBeginView, TOTPConfirmView, MFAVerifyView
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("email/verify/", VerifyEmailView.as_view(), name="email-verify"),
    path("password/forgot/", ForgotPasswordView.as_view(), name="password-forgot"),
    path("password/reset/", ResetPasswordView.as_view(), name="password-reset"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),

    path("magic/request/", MagicLinkRequestView.as_view(), name="magic-request"),
    path("magic/consume/", MagicLinkConsumeView.as_view(), name="magic-consume"),

    path("mfa/totp/setup-begin/", TOTPSetupBeginView.as_view(), name="totp-setup-begin"),
    path("mfa/totp/confirm/", TOTPConfirmView.as_view(), name="totp-confirm"),
    path("mfa/verify/", MFAVerifyView.as_view(), name="mfa-verify"),
]


from .views_webauthn import (
    WebAuthnRegisterBeginView, WebAuthnRegisterCompleteView,
    WebAuthnAuthBeginView, WebAuthnAuthCompleteView,
)

urlpatterns += [
    path("webauthn/register/begin/", WebAuthnRegisterBeginView.as_view()),
    path("webauthn/register/complete/", WebAuthnRegisterCompleteView.as_view()),
    path("webauthn/auth/begin/", WebAuthnAuthBeginView.as_view()),
    path("webauthn/auth/complete/", WebAuthnAuthCompleteView.as_view()),
]
