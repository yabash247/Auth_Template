from django.utils import timezone
from dateutil.relativedelta import relativedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import MembershipPlan, Membership, Payment
from .serializers import MembershipPlanSerializer, MembershipSerializer, PaymentSerializer

def extend_period(membership: Membership):
    plan = membership.plan
    if plan.interval == "month":
        membership.current_period_end = (membership.current_period_end or timezone.now()) + relativedelta(months=1)
    else:
        membership.current_period_end = (membership.current_period_end or timezone.now()) + relativedelta(years=1)
    membership.next_due_amount = plan.price
    membership.next_due_date = membership.current_period_end
    membership.status = "active"
    membership.save()


class MembershipPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MembershipPlan.objects.filter(is_active=True)
    serializer_class = MembershipPlanSerializer
    permission_classes = [AllowAny]


class MembershipViewSet(viewsets.ModelViewSet):
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Membership.objects.filter(user=self.request.user).select_related("plan")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sub = self.get_object()
        sub.auto_renew = False
        sub.status = "canceled"
        sub.save()
        return Response({"detail": "Membership canceled."})

    @action(detail=False, methods=["get"])
    def due(self, request):
        sub = self.get_queryset().filter(status__in=["active", "past_due"]).order_by("next_due_date").first()
        if not sub:
            return Response({"due": None})
        return Response({
            "plan": sub.plan.name,
            "amount": str(sub.next_due_amount),
            "currency": sub.plan.currency,
            "due_date": sub.next_due_date,
            "status": sub.status
        })


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).order_by("-created_at")
