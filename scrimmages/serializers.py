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


from media.models import Media, MediaRelation

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

    # ✅ NEW: expose payment_method for attendee selection
    payment_method = serializers.ChoiceField(
        choices=[
            ("online", "Online"),
            ("cash", "Cash on Event Day"),
            ("transfer", "Zelle / Bank Transfer"),
            ("tentative", "Tentative RSVP"),
        ],
        required=False,
        default="tentative",
    )

    # ✅ NEW: expose reminder_sent_at for read-only (automation can update)
    reminder_sent_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ScrimmageRSVP
        fields = [
            "id",
            "scrimmage",
            "user",
            "status",
             "payment_method",
            "role",
            "team_name",
            "score",
            "feedback",
            "rating",
            "reminder_sent_at",
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
    media = serializers.PrimaryKeyRelatedField(queryset=Media.objects.all())
    file_url = serializers.SerializerMethodField()
    context_name = serializers.CharField(read_only=True)
    caption = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = MediaRelation
        fields = [
            "id",
            "app_name",
            "model_name",
            "object_id",
            "context_name",
            "media",
            "file_url",
            "caption",
            "approved",
            "file_size",
            "uploaded_at",
        ]
        read_only_fields = ["app_name", "model_name", "uploaded_at", "file_url"]

    def get_file_url(self, obj):
        return obj.media.file.url if obj.media and obj.media.file else None

    def create(self, validated_data):
        """Ensure app/model linkage and uploader context automatically."""
        request = self.context.get("request")
        validated_data["app_name"] = "scrimmages"
        validated_data["model_name"] = "scrimmage"
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
    media_relations = ScrimmageMediaSerializer(
        source="media_relations.all", many=True, read_only=True
    )
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
            #"location_name",
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
            "payment_options",
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
            "media_relations",
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
    
    # ✅ Conditional visibility: hide or mask location details based on RSVP status
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        # Hide location details for anonymous users
        if not user or not getattr(user, "is_authenticated", False):
            data.pop("latitude", None)
            data.pop("longitude", None)
            # show only broad address (city/state) if available
            if data.get("address"):
                parts = data["address"].split(",")
                data["address"] = parts[-1].strip() if parts else data["address"]
            return data

        # Determine this user's RSVP status if any
        rsvp = instance.rsvps.filter(user=user).first()
        if rsvp:
            status = rsvp.status
        else:
            status = None

        # If pending payment or waitlisted: mask precise location
        if status in ["pending_payment", "waitlisted"]:
            data.pop("latitude", None)
            data.pop("longitude", None)
            if data.get("address"):
                parts = data["address"].split(",")
                data["address"] = parts[-1].strip() if parts else data["address"]
        # If no RSVP or interested: hide entire address and coordinates
        elif not status or status == "interested":
            data.pop("address", None)
            data.pop("latitude", None)
            data.pop("longitude", None)

        return data


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
