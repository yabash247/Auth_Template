# utils/security.py
from django.core.exceptions import PermissionDenied
from django.conf import settings
from ipware import get_client_ip
import time

# Simple in-memory rate limit cache (replace with Redis in prod)
RATE_LIMIT = {}

def enforce_https(request):
    if not request.is_secure():
        print("🚨 [SECURITY] Attempted insecure request:", request.build_absolute_uri())
        raise PermissionDenied("HTTPS required")

def check_rate_limit(identifier, max_attempts=5, window_seconds=60):
    now = time.time()
    attempts = RATE_LIMIT.get(identifier, [])
    # keep only recent attempts
    attempts = [t for t in attempts if now - t < window_seconds]
    if len(attempts) >= max_attempts:
        print(f"🚨 [RATE LIMIT] Too many attempts for {identifier}")
        raise PermissionDenied("Too many requests, slow down")
    attempts.append(now)
    RATE_LIMIT[identifier] = attempts

def log_device_fingerprint(request, user):
    ip, _ = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")[:250]
    last_login = getattr(user, "last_login_ip", None)
    if last_login and (last_login != ip):
        print(f"⚠️ [SECURITY] New IP detected for {user.email}: {ip} (was {last_login})")
        # TODO: send email alert
    user.last_login_ip = ip
    user.last_login_ua = ua
    user.save(update_fields=["last_login_ip", "last_login_ua"])
    print(f"🖥️ [SECURITY] Logged device for {user.email}: IP={ip}, UA={ua[:50]}...")