"""
Base settings for the Auth Template.

Split settings by concern to keep things maintainable:
- auth.py: DRF, JWT, allauth, OTP, rate limits
- security.py: CSP, HSTS, cookies, CSRF, SECURE_* flags
- email_sms.py: email/SMS providers
- logging.py: logging configuration

Override with environment-specific modules (dev.py, staging.py, prod.py).
"""

from pathlib import Path
import environ, os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Environment helper
env = environ.Env(
    DEBUG=(bool, True),
    AUTH_USE_JWT=(bool, True),
)

# Default env loader (dev fallback)
default_env_path = os.path.join(BASE_DIR, "env", ".env.dev")
if os.path.exists(default_env_path):
    environ.Env.read_env(default_env_path)

# Core settings
DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# Database (SQLite by default, overridden per env)
DATABASES = {"default": env.db(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

# Installed apps
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "rest_framework.authtoken",
    "corsheaders",
    "axes",

    # Auth feature apps
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "two_factor",

    # Local apps
    "accounts",
    "organizations",
]

SITE_ID = 1
AUTH_USER_MODEL = "accounts.User"  # ✅ Custom user model

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",          # Brute force protection
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_otp.middleware.OTPMiddleware",     # OTP sessions
    "allauth.account.middleware.AccountMiddleware",  # Required for allauth
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {
        "NAME": "django_password_validators.password_character_requirements.password_validation.PasswordCharacterValidator",
        "OPTIONS": {
            "min_length_digit": 1,
            "min_length_alpha": 1,
            "min_length_special": 1,
            "min_length_upper": 1,
        },
    },
]

# CORS
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=True)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static & Media
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Import concern-specific settings
from .auth import *     # JWT/DRF/allauth/axes/otp
from .security import * # Cookies/HSTS/CSRF
from .email_sms import *# Email/SMS (console by default)
from .logging import *  # Logging
