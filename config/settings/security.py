"""
Security & cookie settings.
These should be hardened in production.
"""

# Cookies
SESSION_COOKIE_SECURE = False   # True in production
CSRF_COOKIE_SECURE = False      # True in production
CSRF_TRUSTED_ORIGINS = []       # Add frontend domain(s) in prod, e.g. ["https://myapp.com"]

# HSTS (force HTTPS in browsers)
SECURE_HSTS_SECONDS = 0         # > 31536000 in production (1 year)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Other headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
