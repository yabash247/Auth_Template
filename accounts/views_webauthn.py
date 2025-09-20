
# accounts/views_webauthn.py
# WebAuthn register/authenticate endpoints using 'webauthn' library.
import os
from django.utils import timezone
from rest_framework import views, permissions, status
from rest_framework.response import Response
import json
from webauthn.helpers import options_to_json
from webauthn import (
    generate_registration_options,
    generate_authentication_options,
    verify_registration_response,
    verify_authentication_response,
)
from .models import WebAuthnCredential, User
from .serializers import JWTSerializer

RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
RP_NAME = "AuthTemplate"
ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:8000")

class WebAuthnRegisterBeginView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        options = generate_registration_options(
            rp_id=RP_ID,
            rp_name=RP_NAME,
            user_id=str(request.user.id),
            user_name=request.user.email,
        )
        request.session["current_registration_challenge"] = options.challenge
        return Response(json.loads(options_to_json(options)))

class WebAuthnRegisterCompleteView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            verification = verify_registration_response(
                credential=request.data,
                expected_challenge=request.session.pop("current_registration_challenge"),
                expected_rp_id=RP_ID,
                expected_origin=ORIGIN,
            )
        except Exception as e:
            return Response({"detail": f"Verification failed: {e}"}, status=400)

        WebAuthnCredential.objects.create(
            user=request.user,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            label=request.data.get("label", "Security Key"),
        )
        return Response({"detail": "WebAuthn credential registered"})

class WebAuthnAuthBeginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user = User.objects.filter(email=request.data.get("email")).first()
        if not user:
            return Response({"detail": "User not found"}, status=400)
        creds = WebAuthnCredential.objects.filter(user=user)
        options = generate_authentication_options(
            rp_id=RP_ID,
            allow_credentials=[{"id": c.credential_id, "type": "public-key"} for c in creds],
        )
        request.session["current_auth_challenge"] = options.challenge
        request.session["auth_user_id"] = str(user.id)
        return Response(json.loads(options_to_json(options)))

class WebAuthnAuthCompleteView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user_id = request.session.get("auth_user_id")
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=400)

        try:
            verification = verify_authentication_response(
                credential=request.data,
                expected_challenge=request.session.pop("current_auth_challenge"),
                expected_rp_id=RP_ID,
                expected_origin=ORIGIN,
                credential_public_key=user.webauthn_credentials.first().public_key,
                credential_current_sign_count=user.webauthn_credentials.first().sign_count,
            )
        except Exception as e:
            return Response({"detail": f"Verification failed: {e}"}, status=400)

        cred = user.webauthn_credentials.first()
        cred.sign_count = verification.new_sign_count
        cred.save(update_fields=["sign_count"])

        payload = JWTSerializer.for_user(user)
        return Response(payload)
