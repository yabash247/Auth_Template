from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm

class CustomPasswordResetForm(PasswordResetForm):
    """
    Override the default to build reset URLs with FRONTEND_URL.
    """
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        uid = context["uid"]
        token = context["token"]
        frontend_url = getattr(settings, "FRONTEND_URL", "http://127.0.0.1:3000")
        reset_url = f"{frontend_url}/reset-password?uid={uid}&token={token}"

        # overwrite the link in context
        context["password_reset_url"] = reset_url  

        super().send_mail(
            subject_template_name, email_template_name,
            context, from_email, to_email, html_email_template_name
        )
