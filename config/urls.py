from django.contrib import admin
from django.urls import path, include
from accounts.views import CustomConfirmEmailView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Registration only from dj-rest-auth
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),

    # Our custom accounts API
    path("api/auth/", include("accounts.urls")),

    # allauth email confirmation
    path("accounts/", include("allauth.urls")),
    path("accounts/confirm-email/<str:key>/", CustomConfirmEmailView.as_view(),
         name="account_confirm_email"),
]
