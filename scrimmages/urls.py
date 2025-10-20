# scrimmages/urls.py
from rest_framework.routers import DefaultRouter
from .views import ScrimmageViewSet, LeagueViewSet, PerformanceStatViewSet

router = DefaultRouter()
router.register(r"scrimmages", ScrimmageViewSet, basename="scrimmages")
router.register(r"leagues", LeagueViewSet, basename="leagues")
router.register(r"stats", PerformanceStatViewSet, basename="scrimmage-stats")

urlpatterns = router.urls
