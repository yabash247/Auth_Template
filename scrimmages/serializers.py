# scrimmages/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Scrimmage, ScrimmageParticipation, League, LeagueTeam, PerformanceStat, ScrimmageCategory, ScrimmageType, Scrimmage

User = get_user_model()


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email"]


class ScrimmageParticipationSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = ScrimmageParticipation
        fields = ["id", "user", "role", "status", "rating", "notes", "joined_at"]


class ScrimmageSerializer(serializers.ModelSerializer):
    creator = UserMiniSerializer(read_only=True)
    participants = ScrimmageParticipationSerializer(many=True, read_only=True)
    participants_count = serializers.SerializerMethodField()

    class Meta:
        model = Scrimmage
        fields = [
            "id", "slug", "title", "description", "category",
            "creator", "group", "location_name", "address",
            "start_time", "end_time", "is_recurring", "rrule",
            "max_participants", "visibility", "skill_level", "tags",
            "fee_amount", "currency", "requires_membership",
            "status", "participants", "participants_count",
            "created_at", "updated_at"
        ]
        read_only_fields = ["slug", "creator", "created_at", "updated_at"]

    def get_participants_count(self, obj):
        return obj.participants.filter(status__in=["confirmed", "checked_in"]).count()

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        return attrs

    def create(self, validated):
        user = self.context["request"].user
        validated["creator"] = user
        scrim = super().create(validated)
        # Auto-add creator as confirmed participant
        ScrimmageParticipation.objects.get_or_create(user=user, scrimmage=scrim, defaults={"status": "confirmed"})
        return scrim


# scrimmages/serializers.py
from rest_framework import serializers
from .models import (
    ScrimmageTemplate,
    RecurrenceRule,
    Scrimmage,
    ScrimmageType,
    ScrimmageCategory
)


# --- BASE SERIALIZERS (for reference) ---
class ScrimmageCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrimmageCategory
        fields = ["id", "name", "slug"]


class ScrimmageTypeSerializer(serializers.ModelSerializer):
    category = ScrimmageCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=ScrimmageCategory.objects.all(), write_only=True
    )

    class Meta:
        model = ScrimmageType
        fields = ["id", "name", "slug", "category", "category_id", "custom_field_schema"]


class ScrimmageSerializer(serializers.ModelSerializer):
    scrimmage_type = ScrimmageTypeSerializer(read_only=True)
    scrimmage_type_id = serializers.PrimaryKeyRelatedField(
        source="scrimmage_type", queryset=ScrimmageType.objects.all(), write_only=True
    )

    class Meta:
        model = Scrimmage
        fields = "__all__"
        read_only_fields = ("slug", "created_at", "updated_at")


# --- NEW: TEMPLATE SERIALIZER ---
class ScrimmageTemplateSerializer(serializers.ModelSerializer):
    scrimmage_type = ScrimmageTypeSerializer(read_only=True)
    scrimmage_type_id = serializers.PrimaryKeyRelatedField(
        source="scrimmage_type", queryset=ScrimmageType.objects.all(), write_only=True
    )

    class Meta:
        model = ScrimmageTemplate
        fields = [
            "id",
            "creator",
            "title",
            "scrimmage_type",
            "scrimmage_type_id",
            "base_settings",
            "is_shared",
            "created_at",
        ]
        read_only_fields = ("creator", "created_at")

    def create(self, validated_data):
        validated_data["creator"] = self.context["request"].user
        return super().create(validated_data)


# --- NEW: RECURRENCE SERIALIZER ---
class RecurrenceRuleSerializer(serializers.ModelSerializer):
    scrimmage = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RecurrenceRule
        fields = [
            "id",
            "scrimmage",
            "frequency",
            "interval",
            "day_of_week",
            "start_date",
            "end_date",
            "active",
        ]



class LeagueTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeagueTeam
        fields = [
            "id", "league", "group", "name", "owner",
            "wins", "losses", "draws", "points", "join_code"
        ]
        read_only_fields = ["wins", "losses", "draws", "points"]
        extra_kwargs = {
            "league": {"required": False, "allow_null": True},
            "owner": {"required": False, "allow_null": True},
            "group": {"required": False, "allow_null": True},
        }

    def __init__(self, *args, **kwargs):
        """Extra debug to confirm initialization and context."""
        print("⚙️ [SERIALIZER DEBUG] LeagueTeamSerializer initialized with data:", kwargs.get("data"))
        print("⚙️ [SERIALIZER DEBUG] Context:", kwargs.get("context"))
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        """Confirm which fields are being validated."""
        print("🔍 [SERIALIZER DEBUG] validate() called with attrs:", attrs)
        return super().validate(attrs)

    def create(self, validated_data):
        print("⚙️ [SERIALIZER DEBUG] create() called with data:", validated_data)
        request = self.context.get("request")
        if request and not validated_data.get("owner"):
            validated_data["owner"] = request.user
            print("👤 [SERIALIZER DEBUG] owner auto-assigned:", request.user)
        instance = super().create(validated_data)
        print("✅ [SERIALIZER DEBUG] LeagueTeam instance created:", instance)
        return instance



class LeagueSerializer(serializers.ModelSerializer):
    organizer = UserMiniSerializer(read_only=True)
    teams = LeagueTeamSerializer(many=True, read_only=True)

    class Meta:
        model = League
        fields = [
            "id", "slug", "name", "organizer", "group", "category", "description",
            "rules", "commitment_level", "start_date", "end_date", "is_active",
            "max_teams", "team_size_min", "team_size_max", "teams", "created_at"
        ]
        read_only_fields = ["slug", "organizer", "created_at"]

    def create(self, validated):
        validated["organizer"] = self.context["request"].user
        return super().create(validated)


class PerformanceStatSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = PerformanceStat
        fields = ["id", "user", "scrimmage", "metrics", "note", "created_at"]
        read_only_fields = ["user", "created_at"]

    def create(self, validated):
        validated["user"] = self.context["request"].user
        return super().create(validated)



class ScrimmageCategorySerializer(serializers.ModelSerializer):
    class Meta: model = ScrimmageCategory; fields = ["id","name","slug"]

class ScrimmageTypeSerializer(serializers.ModelSerializer):
    category = ScrimmageCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=ScrimmageCategory.objects.all(), write_only=True)
    class Meta: model = ScrimmageType; fields = ["id","name","slug","category","category_id","custom_field_schema"]

class ScrimmageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scrimmage
        fields = "__all__"
        read_only_fields = ("creator",)
