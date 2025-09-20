import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_user(db):
    def make_user(email="test@example.com", password="StrongPass123!"):
        user = User.objects.create_user(email=email, password=password, is_active=True)
        return user
    return make_user


# ----------------------
# 🔹 Registration & Login
# ----------------------
@pytest.mark.django_db
def test_register(api_client):
    url = reverse("auth-register")
    response = api_client.post(url, {"email": "new@example.com", "password": "StrongPass123!"}, format="json")
    assert response.status_code == 201
    assert "email" in response.data


@pytest.mark.django_db
def test_login_success(api_client, create_user):
    user = create_user()
    url = reverse("auth-login")
    response = api_client.post(url, {"email": user.email, "password": "StrongPass123!"}, format="json")
    assert response.status_code == 200
    assert "access" in response.data or "token" in response.data


@pytest.mark.django_db
def test_login_failure(api_client):
    url = reverse("auth-login")
    response = api_client.post(url, {"email": "wrong@example.com", "password": "badpass"}, format="json")
    assert response.status_code == 401


# ----------------------
# 🔹 Logout & Me Endpoint
# ----------------------
@pytest.mark.django_db
def test_me_and_logout(api_client, create_user):
    user = create_user()
    login_url = reverse("auth-login")
    login = api_client.post(login_url, {"email": user.email, "password": "StrongPass123!"}, format="json")
    token = login.data.get("access") or login.data.get("token")

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # test /me
    me_url = reverse("auth-me")
    response = api_client.get(me_url)
    assert response.status_code == 200
    assert response.data["email"] == user.email

    # test logout
    logout_url = reverse("auth-logout")
    response = api_client.post(logout_url)
    assert response.status_code in [200, 204]


# ----------------------
# 🔹 Email Verification
# ----------------------
@pytest.mark.django_db
def test_email_verify(api_client, create_user):
    user = create_user()
    url = reverse("auth-email-verify")
    response = api_client.post(url, {"uid": "fakeuid", "token": "faketoken"})
    # should fail gracefully
    assert response.status_code in [400, 401]


# ----------------------
# 🔹 Password Reset
# ----------------------
@pytest.mark.django_db
def test_password_reset_flow(api_client, create_user):
    user = create_user()
    forgot_url = reverse("auth-password-forgot")
    response = api_client.post(forgot_url, {"email": user.email})
    assert response.status_code == 200

    reset_url = reverse("auth-password-reset")
    response = api_client.post(reset_url, {"uid": "fakeuid", "token": "faketoken", "new_password": "NewPass123!"})
    assert response.status_code in [400, 401]


# ----------------------
# 🔹 Magic Links
# ----------------------
@pytest.mark.django_db
def test_magic_link_request_and_consume(api_client, create_user):
    user = create_user()
    request_url = reverse("auth-magic-request")
    response = api_client.post(request_url, {"email": user.email})
    assert response.status_code == 200

    consume_url = reverse("auth-magic-consume")
    response = api_client.post(consume_url, {"uid": "fakeuid", "token": "faketoken"})
    assert response.status_code in [400, 401]


# ----------------------
# 🔹 MFA / TOTP
# ----------------------
@pytest.mark.django_db
def test_mfa_totp_flow(api_client, create_user):
    user = create_user()
    api_client.force_authenticate(user=user)

    # setup
    setup_url = reverse("auth-mfa-totp-setup-begin")
    response = api_client.post(setup_url)
    assert response.status_code == 200
    assert "otpauth_uri" in response.data

    # confirm (wrong code, should fail gracefully)
    confirm_url = reverse("auth-mfa-totp-confirm")
    response = api_client.post(confirm_url, {"code": "000000"})
    assert response.status_code in [400, 401]

    # verify MFA (wrong code)
    verify_url = reverse("auth-mfa-verify")
    response = api_client.post(verify_url, {"uid": "fakeuid", "type": "TOTP", "code": "000000"})
    assert response.status_code in [400, 401]
