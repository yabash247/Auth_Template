from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from allauth.account.utils import send_email_confirmation


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

    def get_email_confirmation_url(self, request, emailconfirmation):
        """
        Build a proper confirmation URL (instead of example.com).
        """
        print("🚀 Using CustomAccountAdapter.get_email_confirmation_url")
        frontend_url = getattr(settings, "FRONTEND_URL", "http://127.0.0.1:3000")
        # If you want Django to handle it:
        return f"{frontend_url}/accounts/confirm-email/{emailconfirmation.key}/"
        # If you want React to handle it instead:
        # return f"{frontend_url}/verify-email/{emailconfirmation.key}/"

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        # Force using our custom URL
        activate_url = self.get_email_confirmation_url(request, emailconfirmation)
        ctx = {
            "user": emailconfirmation.email_address.user,
            "activate_url": activate_url,
            "site_name": "Auth Template",
        }
        #self.send_mail("emails/verify_email", emailconfirmation.email_address.email, ctx)
        subject = f"Verify your email for {ctx['site_name']}"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = emailconfirmation.email_address.email

        text_body = render_to_string("emails/verify_email.txt", ctx)
        html_body = render_to_string("emails/verify_email.html", ctx)

        msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()

    def send_mail_confirmation(self, request, emailconfirmation, signup):
        return self.send_confirmation_mail(request, emailconfirmation, signup)



    def confirm_email(self, request, email_address: EmailAddress):
        """
        Ensure email gets marked as verified when user clicks confirmation link.
        """
        email_address.verified = True
        email_address.set_as_primary()
        email_address.save()

        # Flip user’s flag too
        user = email_address.user
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        return super().confirm_email(request, email_address)
    
    
    def get_password_reset_url(self, request, uid, token):
        """
        Custom reset password link.
        """
        frontend_url = getattr(settings, "FRONTEND_URL", "http://127.0.0.1:3000")
        return f"{frontend_url}/reset-password?uid={uid}&token={token}"

    class ResendVerificationEmailView(APIView):
        permission_classes = [permissions.AllowAny]

        def post(self, request):
            email = request.data.get("email")

            if request.user.is_authenticated:
                user = request.user
            elif email:
                from accounts.models import User
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    return Response({"detail": "User not found"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"detail": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Ensure EmailAddress exists
            email_address, created = EmailAddress.objects.get_or_create(user=user, email=user.email)

            if email_address.verified:
                return Response({"detail": "Email is already verified."}, status=status.HTTP_400_BAD_REQUEST)

            # 🔑 Send the email using allauth
            send_email_confirmation(request, user, signup=False)

            return Response({"detail": "Verification email resent."}, status=status.HTTP_200_OK)

