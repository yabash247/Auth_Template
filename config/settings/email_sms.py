
#EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

import os
from dotenv import load_dotenv

load_dotenv()

# === EMAIL CONFIGURATION ===
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"         # Use your email provider’s SMTP
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "your_email@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "your_app_password")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "no-reply@example.com"

# Optional: Debug logs
print(f"📧 [TRACE] Email backend: {EMAIL_BACKEND}")
print(f"📧 [TRACE] Sending from: {DEFAULT_FROM_EMAIL}")



