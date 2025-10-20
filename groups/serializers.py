from rest_framework import serializers
from .models import Group, GroupMember

class GroupMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMember
        fields = ["id", "user", "group", "role", "joined_at"]
        read_only_fields = ["joined_at"]


class GroupSerializer(serializers.ModelSerializer):
    members = GroupMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ["id", "owner", "name", "slug", "description", "created_at", "members"]
        read_only_fields = ["owner", "slug", "created_at"]

    def create(self, validated):
        validated["owner"] = self.context["request"].user
        return super().create(validated)
