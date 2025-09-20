from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Add this 👇 for admin login page to work
    path("accounts/", include("django.contrib.auth.urls")),

    # dj-rest-auth endpoints (register, login, logout, etc.)
    path("api/auth/", include("dj_rest_auth.urls")),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),

    # allauth account management (needed for /accounts/login/, password reset, etc.)
    path("accounts/", include("allauth.urls")),
]
