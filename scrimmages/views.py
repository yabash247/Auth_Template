# scrimmages/views.py
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import Scrimmage, ScrimmageParticipation, League, LeagueTeam, PerformanceStat
from .serializers import (
    ScrimmageSerializer, ScrimmageParticipationSerializer,
    LeagueSerializer, LeagueTeamSerializer, PerformanceStatSerializer
)
from .permissions import IsOwnerOrReadOnly


class ScrimmageViewSet(viewsets.ModelViewSet):
    queryset = Scrimmage.objects.select_related("creator", "group")
    serializer_class = ScrimmageSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "upcoming"]:
            return [AllowAny()]
        if self.action in ["create"]:
            return [IsAuthenticated()]
        return [IsOwnerOrReadOnly()]
    
    def perform_create(self, serializer):
        """
        Automatically assign the logged-in user as the creator of the scrimmage.
        """
        serializer.save(creator=self.request.user)


    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_authenticated:
            qs = qs.filter(visibility="public", status="published")
        # simple filters
        category = self.request.query_params.get("category")
        upcoming = self.request.query_params.get("upcoming")
        if category:
            qs = qs.filter(category=category)
        if upcoming == "true":
            qs = qs.filter(end_time__gte=timezone.now())
        return qs

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my(self, request):
        qs = Scrimmage.objects.filter(
            Q(creator=request.user) | Q(participants__user=request.user)
        ).distinct().order_by("start_time")
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def upcoming(self, request):
        qs = Scrimmage.objects.filter(visibility="public", status="published", end_time__gte=timezone.now()).order_by("start_time")
        return Response(self.get_serializer(qs, many=True).data)

    # ---- roster actions ----
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        scrim = self.get_object()
        # basic capacity guard
        confirmed = scrim.participants.filter(status__in=["confirmed", "checked_in"]).count()
        if scrim.max_participants and confirmed >= scrim.max_participants:
            return Response({"detail": "Scrimmage is full."}, status=400)
        part, _ = ScrimmageParticipation.objects.get_or_create(
            user=request.user, scrimmage=scrim, defaults={"status": "confirmed"}
        )
        if part.status == "declined":
            part.status = "confirmed"
            part.save(update_fields=["status"])
        return Response(ScrimmageParticipationSerializer(part).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def leave(self, request, pk=None):
        scrim = self.get_object()
        ScrimmageParticipation.objects.filter(user=request.user, scrimmage=scrim).delete()
        return Response({"detail": "Left scrimmage."})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def invite(self, request, pk=None):
        """
        Invite specific user_id to private scrimmage (owner/staff only).
        """
        scrim = self.get_object()
        if not (request.user == scrim.creator or request.user.is_staff):
            return Response({"detail": "Only the creator can invite."}, status=403)
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id required."}, status=400)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target = User.objects.filter(id=user_id).first()
        if not target:
            return Response({"detail": "User not found."}, status=404)
        inv, _ = ScrimmageParticipation.objects.get_or_create(
            user=target, scrimmage=scrim, defaults={"status": "invited"}
        )
        return Response({"detail": f"Invited {target.email}."})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def checkin(self, request, pk=None):
        scrim = self.get_object()
        part = ScrimmageParticipation.objects.filter(user=request.user, scrimmage=scrim).first()
        if not part:
            return Response({"detail": "You are not on this roster."}, status=404)
        part.status = "checked_in"
        part.save(update_fields=["status"])
        return Response({"detail": "Checked in."})
    
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        scrim = self.get_object()
        scrim.status = "cancelled"
        scrim.save(update_fields=["status"])
        results = bulk_refund("scrimmage", scrim.id)
        return Response({"detail": "Scrimmage cancelled, refunds processed.", "results": results})
    
    # ========== TEMPLATE ACTIONS ==========

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def create_from_template(self, request):
        """
        Clone a saved scrimmage template to a new scrimmage instance.
        """
        from .models import ScrimmageTemplate
        template_id = request.data.get("template_id")
        start_time = request.data.get("start_time")

        try:
            template = ScrimmageTemplate.objects.get(pk=template_id, creator=request.user)
        except ScrimmageTemplate.DoesNotExist:
            return Response({"detail": "Template not found."}, status=404)

        data = template.base_settings.copy()
        if start_time:
            data["start_time"] = start_time
        data["creator"] = request.user.id

        serializer = ScrimmageSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        scrimmage = serializer.save()

        return Response(ScrimmageSerializer(scrimmage).data, status=201)


# ========== RECURRENCE RULE ==========

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def set_recurrence(self, request, pk=None):
        """
        Define recurrence for a scrimmage (weekly/monthly pattern).
        """
        from .models import RecurrenceRule
        from .serializers import RecurrenceRuleSerializer

        scrimmage = self.get_object()
        serializer = RecurrenceRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save(scrimmage=scrimmage)
        return Response(RecurrenceRuleSerializer(rule).data, status=201)


# ========== INTEREST-BASED AUTO-INVITES ==========

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def auto_invite(self, request, pk=None):
        """
        Automatically invite users whose interests match this scrimmage’s type or category.
        """
        from users.models import UserInterest
        from notifications.utils import notify_admins
        scrimmage = self.get_object()
        scrimmage_type_slug = scrimmage.scrimmage_type.slug

        matching_users = UserInterest.objects.filter(
            Q(types__icontains=scrimmage_type_slug)
            | Q(categories__icontains=scrimmage.scrimmage_type.category.slug),
            status="active"
        ).select_related("user")

        invited = 0
        for ui in matching_users:
            exists = scrimmage.participants.filter(user=ui.user).exists()
            if not exists:
                scrimmage.participants.create(user=ui.user, role="player", status="invited")
                invited += 1

        notify_admins(
            title="Scrimmage Auto-Invites Sent",
            body=f"{invited} users were auto-invited to {scrimmage.title}."
        )

        return Response({"message": f"Auto-invited {invited} users."}, status=200)



class LeagueViewSet(viewsets.ModelViewSet):
    queryset = League.objects.select_related("organizer", "group")
    serializer_class = LeagueSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        if self.action in ["create"]:
            return [IsAuthenticated()]
        return [IsOwnerOrReadOnly()]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_authenticated:
            qs = qs.filter(is_active=True)
        return qs

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def add_team(self, request, pk=None):
        print("\n⚙️ [DEBUG] add_team called for league:", pk)

        league = self.get_object()
        print("✅ [DEBUG] League object retrieved:", league)

        serializer = LeagueTeamSerializer(data=request.data, context={"request": request})
        print("📦 [DEBUG] Incoming data:", request.data)

        if not serializer.is_valid():
            print("❌ [DEBUG] Validation errors:", serializer.errors)
            return Response(serializer.errors, status=400)

        print("✅ [DEBUG] Serializer validated successfully.")
        team = serializer.save(league=league)
        print("🎯 [DEBUG] Team saved successfully:", team)

        response_data = LeagueTeamSerializer(team).data
        print("📤 [DEBUG] Returning response:", response_data)

        return Response(response_data, status=201)




class PerformanceStatViewSet(viewsets.ModelViewSet):
    serializer_class = PerformanceStatSerializer

    def get_queryset(self):
        qs = PerformanceStat.objects.select_related("user", "scrimmage")
        user = self.request.user
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
