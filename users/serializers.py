from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    UserProfile, Follow, MembershipPlan, Membership, Payment,
    Group, GroupMember, Event, RSVP, CalendarItem,
    Notification, MessageThread, Message, CalendarItem, Event
)

User = get_user_model()


# --------- User & Profile ---------
class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    followers_count = serializers.IntegerField(source="followed_by.count", read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id", "user", "display_name", "bio", "avatar", "cover_photo", "location",
            "website", "pronouns", "dob", "verified", "visibility", "interests",
            "is_creator", "reputation_points", "created_at", "followers_count",
        ]


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        exclude = ["user", "followers", "created_at"]


# --------- Membership & Payments ---------
class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = "__all__"


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["user", "created_at"]


class MembershipSerializer(serializers.ModelSerializer):
    plan = MembershipPlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=MembershipPlan.objects.filter(is_active=True),
        write_only=True, source="plan"
    )

    class Meta:
        model = Membership
        fields = [
            "id", "plan", "plan_id", "status", "started_at", "current_period_end",
            "auto_renew", "next_due_amount", "next_due_date", "external_ref"
        ]
        read_only_fields = ["started_at"]


# --------- Groups ---------
class GroupMemberSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = GroupMember
        fields = ["user", "role", "joined_at"]


class GroupSerializer(serializers.ModelSerializer):
    owner = PublicUserSerializer(read_only=True)
    members_count = serializers.IntegerField(source="members.count", read_only=True)

    class Meta:
        model = Group
        fields = ["id", "name", "slug", "owner", "description", "avatar", "is_public", "created_at", "members_count"]


# --------- Events & RSVP ---------
class EventSerializer(serializers.ModelSerializer):
    host = PublicUserSerializer(read_only=True)
    group = GroupSerializer(read_only=True)
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), write_only=True, source="group", required=False, allow_null=True
    )
    going_count = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "title", "description", "host", "group", "group_id",
            "start", "end", "location_name", "address", "latitude", "longitude",
            "capacity", "is_public", "cover", "tags", "going_count",
        ]

    def get_going_count(self, obj):
        return obj.rsvps.filter(status="going").count()


class RSVPSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = RSVP
        fields = ["id", "user", "event", "status", "created_at"]
        read_only_fields = ["user", "created_at"]


# --------- Calendar ---------
class CalendarItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarItem
        fields = ["id", "kind", "title", "start", "end", "notes", "event", "created_at"]
        read_only_fields = ["created_at"]



# --- Notifications ---
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "url", "is_read", "created_at"]

# --- Chat ---
class MessageSerializer(serializers.ModelSerializer):
    sender = PublicUserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "thread", "sender", "body", "created_at", "read_by"]
        read_only_fields = ["sender", "created_at", "read_by"]

class MessageThreadSerializer(serializers.ModelSerializer):
    participants = PublicUserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = MessageThread
        fields = ["id", "participants", "created_at", "updated_at", "last_message", "unread_count"]

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-created_at").first()
        if not msg:
            return None
        return MessageSerializer(msg).data

    def get_unread_count(self, obj):
        user = self.context.get("request").user
        return obj.messages.exclude(read_by=user).count() if user.is_authenticated else 0

# --- FullCalendar feed serializer (computed) ---
class FullCalendarItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    url = serializers.CharField(required=False, allow_blank=True)
    color = serializers.CharField(required=False, allow_blank=True)
