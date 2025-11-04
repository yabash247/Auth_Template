from rest_framework import serializers
from django.utils import timezone

from .models import (
    Scrimmage,
    ScrimmageCategory,
    ScrimmageType,
    ScrimmageRSVP,
    ScrimmageMedia,
    RecurrenceRule,
    ScrimmageTemplate,
    PerformanceStat,
)

from media.models import Media


# ============================================================
# ✅ Category & Type Serializers
# ============================================================
class ScrimmageCategorySerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ScrimmageCategory
        fields = [
            "id",
            "name",
            "created_by",
            "approved",
            "created_at",
        ]
        read_only_fields = ["approved", "created_by", "created_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ScrimmageTypeSerializer(serializers.ModelSerializer):
    category = ScrimmageCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=ScrimmageCategory.objects.all(),
        write_only=True,
    )
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ScrimmageType
        fields = [
            "id",
            "name",
            "category",
            "category_id",
            "created_by",
            "approved",
            "custom_field_schema",
        ]
        read_only_fields = ["approved", "created_by"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


# ============================================================
# ✅ RSVP Serializer (attendance, role, feedback, rating)
# ============================================================
class ScrimmageRSVPSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    scrimmage = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ScrimmageRSVP
        fields = [
            "id",
            "scrimmage",
            "user",
            "status",
            "role",
            "team_name",
            "score",
            "feedback",
            "rating",
            "checked_in_at",
            "created_at",
        ]
        read_only_fields = ["checked_in_at", "created_at", "user"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


# ============================================================
# ✅ Scrimmage Media Serializer (with upload moderation)
# ============================================================
class ScrimmageMediaSerializer(serializers.ModelSerializer):
    uploader = serializers.StringRelatedField(read_only=True)
    media_id = serializers.PrimaryKeyRelatedField(
        source="media",
        queryset=[],  # set in __init__ dynamically if media model imported
        write_only=True,
    )

    class Meta:
        model = ScrimmageMedia
        fields = [
            "id",
            "scrimmage",
            "uploader",
            "media_id",
            "caption",
            "approved",
            "file_size",
            "created_at",
        ]
        read_only_fields = ["uploader", "approved", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Late import to avoid circular dependency with media app
        from media.models import Media
        self.fields["media_id"].queryset = Media.objects.all()

    def create(self, validated_data):
        validated_data["uploader"] = self.context["request"].user
        return super().create(validated_data)


# ============================================================
# ✅ Recurrence Rule Serializer
# ============================================================
class RecurrenceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurrenceRule
        fields = [
            "id",
            "frequency",
            "interval",
            "day_of_week",
            "start_date",
            "end_date",
            "active",
            "auto_generate",
            "suggest_similar",
        ]


# ============================================================
# ✅ Scrimmage Template Serializer
# ============================================================
class ScrimmageTemplateSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField(read_only=True)
    scrimmage_type = ScrimmageTypeSerializer(read_only=True)
    scrimmage_type_id = serializers.PrimaryKeyRelatedField(
        source="scrimmage_type",
        queryset=ScrimmageType.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ScrimmageTemplate
        fields = [
            "id",
            "title",
            "creator",
            "scrimmage_type",
            "scrimmage_type_id",
            "base_settings",
            "is_shared",
            "approved",
            "is_public",
            "created_at",
        ]
        read_only_fields = ["creator", "approved", "is_public", "created_at"]

    def create(self, validated_data):
        validated_data["creator"] = self.context["request"].user
        return super().create(validated_data)


# ============================================================
# ✅ Scrimmage Serializer (core model)
# ============================================================
class ScrimmageSerializer(serializers.ModelSerializer):
    host = serializers.StringRelatedField(read_only=True)
    category = ScrimmageCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=ScrimmageCategory.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    scrimmage_type = ScrimmageTypeSerializer(read_only=True)
    scrimmage_type_id = serializers.PrimaryKeyRelatedField(
        source="scrimmage_type",
        queryset=ScrimmageType.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    rsvps = ScrimmageRSVPSerializer(many=True, read_only=True)
    media_files = ScrimmageMediaSerializer(many=True, read_only=True)
    recurrence_rule = RecurrenceRuleSerializer(read_only=True)

    spots_left = serializers.IntegerField(read_only=True)
    spots_taken = serializers.IntegerField(read_only=True)

    class Meta:
        model = Scrimmage
        fields = [
            "id",
            "title",
            "description",
            "host",
            "group",
            "league",
            "category",
            "category_id",
            "scrimmage_type",
            "scrimmage_type_id",
            "visibility",
            "location_name",
            "address",
            "latitude",
            "longitude",
            "start_datetime",
            "end_datetime",
            "max_participants",
            "waitlist_enabled",
            "entry_fee",
            "currency",
            "credit_required",
            "is_paid",
            "teams",
            "status",
            "rating_avg",
            "rating_count",
            "created_at",
            "updated_at",
            "spots_left",
            "spots_taken",
            "rsvps",
            "media_files",
            "recurrence_rule",
        ]
        read_only_fields = [
            "host",
            "rating_avg",
            "rating_count",
            "created_at",
            "updated_at",
            "spots_left",
            "spots_taken",
        ]

    def create(self, validated_data):
        validated_data["host"] = self.context["request"].user
        return super().create(validated_data)


# ============================================================
# ✅ Performance Stats Serializer
# ============================================================
class PerformanceStatSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    scrimmage = serializers.PrimaryKeyRelatedField(queryset=Scrimmage.objects.all())

    class Meta:
        model = PerformanceStat
        fields = [
            "id",
            "user",
            "scrimmage",
            "metrics",
            "note",
            "created_at",
        ]
        read_only_fields = ["user", "created_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
