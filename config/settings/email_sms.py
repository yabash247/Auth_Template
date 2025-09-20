

import os

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@yourdomain.com"

# Production example (with SendGrid via django-anymail)
#EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"
#ANYMAIL = {
    #"SENDGRID_API_KEY": os.environ.get("SENDGRID_API_KEY"),
#}




