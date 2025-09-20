"""
Authentication & API related settings:
- DRF, JWT (SimpleJWT)
- allauth (email verification, social providers)
- axes (brute force protection)
- otp/two-factor scaffolding (TOTP)
- cors
"""
from datetime import timedelta
import os

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "otp_send": "5/min",
        "otp_verify": "10/min",
        "password_reset": "5/min",
        "magic_link": "5/min",
    },
}

# config/settings/auth.py
LOGIN_URL = "/accounts/login/"
ADMIN_LOGIN_URL = "/admin/login/"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.environ.get("JWT_SIGNING_KEY", os.environ.get("SECRET_KEY", "dev-secret")),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# === Allauth config ===
ACCOUNT_USER_MODEL_USERNAME_FIELD = None   # No username field in custom User
ACCOUNT_AUTHENTICATION_METHOD = "email"    # Login with email only
ACCOUNT_EMAIL_REQUIRED = True              # Require email
ACCOUNT_USERNAME_REQUIRED = False          # Don't generate usernames
ACCOUNT_UNIQUE_EMAIL = True                # Ensure unique emails

ACCOUNT_ADAPTER = "accounts.adapter.CustomAccountAdapter"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

# Redirects after login/logout
LOGIN_REDIRECT_URL = "/app/"
LOGOUT_REDIRECT_URL = "/"

# Development: print emails in console
#EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Production example (with SendGrid via django-anymail)
# EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"
# ANYMAIL = {"SENDGRID_API_KEY": env("SENDGRID_API_KEY")}


# dj-rest-auth will use SimpleJWT automatically

# Axes (brute force protection)
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 30  # minutes

# OTP / Two Factor: two_factor app provides views; we use our own API stubs
# CORS (tighten in prod)
CORS_ALLOW_ALL_ORIGINS = True


# === Social Login: Google Example ===
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["email", "profile"],
        "AUTH_PARAMS": {"access_type": "offline"},
    }
}


AUTHENTICATION_BACKENDS = (
    # Axes must be first so it can intercept failed logins
    "axes.backends.AxesStandaloneBackend",

    # Default Django auth
    "django.contrib.auth.backends.ModelBackend",

    # Allauth (for social logins)
    "allauth.account.auth_backends.AuthenticationBackend",
)
