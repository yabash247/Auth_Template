import hashlib, qrcode
from io import BytesIO
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from datetime import datetime

# accounts/utils.py
import secrets, string
from django.utils import timezone
from datetime import timedelta
from django.template.loader import render_to_string

import pyotp

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

def notify_user(user, action, by_admin=True):
    """
    Sends email notification to user about account events (lock, delete, suspend, etc.).
    Automatically logs event to AuthRequestLog.
    """
    print(f"🔔 [TRACE] notify_user triggered for {user.email} | action={action} | by_admin={by_admin}")

    subject = f"Account {action.replace('_',' ').title()}"
    revert_msg = ""

    # Only include revert/cancel link if action is initiated by user
    if not by_admin and action in ["suspended", "soft_deleted", "delete_requested"]:
        revert_msg = (
            "\n\nIf this wasn’t you, click here to cancel: "
            f"{settings.FRONTEND_URL}/account/cancel/{action}?uid={user.id}"
        )

    message = f"""
Hello {user.email},

Your account has been {action.replace('_',' ')}.

{revert_msg}

If you did not authorize this, please contact support immediately.
"""

    # Log the process
    print(f"📧 [TRACE] Preparing to send email to {user.email}")
    print(f"📨 [TRACE] Email subject: {subject}")
    print(f"📝 [TRACE] Email body:\n{message}")

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        print(f"✅ [SUCCESS] Email successfully sent to {user.email}")
    except Exception as e:
        print(f"❌ [ERROR] Failed to send email to {user.email}: {e}")

    # Lazy import to avoid circular import
    try:
        from accounts.models import AuthRequestLog
        AuthRequestLog.objects.create(
            user=user,
            action=action,
            ip_address="system",  # Replace later if you track IPs
            user_agent="system",
            timestamp=datetime.now(),
            success=True,
            message=f"Notification sent for action={action}",
        )
        print(f"🧾 [TRACE] AuthRequestLog entry created for {user.email} (action={action})")
    except Exception as e:
        print(f"⚠️ [ERROR] Failed to log AuthRequestLog entry: {e}")



def generate_token(length=48):
    token = secrets.token_urlsafe(length)
    print(f"[util] generate_token -> {token[:16]}... (len={len(token)})")
    return token

def generate_numeric_code(digits=6):
    code = ''.join(secrets.choice(string.digits) for _ in range(digits))
    print(f"[util] generate_numeric_code -> {code}")
    return code

def create_magic_link(user, ttl_seconds=600, request=None):
    from .models import MagicLink
    token = generate_token(24)
    expires = timezone.now() + timedelta(seconds=ttl_seconds)
    ml = MagicLink.objects.create(user=user, token=token, expires_at=expires,
                                  ip=(request.META.get("REMOTE_ADDR") if request else None),
                                  user_agent=(request.META.get("HTTP_USER_AGENT","") if request else ""))
    print(f"[util] MagicLink created for user {user.email} token={token} expires={expires}")
    return ml

def send_magic_email(user, magic_link, subject="Login link", template_txt="emails/magic_link.txt", template_html="emails/magic_link.html"):
    # Always HTTPS
    base_url = getattr(settings, "FRONTEND_URL", "https://yourdomain.com")
    if base_url.startswith("http://"):
        print("⚠️ [SECURITY] Magic link attempted with HTTP. Forcing HTTPS.")
        base_url = base_url.replace("http://", "https://")

    activate_url = f"{base_url}/magic/consume/?token={magic_link.token}"
    print(f"[util] Sending magic link to {user.email} (expires {magic_link.expires_at}) URL={activate_url}")

    context = {"user": user, "activate_url": activate_url}
    text = render_to_string(template_txt, context)
    html = render_to_string(template_html, context)
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.attach_alternative(html, "text/html")
    msg.send()
    print(f"[util] Sent magic email to {user.email} url={activate_url}")

def create_and_send_email_otp(user, ttl_seconds=300, digits=6, purpose="login"):
    from .models import EmailOTP
    code = generate_numeric_code(digits)
    expires = timezone.now() + timedelta(seconds=ttl_seconds)
    otp = EmailOTP.objects.create(user=user, code=code, expires_at=expires, purpose=purpose)
    send_mail(subject="Your verification code", message=f"Your code is {code}", from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[user.email])
    print(f"[util] Created EmailOTP for {user.email} code={code} expires={expires}")
    return otp

def create_and_send_sms_otp(user, phone, ttl_seconds=300, digits=6):
    from .models import SMSOTP
    code = generate_numeric_code(digits)
    expires = timezone.now() + timedelta(seconds=ttl_seconds)
    otp = SMSOTP.objects.create(user=user, code=code, expires_at=expires, phone=phone)
    # STUB: replace with Twilio or other provider
    print(f"[util] (STUB) Sending SMS to {phone}: code={code}")
    # Example Twilio: client.messages.create(body=f"Your code: {code}", from_=TWILIO_FROM, to=phone)
    return otp

def generate_totp_secret():
    secret = pyotp.random_base32()
    print(f"[util] Generated TOTP secret -> {secret}")
    return secret

