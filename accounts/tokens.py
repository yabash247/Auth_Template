from django.contrib.auth.tokens import PasswordResetTokenGenerator

# Reuse Django's built token generator mechanics for email verification & magic links.
email_verification_token = PasswordResetTokenGenerator()
magic_link_token = PasswordResetTokenGenerator()
password_reset_token = PasswordResetTokenGenerator()
