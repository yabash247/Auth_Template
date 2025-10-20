from rest_framework import serializers
from .models import MembershipPlan, Membership, Payment

class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = "__all__"


class MembershipSerializer(serializers.ModelSerializer):
    plan = MembershipPlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=MembershipPlan.objects.all(), source="plan", write_only=True
    )

    class Meta:
        model = Membership
        fields = [
            "id", "user", "plan", "plan_id", "status",
            "started_at", "current_period_end",
            "next_due_date", "next_due_amount",
            "auto_renew", "external_ref",
        ]
        read_only_fields = ["user", "status", "started_at", "external_ref"]

    def create(self, validated):
        validated["user"] = self.context["request"].user
        sub = super().create(validated)
        sub.next_due_amount = sub.plan.price
        sub.next_due_date = sub.current_period_end
        sub.save()
        return sub


# add these inside your existing PaymentSerializer
class PaymentSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    league_name = serializers.CharField(source="league.name", read_only=True)
    scrimmage_title = serializers.CharField(source="scrimmage.title", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id","user","membership","amount","currency","status","method","provider","provider_ref","created_at",
            "event","event_title","league","league_name","scrimmage","scrimmage_title"
        ]
        read_only_fields = ["user","created_at","provider_ref","status","method","provider"]