def backup_codes_for_user(user, count=10):
    from .models import BackupCode
    # Plain codes for dev; hash in prod.
    codes = []
    for _ in range(count):
        code = secrets.token_hex(4)
        BackupCode.objects.create(user=user, code=code)
        codes.append(code)
    print(f"[util] Created {len(codes)} backup codes for {user.email}")
    return codes


def check_rate_limit(email=None, phone=None, user=None, ip=None, limit=5, seconds=300, action="unknown"):
    """
    Checks if user/email/phone/ip has exceeded rate limits for a specific action.
    Returns (True, None) if under limit, (False, reason) if exceeded.
    """

    print(f"⚙️ [TRACE] check_rate_limit called → user={user}, email={email}, phone={phone}, ip={ip}, action={action}")

    try:
        # Lazy import prevents circular dependency
        from accounts.models import AuthRequestLog
    except Exception as e:
        print(f"⚠️ [ERROR] Could not import AuthRequestLog: {e}")
        return True, "Rate limit check skipped due to import error."

    cutoff = timezone.now() - timedelta(seconds=seconds)

    # Build query
    qs = AuthRequestLog.objects.filter(timestamp__gte=cutoff, action=action)
    if user:
        qs = qs.filter(user=user)
    elif email:
        qs = qs.filter(message__icontains=email)
    elif phone:
        qs = qs.filter(message__icontains=phone)
    if ip:
        qs = qs.filter(ip_address=ip)

    count = qs.count()
    print(f"⏱️ [RATE LIMIT] Found {count}/{limit} '{action}' requests in last {seconds}s for {email or phone or user or ip}")

    if count >= limit:
        msg = f"Rate limit exceeded for {action}. Try again later."
        print(f"🚫 [RATE LIMIT BLOCK] {msg}")
        return False, msg

    return True, None


def log_request(user=None, email=None, phone=None, request=None, action="unknown", success=True, message=""):
    """
    Logs authentication or security-related events (e.g., OTP, magic link, rate limit).
    Lazy imports AuthRequestLog to avoid circular dependencies.
    """

    print(f"📝 [TRACE] Logging AuthRequestLog entry → user={user}, email={email}, phone={phone}, action={action}")

    try:
        # Lazy import to prevent circular reference
        from accounts.models import AuthRequestLog

        AuthRequestLog.objects.create(
            user=user,
            action=action,
            ip_address=getattr(request, "META", {}).get("REMOTE_ADDR", "system") if request else "system",
            user_agent=getattr(request, "META", {}).get("HTTP_USER_AGENT", "system") if request else "system",
            timestamp=datetime.now(),
            success=success,
            message=message or f"Security event: {action}",
        )

        print(f"✅ [TRACE] AuthRequestLog created successfully for action={action}")

    except Exception as e:
        print(f"⚠️ [ERROR] Failed to log AuthRequestLog entry for action={action}: {e}")


# accounts/utils.py

# --------------------------------------------
# Adaptive Authentication Policy Evaluation
# --------------------------------------------
def get_required_methods(user, action):
    """
    Determine which authentication methods must be verified for a given action.
    Priority: Admin (mandatory) > Admin (advisory) > User Policy > Default
    """
    from .models import AuthPolicy

    print(f"🔎 1. [TRACE] get_required_methods called for user={user.email} action={action}")

    DEFAULT_REQUIREMENTS = {
        "login": ["password"],
        "profile_edit": ["password"],
        "delete_account": ["password", "security_phrase"],
        "sensitive_ops": ["password", "otp"],
    }

    required = set(DEFAULT_REQUIREMENTS.get(action, []))

    # Always pick the latest active record
    global_policy = AuthPolicy.objects.filter(scope="global", is_active=True).order_by("-updated_at").first()
    user_policy = AuthPolicy.objects.filter(user=user, is_active=True).order_by("-updated_at").first()
    print(f"🔎 1. [TRACE] get_required_methods called for user={user.email} action={action}")

    # If admin global policy is mandatory → overrides everything
    if global_policy and global_policy.is_mandatory:
        methods = global_policy.applicable_methods.get(action, [])
        print("🔒 Using mandatory global policy")
        return methods
    
    # --- Merge admin advisory (global) + user-selected (if allowed) ---
    print(f"🔎 [TRACE] Evaluating auth policy for user={user.email} action={action}")

    if global_policy: 
        global_methods = global_policy.applicable_methods.get(action, [])
        print(f"🔎 [TRACE] Found global policy (ID={global_policy.id}) methods={global_methods}")
        required.update(global_policy.get_methods_for(action))

    if user_policy:
        user_methods = user_policy.selected_methods.get(action, [])
        print(f"🔎 3. [TRACE] Found user policy (ID={user_policy.id}) selected_methods={user_methods}")
        required.update(user_methods)

    else:
        print("🚫 [TRACE] No user policy found for user")

    final_methods = list(required)
    print(f"🔎 4. [TRACE] Final required methods for {user.email}: {final_methods}")
    return final_methods
