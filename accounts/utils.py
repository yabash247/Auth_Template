import hashlib, os, base64, qrcode
from io import BytesIO
from django.core.mail import send_mail
from django.conf import settings

def send_verification_email(user, token):
    link = f"https://example.com/verify-email?uid={user.pk}&token={token}"
    send_mail("Verify your email", f"Click to verify: {link}", settings.DEFAULT_FROM_EMAIL, [user.email])

def send_password_reset_email(user, token):
    link = f"https://example.com/reset-password?uid={user.pk}&token={token}"
    send_mail("Reset your password", f"Click to reset: {link}", settings.DEFAULT_FROM_EMAIL, [user.email])

def send_magic_link_email(user, token):
    link = f"https://example.com/magic-login?uid={user.pk}&token={token}"
    send_mail("Your magic login link", f"Click to sign in: {link}", settings.DEFAULT_FROM_EMAIL, [user.email])

def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def generate_backup_codes(n=10):
    import secrets
    return [secrets.token_urlsafe(8) for _ in range(n)]

def totp_qr_image_uri(otpauth_uri: str) -> bytes:
    img = qrcode.make(otpauth_uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
