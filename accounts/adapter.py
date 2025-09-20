from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter for:
    1. Sending styled HTML email for verification
    2. Marking email as verified on confirmation
    """

    def send_mail(self, template_prefix, email, context):
        """
        Override default send_mail to use our own HTML template.
        """
        subject = f"Verify your email for {context.get('site_name', 'Our App')}"
        from_email = "no-reply@example.com"  # 👈 replace with real sender

        # Render both text and HTML versions
        text_body = render_to_string("emails/verify_email.txt", context)
        html_body = render_to_string("emails/verify_email.html", context)

        msg = EmailMultiAlternatives(subject, text_body, from_email, [email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()

    def confirm_email(self, request, email_address: EmailAddress):
        """
        Ensure email gets marked as verified when user clicks confirmation link.
        """
        email_address.verified = True
        email_address.set_as_primary()
        email_address.save()
        super().confirm_email(request, email_address)
