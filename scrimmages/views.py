from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal

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
from .serializers import (
    ScrimmageSerializer,
    ScrimmageCategorySerializer,
    ScrimmageTypeSerializer,
    ScrimmageRSVPSerializer,
    ScrimmageMediaSerializer,
    RecurrenceRuleSerializer,
    ScrimmageTemplateSerializer,
    PerformanceStatSerializer,
)
from .permissions import (
    ScrimmagePermission,
    RSVPWritePermission,
    MediaUploadPermission,
    CategoryTypePermission,
    TemplatePermission,
    IsHostOrAdmin,
)
from .validators import (
    validate_scrimmage_dates,
    validate_media_upload,
    validate_rsvp_data,
    promote_next_waitlisted,
)


# ============================================================
# ✅ Category & Type ViewSets
# ============================================================

class ScrimmageCategoryViewSet(viewsets.ModelViewSet):
    queryset = ScrimmageCategory.objects.all()
    serializer_class = ScrimmageCategorySerializer
    permission_classes = [CategoryTypePermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.filter(approved=True)
        return self.queryset.filter(Q(approved=True) | Q(created_by=user))


class ScrimmageTypeViewSet(viewsets.ModelViewSet):
    queryset = ScrimmageType.objects.all()
    serializer_class = ScrimmageTypeSerializer
    permission_classes = [CategoryTypePermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.filter(approved=True)
        return self.queryset.filter(Q(approved=True) | Q(created_by=user))


# ============================================================
# ✅ Scrimmage ViewSet
# ============================================================

class ScrimmageViewSet(viewsets.ModelViewSet):
    queryset = Scrimmage.objects.select_related("category", "scrimmage_type", "host")
    serializer_class = ScrimmageSerializer
    permission_classes = [ScrimmagePermission]

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()
        qs = self.queryset

        # Public for everyone
        if not user.is_authenticated:
            return qs.filter(visibility="public", status__in=["upcoming", "ongoing"])

        # Authenticated users: show public + their group/league/private
        return qs.filter(
            Q(visibility="public")
            | Q(host=user)
            | Q(rsvps__user=user)
            | Q(group__members__user=user)
            #| Q(league__members__user=user)
        ).distinct()

    def perform_create(self, serializer):
        """Create scrimmage and enforce credit/payment rules."""
        user = self.request.user
        start = self.request.data.get("start_datetime")
        end = self.request.data.get("end_datetime")
        entry_fee = float(self.request.data.get("entry_fee", 0))

        # Validate time
        if start and end:
            validate_scrimmage_dates(serializer.validated_data["start_datetime"],
                                     serializer.validated_data["end_datetime"])

        # Handle credits
        credit_required = False
        if entry_fee > 0:
            try:
                from payments.models import CreditWallet
                wallet = CreditWallet.objects.get(user=user)
                if wallet.balance < entry_fee:
                    credit_required = True
            except Exception:
                credit_required = True

        scrimmage = serializer.save(host=user, credit_required=credit_required)
        return scrimmage

    # ----------------------------
    # RSVP Flow (Safe Payment Logic)
    # ----------------------------

    @action(detail=True, methods=["post"], permission_classes=[RSVPWritePermission])
    def rsvp(self, request, pk=None):
        """RSVP or update attendance."""
        scrim = self.get_object()
        user = request.user
        data = request.data.copy()
        data["scrimmage"] = scrim.id
        data["user"] = user.id
        validate_rsvp_data(data)

        # Determine payment method (default to tentative) and compute initial RSVP status
        payment_method = data.get("payment_method", "tentative") or "tentative"

        # Default status
        desired_status = data.get("status")  # allow explicit status override

        # If the scrimmage has an entry fee, determine status based on payment method
        if scrim.entry_fee and Decimal(scrim.entry_fee) > 0:
            if payment_method == "online":
                if not data.get("confirmed_payment_intent"):
                    raise ValidationError("Payment must be confirmed by user before charging.")
                # Attempt auto payment if payments module available
                try:
                    from payments.utils import process_auto_payment  # type: ignore
                    result = process_auto_payment(
                        user=user,
                        amount=Decimal(scrim.entry_fee),
                        app_source="scrimmage",
                        related_id=scrim.id,
                        description=f"Entry fee for scrimmage '{scrim.title}'",
                    )
                    status_result = result.get("status")
                    if status_result == "paid":
                        desired_status = "going"
                    elif status_result == "pending":
                        desired_status = "pending_payment"
                    else:
                        return Response({"error": "Payment could not be processed."}, status=400)
                except Exception:
                    # Fallback: mark as pending payment until confirmed by organizer
                    desired_status = "pending_payment"
            elif payment_method in ["cash", "transfer"]:
                desired_status = "pending_payment"
            else:
                # Tentative selection means interest only
                desired_status = "interested"
        else:
            # Free scrimmage: going unless user explicitly chooses tentative
            if payment_method in ["cash", "transfer", "online"]:
                desired_status = "going"
            else:
                desired_status = "going" if payment_method != "tentative" else "interested"

        if desired_status:
            data["status"] = desired_status

        # Upsert RSVP
        rsvp, created = ScrimmageRSVP.objects.get_or_create(scrimmage=scrim, user=user)
        serializer = ScrimmageRSVPSerializer(rsvp, data=data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Waitlist handling: demote to waitlist if confirmed going but no spots left
        if scrim.spots_left <= 0 and scrim.waitlist_enabled and serializer.instance.status == "going":
            serializer.instance.status = "waitlisted"
            serializer.instance.save(update_fields=["status"])

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def rsvps(self, request, pk=None):
        scrim = self.get_object()
        rsvps = scrim.rsvps.all().select_related("user")
        return Response(ScrimmageRSVPSerializer(rsvps, many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[RSVPWritePermission])
    def feedback(self, request, pk=None):
        """Submit feedback and rating."""
        scrim = self.get_object()
        rsvp = ScrimmageRSVP.objects.filter(scrimmage=scrim, user=request.user).first()
        if not rsvp:
            return Response({"detail": "You have not RSVP'd for this scrimmage."}, status=400)

        rating = request.data.get("rating")
        feedback = request.data.get("feedback")
        validate_rsvp_data({"rating": rating})

        rsvp.rating = rating
        rsvp.feedback = feedback
        rsvp.save(update_fields=["rating", "feedback"])

        # Update scrimmage rating average
        ratings = scrim.rsvps.filter(rating__isnull=False).values_list("rating", flat=True)
        if ratings:
            scrim.rating_count = len(ratings)
            scrim.rating_avg = sum(ratings) / scrim.rating_count
            scrim.save(update_fields=["rating_avg", "rating_count"])

        return Response({"success": "Feedback submitted."})

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def media(self, request, pk=None):
        """Get all media for this scrimmage."""
        scrim = self.get_object()
        media = scrim.media_files.filter(approved=True)
        return Response(ScrimmageMediaSerializer(media, many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[MediaUploadPermission])
    def upload_media(self, request, pk=None):
        """Upload new media with file size validation."""
        scrim = self.get_object()
        user = request.user
        file_size = int(request.data.get("file_size", 0))

        validate_media_upload(user, scrim, file_size)
        serializer = ScrimmageMediaSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(scrimmage=scrim)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsHostOrAdmin])
    def cancel(self, request, pk=None):
        """Cancel scrimmage and trigger refunds if applicable."""
        scrim = self.get_object()
        scrim.status = "cancelled"
        scrim.save(update_fields=["status"])

        # Auto refunds via signal (if payments integrated)
        return Response({"success": f"Scrimmage '{scrim.title}' cancelled."})

    @action(detail=True, methods=["post"], permission_classes=[IsHostOrAdmin])
    def check_in(self, request, pk=None):
        """Host marks participant as checked in."""
        scrim = self.get_object()
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id is required."}, status=400)

        try:
            rsvp = ScrimmageRSVP.objects.get(scrimmage=scrim, user_id=user_id)
        except ScrimmageRSVP.DoesNotExist:
            return Response({"error": "RSVP not found."}, status=404)

        rsvp.status = "checked_in"
        rsvp.checked_in_at = timezone.now()
        rsvp.save(update_fields=["status", "checked_in_at"])
        return Response({"success": f"{rsvp.user} checked in."})


# ============================================================
# ✅ Media ViewSet
# ============================================================

class ScrimmageMediaViewSet(viewsets.ModelViewSet):
    queryset = ScrimmageMedia.objects.select_related("scrimmage", "uploader")
    serializer_class = ScrimmageMediaSerializer
    permission_classes = [MediaUploadPermission]

    def perform_create(self, serializer):
        serializer.save(uploader=self.request.user)


# ============================================================
# ✅ Template ViewSet
# ============================================================

class ScrimmageTemplateViewSet(viewsets.ModelViewSet):
    queryset = ScrimmageTemplate.objects.all()
    serializer_class = ScrimmageTemplateSerializer
    permission_classes = [TemplatePermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.filter(is_public=True, approved=True)
        return self.queryset.filter(Q(is_public=True) | Q(creator=user)).distinct()

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


# ============================================================
# ✅ Recurrence Rule ViewSet
# ============================================================

class RecurrenceRuleViewSet(viewsets.ModelViewSet):
    queryset = RecurrenceRule.objects.select_related("scrimmage")
    serializer_class = RecurrenceRuleSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


# ============================================================
# ✅ Performance Stats ViewSet
# ============================================================

class PerformanceStatViewSet(viewsets.ModelViewSet):
    queryset = PerformanceStat.objects.select_related("scrimmage", "user")
    serializer_class = PerformanceStatSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)






# SCRIMMAGE WORKFLOW OVERVIEW

'''

 ┌────────────────────────────────────────┐
 │        SCRIMMAGE CREATION FLOW         │
 └────────────────────────────────────────┘
          │
          ▼
 ┌──────────────────────────────────────┐
 │ Host creates Scrimmage               │
 │ - Sets entry_fee                     │
 │ - Defines payment_options            │
 │   (online / cash / transfer / tentative) │
 └──────────────────────────────────────┘
          │
          ▼
 ┌──────────────────────────────────────┐
 │ Scrimmage saved in DB                │
 │ → Signals create calendar + notify   │
 │ → CreditRequired = True if wallet < fee │
 └──────────────────────────────────────┘
          │
          ▼
   Users browse and RSVP

─────────────────────────────────────────────
           RSVP + PAYMENT DECISION
─────────────────────────────────────────────
          │
          ▼
 ┌────────────────────────────────────────┐
 │ User submits RSVP                      │
 │ (selects payment_method)               │
 └────────────────────────────────────────┘
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ Backend logic (views.py)                   │
 │ - Checks scrimmage.entry_fee               │
 │ - If free → status = "going"               │
 │ - If paid + method:                        │
 │    • online   → process_auto_payment()     │
 │    • cash/transfer → pending_payment       │
 │    • tentative     → interested            │
 └────────────────────────────────────────────┘
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ process_auto_payment (payments/utils.py)   │
 │ - Checks CreditWallet balance              │
 │ - If balance ≥ amount → deduct + mark paid │
 │ - Else → create PaymentTransaction (pending)│
 │ - Sends Notification                       │
 └────────────────────────────────────────────┘
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ RSVP record updated                        │
 │ - status = going / pending_payment / interested │
 │ - payment_method saved                     │
 │ - reminder_sent_at remains null            │
 └────────────────────────────────────────────┘
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ Conditional Visibility                     │
 │ - going/checked_in/completed → full details│
 │ - pending_payment/waitlisted → only city   │
 │ - interested/no RSVP → hides address       │
 └────────────────────────────────────────────┘

─────────────────────────────────────────────
           EVENT LIFE CYCLE
─────────────────────────────────────────────
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ Organizer confirms cash payments           │
 │ - Updates RSVP → status = "going"          │
 │ - Payment model (optional) updated         │
 └────────────────────────────────────────────┘
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ Waitlist Automation                        │
 │ - promote_next_waitlisted() runs            │
 │ - fills freed spots automatically          │
 └────────────────────────────────────────────┘
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ Scrimmage starts → check_in()              │
 │ - Host marks participants as checked_in    │
 │ - Optional payment validation              │
 └────────────────────────────────────────────┘
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ Scrimmage ends → feedback & rating         │
 │ - RSVP feedback() updates stats            │
 │ - Notifications trigger                   │
 └────────────────────────────────────────────┘

─────────────────────────────────────────────
           POST-EVENT SIGNALS
─────────────────────────────────────────────
          │
          ▼
 ┌────────────────────────────────────────────┐
 │ signals.py (post_save)                     │
 │ - Add to user calendar (if "going")        │
 │ - Notify user or group                     │
 │ - Refund via Payment if cancelled          │
 └────────────────────────────────────────────┘


'''