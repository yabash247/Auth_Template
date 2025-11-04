from rest_framework.routers import DefaultRouter
from .views import (
    ScrimmageViewSet, ScrimmageCategoryViewSet, ScrimmageTypeViewSet,
    ScrimmageTemplateViewSet, RecurrenceRuleViewSet, ScrimmageMediaViewSet,
    PerformanceStatViewSet
)

router = DefaultRouter()
router.register("scrimmages", ScrimmageViewSet)
router.register("scrimmage-categories", ScrimmageCategoryViewSet)
router.register("scrimmage-types", ScrimmageTypeViewSet)
router.register("scrimmage-templates", ScrimmageTemplateViewSet)
router.register("recurrence-rules", RecurrenceRuleViewSet)
router.register("scrimmage-media", ScrimmageMediaViewSet)
router.register("performance-stats", PerformanceStatViewSet)

urlpatterns = router.urls
