from rest_framework.routers import DefaultRouter
from .views import CalendarViewSet

router = DefaultRouter()
router.register(r"calendars", CalendarViewSet, basename="calendar")

urlpatterns = router.urls
