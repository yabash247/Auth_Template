from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .tokens import email_verification_token
from .utils import send_verification_email

User = get_user_model()

@receiver(post_save, sender=User)
def send_verify_on_create(sender, instance, created, **kwargs):
    if created and instance.email:
        token = email_verification_token.make_token(instance)
        send_verification_email(instance, token)
