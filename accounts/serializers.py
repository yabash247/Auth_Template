from django.contrib.auth import authenticate, password_validation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, LockoutPolicy, AuthPolicy, SecurityPhrase
from datetime import timedelta


from django.utils.timezone import now

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "is_email_verified", "phone_number", "is_phone_verified", "must_change_password", "is_locked"]

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password"]

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user
    
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # email, username, or phone
    password = serializers.CharField(write_only=True)

    print("⚡ LoginSerializer loaded with multi-identifier support")

    @staticmethod
    def _remaining_time(lockout_until):
        seconds = int((lockout_until - now()).total_seconds())
        if seconds < 60:
            return f"{seconds} seconds"
        return f"{seconds // 60} minutes"

    def validate(self, data):
        identifier = data.get("identifier")
        password = data.get("password")
        print(f"🔎 [TRACE] Login attempt with identifier: {identifier}")

        # 1️⃣ Resolve identifier → user
        user = None
        try:
            if "@" in identifier:
                user = User.objects.get(email=identifier)
                print(f"📧 [TRACE] Matched email: {user.email}")
            elif identifier.isdigit():
                user = User.objects.get(phone_number=identifier)
                print(f"📱 [TRACE] Matched phone: {user.phone_number} → {user.email}")
            else:
                user = User.objects.get(username=identifier)
                print(f"👤 [TRACE] Matched username: {user.username} → {user.email}")
        except User.DoesNotExist:
            print("🚫 [TRACE] No user found for identifier:", identifier)
            raise serializers.ValidationError("Invalid credentials")

        # 2️⃣ Admin enforced flags
        if getattr(user, "is_locked", False):
            print(f"🚫 [TRACE] Login blocked: {user.email} is explicitly locked by admin")
            raise serializers.ValidationError("Account is locked. Contact support.")

        if getattr(user, "is_disabled", False):
            print(f"🚫 [TRACE] Login blocked: {user.email} is disabled")
            raise serializers.ValidationError("Account is disabled. Contact support.")

        if getattr(user, "is_soft_deleted", False):
            print(f"🚫 [TRACE] Login blocked: {user.email} is soft-deleted")
            raise serializers.ValidationError("Account is deleted. Contact support.")

        # 3️⃣ Time-based lockout check
        if hasattr(user, "is_locked_out") and user.is_locked_out():
            remaining = self._remaining_time(user.lockout_until)
            print(f"⏳ [TRACE] {user.email} is temporarily locked ({remaining} left)")
            raise serializers.ValidationError(
                f"Account temporarily locked. Try again in {remaining}."
            )

        # 4️⃣ Wrong password → increment failed_attempts
        if not user.check_password(password):
            user.failed_attempts += 1
            policy = LockoutPolicy.objects.filter(active=True).first()
            print(f"❌ [TRACE] Wrong password for {user.email}, failed_attempts={user.failed_attempts}")

            locked = False
            if policy:
                if user.failed_attempts >= policy.threshold3:
                    user.lockout_until = now() + timedelta(seconds=policy.wait3)
                    locked = True
                elif user.failed_attempts >= policy.threshold2:
                    user.lockout_until = now() + timedelta(seconds=policy.wait2)
                    locked = True
                elif user.failed_attempts >= policy.threshold1:
                    user.lockout_until = now() + timedelta(seconds=policy.wait1)
                    locked = True

                print(
                    f"🔒 [TRACE] Policy applied for {user.email}: "
                    f"thresholds=({policy.threshold1},{policy.threshold2},{policy.threshold3}), "
                    f"waits=({policy.wait1},{policy.wait2},{policy.wait3}), "
                    f"lockout_until={user.lockout_until}"
                )
            else:
                print("⚠️ [TRACE] No LockoutPolicy configured.")

            user.save(update_fields=["failed_attempts", "lockout_until"])

            if locked:
                remaining = self._remaining_time(user.lockout_until)
                raise serializers.ValidationError(
                    f"Account locked due to repeated failures. Try again in {remaining}."
                )

            raise serializers.ValidationError("Invalid credentials")

        # 5️⃣ ✅ Password correct → reset lockout
        print(f"✅ [TRACE] Successful password check for {user.email}")
        user.failed_attempts = 0
        user.lockout_until = None
        user.save(update_fields=["failed_attempts", "lockout_until"])

        data["user"] = user
        return data

class ReAuthSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context["request"].user
        if not user.check_password(data["password"]):
            raise serializers.ValidationError("Invalid password for re-authentication")
        return data


class JWTSerializer(serializers.Serializer):

    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)

    @classmethod
    def for_user(cls, user, remember_me=False):
        """
        Generate refresh+access tokens for a user.
        If remember_me=True, extend refresh lifetime.
        """
        refresh = RefreshToken.for_user(user)

        if remember_me:
            refresh.set_exp(lifetime=timedelta(days=30))  # extend validity
            print(f"🔑 [TRACE] Extended refresh token for {user.email} (30 days)")

        access = refresh.access_token
        print(f"🎫 [TRACE] Tokens issued for {user.email}")

        return {
            "user": UserSerializer(user).data,
            "refresh": str(refresh),
            "access": str(access),
            "remember_me": remember_me,
        }



class MagicRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class MagicConsumeSerializer(serializers.Serializer):
    token = serializers.CharField()

class EmailOTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    digits = serializers.IntegerField(default=6, min_value=4, max_value=8)

class EmailOTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()

class SMSOTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField()
    digits = serializers.IntegerField(default=6, min_value=4, max_value=8)

class SMSOTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField()

class TOTPSetupBeginSerializer(serializers.Serializer):
    # returns secret & otpauth_url
    pass

class TOTPConfirmSerializer(serializers.Serializer):
    code = serializers.CharField()

class BackupCodesSerializer(serializers.Serializer):
    count = serializers.IntegerField(default=10, min_value=1, max_value=50)

class BackupCodeVerifySerializer(serializers.Serializer):
    code = serializers.CharField()

# WebAuthn serializers (stubs)
class WebAuthnBeginSerializer(serializers.Serializer):
    label = serializers.CharField(required=False, default="")

class WebAuthnCompleteSerializer(serializers.Serializer):
    credential = serializers.DictField()


# serializers.py
class AuthPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthPolicy
        fields = "__all__"
        read_only_fields = ["user", "updated_at"]


class SecurityPhraseSerializer(serializers.Serializer):
    security_phrase = serializers.CharField(write_only=True, min_length=3, max_length=64)

    def create(self, validated_data):
        user = self.context["request"].user
        phrase = validated_data["security_phrase"]
        phrase_obj, created = SecurityPhrase.objects.get_or_create(user=user)
        phrase_obj.set_phrase(phrase)
        return {"detail": "Security phrase set successfully."}


class SecurityPhraseUpdateSerializer(serializers.Serializer):
    old_phrase = serializers.CharField(write_only=True)
    new_phrase = serializers.CharField(write_only=True, min_length=3, max_length=64)

    def update(self, instance, validated_data):
        user = self.context["request"].user
        old_phrase = validated_data["old_phrase"]
        new_phrase = validated_data["new_phrase"]
        phrase_obj = getattr(user, "security_phrase_policy", None)

        if not phrase_obj or not phrase_obj.verify_phrase(old_phrase):
            raise serializers.ValidationError({"detail": "Old phrase is incorrect."})

        phrase_obj.set_phrase(new_phrase)
        return {"detail": "Security phrase updated successfully."}
