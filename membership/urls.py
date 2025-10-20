from rest_framework.routers import DefaultRouter
from .views import MembershipPlanViewSet, MembershipViewSet, PaymentViewSet

router = DefaultRouter()
router.register(r"plans", MembershipPlanViewSet, basename="plans")
router.register(r"memberships", MembershipViewSet, basename="memberships")
router.register(r"payments", PaymentViewSet, basename="payments")

urlpatterns = router.urls
