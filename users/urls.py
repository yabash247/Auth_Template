from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    UserProfileViewSet, MembershipPlanViewSet, MembershipViewSet, PaymentViewSet,
    GroupViewSet, EventViewSet, RSVPViewSet, CalendarViewSet,
    StripeWebhookView, PayPalWebhookView, NotificationViewSet,
    MessageThreadViewSet, MessageViewSet
)

router = DefaultRouter()
urlpatterns = router.urls

router.register(r"profiles", UserProfileViewSet, basename="profiles")
router.register(r"plans", MembershipPlanViewSet, basename="plans")
router.register(r"memberships", MembershipViewSet, basename="memberships")
router.register(r"payments", PaymentViewSet, basename="payments")
router.register(r"groups", GroupViewSet, basename="groups")
router.register(r"events", EventViewSet, basename="events")
router.register(r"rsvps", RSVPViewSet, basename="rsvps")
router.register(r"calendar", CalendarViewSet, basename="calendar")



router.register(r"profiles", UserProfileViewSet, basename="profiles")
router.register(r"plans", MembershipPlanViewSet, basename="plans")
router.register(r"memberships", MembershipViewSet, basename="memberships")
router.register(r"payments", PaymentViewSet, basename="payments")
router.register(r"groups", GroupViewSet, basename="groups")
router.register(r"events", EventViewSet, basename="events")
router.register(r"rsvps", RSVPViewSet, basename="rsvps")
router.register(r"calendar", CalendarViewSet, basename="calendar")
router.register(r"notifications", NotificationViewSet, basename="notifications")
router.register(r"threads", MessageThreadViewSet, basename="threads")
router.register(r"messages", MessageViewSet, basename="messages")

urlpatterns = [
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("webhooks/paypal/", PayPalWebhookView.as_view(), name="paypal-webhook"),
]
urlpatterns += router.urls
