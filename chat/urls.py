from rest_framework.routers import DefaultRouter
from .views import MessageThreadViewSet, MessageViewSet

router = DefaultRouter()
router.register(r"threads", MessageThreadViewSet, basename="threads")
router.register(r"messages", MessageViewSet, basename="messages")

urlpatterns = router.urls
