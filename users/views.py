from django.utils import timezone
from dateutil.relativedelta import relativedelta
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from .models import (
    UserProfile, Follow, MembershipPlan, Membership, Payment,
    Group, GroupMember, Event, RSVP, CalendarItem
)
from .serializers import (
    UserProfileSerializer, ProfileUpdateSerializer, MembershipPlanSerializer,
    MembershipSerializer, PaymentSerializer, GroupSerializer, GroupMemberSerializer,
    EventSerializer, RSVPSerializer, CalendarItemSerializer
)
from .permissions import IsOwnerOrReadOnly, IsOrganizerOrReadOnly


def _extend_membership_period(membership: Membership):
    plan = membership.plan
    if plan.interval == "month":
        membership.current_period_end = (membership.current_period_end or timezone.now()) + relativedelta(months=1)
    else:
        membership.current_period_end = (membership.current_period_end or timezone.now()) + relativedelta(years=1)
    membership.next_due_amount = plan.price
    membership.next_due_date = membership.current_period_end
    membership.status = "active"
    membership.save()


# --------- Profiles ---------
class UserProfileViewSet(viewsets.GenericViewSet,
                         mixins.RetrieveModelMixin,
                         mixins.UpdateModelMixin,
                         mixins.ListModelMixin):
    """
    GET /profiles/                -> list (public, search)
    GET /profiles/{id}/           -> retrieve
    PATCH /profiles/{id}/         -> owner update
    GET /profiles/me/             -> my profile
    POST /profiles/{id}/follow/   -> follow/unfollow
    """
    queryset = UserProfile.objects.select_related("user")
    serializer_class = UserProfileSerializer
    permission_classes = [IsOwnerOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["user__username", "display_name", "bio", "location", "interests"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        profile = request.user.profile
        return Response(self.get_serializer(profile).data)

    def get_serializer_class(self):
        if self.action in ["partial_update", "update"]:
            return ProfileUpdateSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def follow(self, request, pk=None):
        profile = self.get_object()
        if request.user == profile.user:
            return Response({"detail": "You cannot follow yourself."}, status=400)

        existing = Follow.objects.filter(follower=request.user, profile=profile).first()
        if existing:
            existing.delete()
            return Response({"detail": "Unfollowed."})
        Follow.objects.create(follower=request.user, profile=profile)
        return Response({"detail": "Followed."})

    @action(detail=True, methods=["get"])
    def followers(self, request, pk=None):
        profile = self.get_object()
        qs = profile.followed_by.select_related("follower").all()
        data = [{"id": f.follower.id, "username": f.follower.username} for f in qs]
        return Response(data)


# --------- Plans, Memberships, Payments ---------
class MembershipPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MembershipPlan.objects.filter(is_active=True)
    serializer_class = MembershipPlanSerializer
    permission_classes = [AllowAny]


class MembershipViewSet(viewsets.ModelViewSet):
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Membership.objects.filter(user=self.request.user).select_related("plan")

    def perform_create(self, serializer):
        sub = serializer.save(user=self.request.user)
        # seed due fields
        sub.next_due_amount = sub.plan.price
        sub.next_due_date = sub.current_period_end
        sub.save()

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sub = self.get_object()
        sub.auto_renew = False
        sub.status = "canceled"
        sub.save()
        return Response({"detail": "Membership canceled at period end."})

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
    filter_backends = [OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


# --------- Groups ---------
class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().select_related("owner")
    serializer_class = GroupSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description", "slug"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["create"]:
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsOwnerOrReadOnly()]
        return [AllowAny()]

    def perform_create(self, serializer):
        group = serializer.save(owner=self.request.user)
        GroupMember.objects.create(user=self.request.user, group=group, role="organizer")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        group = self.get_object()
        GroupMember.objects.get_or_create(user=request.user, group=group)
        return Response({"detail": "Joined group."})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def leave(self, request, pk=None):
        group = self.get_object()
        GroupMember.objects.filter(user=request.user, group=group).delete()
        return Response({"detail": "Left group."})

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        group = self.get_object()
        members = GroupMember.objects.filter(group=group).select_related("user")
        return Response(GroupMemberSerializer(members, many=True).data)


# --------- Events & RSVP ---------
class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["group", "is_public"]
    search_fields = ["title", "description", "location_name", "address", "tags"]
    ordering = ["start"]

    def get_queryset(self):
        qs = Event.objects.select_related("host", "group")
        # public by default; authenticated users also see their private ones
        if self.request.user.is_authenticated:
            return qs
        return qs.filter(is_public=True)

    def get_permissions(self):
        if self.action in ["create"]:
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsOrganizerOrReadOnly()]
        return [AllowAny()]

    def perform_create(self, serializer):
        event = serializer.save(host=self.request.user)
        # auto add to host calendar
        CalendarItem.objects.create(
            user=self.request.user, kind="event", title=event.title, start=event.start, end=event.end, event=event
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def rsvp(self, request, pk=None):
        event = self.get_object()
        status_val = request.data.get("status", "interested")
        rsvp, _ = RSVP.objects.update_or_create(user=request.user, event=event, defaults={"status": status_val})
        # auto calendar entry for going
        if status_val == "going":
            CalendarItem.objects.get_or_create(
                user=request.user, event=event,
                defaults={"kind": "event", "title": event.title, "start": event.start, "end": event.end}
            )
        return Response(RSVPSerializer(rsvp).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def checkin(self, request, pk=None):
        event = self.get_object()
        try:
            rsvp = RSVP.objects.get(user=request.user, event=event)
            rsvp.status = "checked_in"
            rsvp.save()
            return Response({"detail": "Checked in."})
        except RSVP.DoesNotExist:
            return Response({"detail": "RSVP not found."}, status=404)


class RSVPViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RSVPSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RSVP.objects.filter(user=self.request.user).select_related("event")


# --------- Calendar ---------
class CalendarViewSet(viewsets.ModelViewSet):
    serializer_class = CalendarItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["kind"]
    ordering = ["start"]

    def get_queryset(self):
        return CalendarItem.objects.filter(user=self.request.user).select_related("event")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)




import stripe
from paypalcheckoutsdk.core import LiveEnvironment, SandboxEnvironment, PayPalHttpClient
from paypalcheckoutsdk.notifications.verifywebhooksignaturerequest import VerifyWebhookSignatureRequest
from django.conf import settings
import json

from .models import (
    # existing:
    UserProfile, Follow, MembershipPlan, Membership, Payment,
    Group, GroupMember, Event, RSVP, CalendarItem,
    # new:
    Notification, MessageThread, Message
)
from .serializers import (
    # existing:
    UserProfileSerializer, ProfileUpdateSerializer, MembershipPlanSerializer,
    MembershipSerializer, PaymentSerializer, GroupSerializer, GroupMemberSerializer,
    EventSerializer, RSVPSerializer, CalendarItemSerializer,
    # new:
    NotificationSerializer, MessageThreadSerializer, MessageSerializer, FullCalendarItemSerializer
)


class StripeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        stripe.api_key = settings.STRIPE_API_KEY
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        # Handle relevant events
        if event["type"] in ("checkout.session.completed", "payment_intent.succeeded", "invoice.paid"):
            data = event["data"]["object"]

            # Resolve user + membership by metadata or external_ref
            user_id = (data.get("metadata") or {}).get("user_id")
            plan_id = (data.get("metadata") or {}).get("plan_id")
            provider_ref = data.get("id") or data.get("payment_intent") or data.get("invoice")

            user = None
            membership = None
            if user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.filter(id=user_id).first()

            if user and plan_id:
                plan = MembershipPlan.objects.filter(id=plan_id).first()
                membership = Membership.objects.filter(user=user, plan=plan).order_by("-started_at").first()
                if not membership and plan:
                    # create one if missing
                    membership = Membership.objects.create(
                        user=user, plan=plan, status="active", started_at=timezone.now(),
                        current_period_end=timezone.now(), external_ref=""
                    )

            if user and membership:
                Payment.objects.create(
                    user=user,
                    membership=membership,
                    amount=membership.plan.price,
                    currency=membership.plan.currency,
                    status="succeeded",
                    method="card",
                    provider="stripe",
                    provider_ref=provider_ref,
                )
                _extend_membership_period(membership)
                Notification.objects.create(
                    user=user, kind="payment", title="Payment received",
                    body=f"Your {membership.plan.name} subscription has been renewed.",
                    url="/memberships"
                )

        elif event["type"] in ("invoice.payment_failed", "payment_intent.payment_failed"):
            data = event["data"]["object"]
            user_id = (data.get("metadata") or {}).get("user_id")
            provider_ref = data.get("id") or data.get("payment_intent") or data.get("invoice")
            if user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.filter(id=user_id).first()
                if user:
                    Payment.objects.create(
                        user=user,
                        membership=None,
                        amount=(data.get("amount_due") or 0)/100.0 if "amount_due" in data else 0,
                        currency=(data.get("currency") or "usd").upper(),
                        status="failed",
                        method="card",
                        provider="stripe",
                        provider_ref=provider_ref,
                    )
                    Notification.objects.create(
                        user=user, kind="payment", title="Payment failed",
                        body="We couldn't process your recent payment. Please update your billing method.",
                        url="/billing"
                    )
        # Always 200 so Stripe stops retrying once handled
        return Response({"received": True})


def _paypal_client():
    if settings.PAYPAL_ENVIRONMENT == "live":
        env = LiveEnvironment(client_id=settings.PAYPAL_CLIENT_ID, client_secret=settings.PAYPAL_CLIENT_SECRET)
    else:
        env = SandboxEnvironment(client_id=settings.PAYPAL_CLIENT_ID, client_secret=settings.PAYPAL_CLIENT_SECRET)
    return PayPalHttpClient(env)

class PayPalWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        client = _paypal_client()
        body = request.body.decode("utf-8")
        body_json = json.loads(body or "{}")

        verify_req = VerifyWebhookSignatureRequest()
        verify_req.request_body(body)
        verify_req.headers = {
            "transmission_id": request.META.get("HTTP_PAYPAL_TRANSMISSION_ID"),
            "transmission_time": request.META.get("HTTP_PAYPAL_TRANSMISSION_TIME"),
            "cert_url": request.META.get("HTTP_PAYPAL_CERT_URL"),
            "auth_algo": request.META.get("HTTP_PAYPAL_AUTH_ALGO"),
            "transmission_sig": request.META.get("HTTP_PAYPAL_TRANSMISSION_SIG"),
            "webhook_id": settings.PAYPAL_WEBHOOK_ID,
        }

        try:
            response = client.execute(verify_req)
            if response.result.verification_status != "SUCCESS":
                return Response({"detail": "Invalid webhook signature"}, status=400)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        event_type = body_json.get("event_type")
        resource = body_json.get("resource", {})

        if event_type in ("BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.RENEWED", "PAYMENT.SALE.COMPLETED"):
            # Extract metadata you pass when creating the subscription/checkout
            custom_id = resource.get("custom_id") or (resource.get("billing_agreement_id") or "")
            # custom_id you set like "user_id:PLANID"
            user_id, _, plan_id = custom_id.partition(":")
            provider_ref = resource.get("id") or resource.get("sale_id")
            amount = (resource.get("amount") or {}).get("total") or (resource.get("amount") or {}).get("value") or 0
            currency = (resource.get("amount") or {}).get("currency") or (resource.get("amount") or {}).get("currency_code") or "USD"

            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(id=user_id).first() if user_id else None
            plan = MembershipPlan.objects.filter(id=plan_id).first() if plan_id else None

            if user and plan:
                membership = Membership.objects.filter(user=user, plan=plan).order_by("-started_at").first()
                if not membership:
                    membership = Membership.objects.create(
                        user=user, plan=plan, status="active", started_at=timezone.now(),
                        current_period_end=timezone.now(), external_ref=""
                    )
                Payment.objects.create(
                    user=user, membership=membership, amount=amount, currency=currency,
                    status="succeeded", method="wallet", provider="paypal", provider_ref=provider_ref
                )
                _extend_membership_period(membership)
                Notification.objects.create(
                    user=user, kind="payment", title="Payment received",
                    body=f"Your {membership.plan.name} subscription has been renewed via PayPal.",
                    url="/memberships"
                )

        elif event_type in ("PAYMENT.SALE.DENIED", "BILLING.SUBSCRIPTION.SUSPENDED"):
            # Inform user
            # (You can also set membership.status = "past_due")
            pass

        return Response({"received": True})


class CalendarViewSet(viewsets.ModelViewSet):
    # ... existing code ...

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def fullcalendar(self, request):
        """
        Returns events in FullCalendar-friendly format
        """
        items = self.get_queryset()
        # optionally filter by ?start= & ?end=
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if start and end:
            items = items.filter(start__lt=end, end__gt=start)

        payload = []
        for item in items.select_related("event"):
            payload.append({
                "id": item.id,
                "title": item.title,
                "start": item.start,
                "end": item.end,
                "url": f"/events/{item.event_id}" if item.event_id else "",
                "color": "#2563eb" if item.kind == "event" else "#10b981",  # blue for events, green for personal
            })
        return Response(FullCalendarItemSerializer(payload, many=True).data)


# --------- Notifications ---------
class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        qs = self.get_queryset().filter(is_read=False)
        count = qs.update(is_read=True)
        return Response({"updated": count})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save()
        return Response({"detail": "Marked read"})


# --------- Chat Threads ---------
class MessageThreadViewSet(viewsets.ModelViewSet):
    serializer_class = MessageThreadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MessageThread.objects.filter(participants=self.request.user).prefetch_related("participants", "messages")

    def perform_create(self, serializer):
        thread = serializer.save()
        # Expect a list of participant IDs in request.data["participants"]
        pids = self.request.data.get("participants", [])
        from django.contrib.auth import get_user_model
        User = get_user_model()
        thread.participants.add(self.request.user, *User.objects.filter(id__in=pids))
        thread.save()

    @action(detail=True, methods=["post"])
    def add_participant(self, request, pk=None):
        thread = self.get_object()
        pid = request.data.get("user_id")
        if not pid:
            return Response({"detail": "user_id required"}, status=400)
        thread.participants.add(get_object_or_404(User, id=pid))
        return Response({"detail": "Participant added"})

    @action(detail=True, methods=["post"])
    def remove_participant(self, request, pk=None):
        thread = self.get_object()
        pid = request.data.get("user_id")
        if not pid:
            return Response({"detail": "user_id required"}, status=400)
        thread.participants.remove(get_object_or_404(User, id=pid))
        return Response({"detail": "Participant removed"})


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        thread_id = self.request.query_params.get("thread")
        qs = Message.objects.filter(thread__participants=self.request.user)
        if thread_id:
            qs = qs.filter(thread_id=thread_id)
        return qs.select_related("thread", "sender")

    def perform_create(self, serializer):
        thread_id = self.request.data.get("thread")
        thread = get_object_or_404(MessageThread, id=thread_id, participants=self.request.user)
        msg = serializer.save(sender=self.request.user, thread=thread)
        # notify other participants
        others = thread.participants.exclude(id=self.request.user.id)
        for u in others:
            Notification.objects.create(
                user=u, kind="message", title="New message", body=msg.body[:140], url=f"/messages?thread={thread.id}"
            )
        thread.save()  # updates updated_at

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        msg = self.get_object()
        msg.read_by.add(request.user)
        return Response({"detail": "Message marked as read"})
