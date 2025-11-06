# scrimmages/admin.py
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import (
    Scrimmage,
    ScrimmageRSVP,
    ScrimmageCategory,
    ScrimmageType,
    ScrimmageTemplate,
    RecurrenceRule,
    PerformanceStat,
    ScrimmageMedia,
)


from media.admin import MediaRelationInline
from media.models import MediaRelation

# Inline participation display
class ScrimmageParticipationInline(admin.TabularInline):
    model = ScrimmageRSVP
    extra = 0


# Inline media display
class MediaRelationInline(GenericTabularInline):
    """Inline to attach MediaRelations (icon, thumbnail, gallery, etc.)."""
    model = MediaRelation
    extra = 1
    autocomplete_fields = ["media"]
    readonly_fields = ("uploaded_at",)
    fields = ("context_name", "media", "caption", "approved", "file_size", "uploaded_at")

    def save_model(self, request, obj, form, change):
        """Auto-assign app/model names when added through Scrimmage admin."""
        if not obj.app_name:
            obj.app_name = "scrimmages"
        if not obj.model_name:
            obj.model_name = "scrimmage"
        super().save_model(request, obj, form, change)


@admin.register(ScrimmageCategory)
class ScrimmageCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(ScrimmageType)
class ScrimmageTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name", "category__name")
    fieldsets = (
        (None, {"fields": ("category", "name", "custom_field_schema")}),
    )


@admin.register(Scrimmage)
class ScrimmageAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "visibility", "status")
    list_filter = ("category", "visibility", "status", "scrimmage_type")
    search_fields = ("title", "description", "address", "scrimmage_type__name")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ScrimmageParticipationInline, MediaRelationInline]

    fieldsets = (
        ("General", {
            "fields": (
                "title", "description", "scrimmage_type", "category"
            )
        }),
        ("Location & Timing", {
            "fields": (
                "location","start_datetime", "end_datetime"
            )
        }),
        ("Financials", {
            "fields": (
                "entry_fee", "currency"
            )
        }),
        ("Meta", {
            "fields": (
                "status", "visibility", "created_at", "updated_at"
            )
        }),
    )

    def save_model(self, request, obj, form, change):
        """Auto-assign host if not set."""
        if not obj.host_id:
            obj.host = request.user
        super().save_model(request, obj, form, change)


@admin.register(ScrimmageTemplate)
class ScrimmageTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "is_shared", "created_at")
    search_fields = ("title",)
    list_filter = ("is_shared", "approved", "is_public")


@admin.register(RecurrenceRule)
class RecurrenceRuleAdmin(admin.ModelAdmin):
    list_display = ("scrimmage", "frequency", "interval", "active")
    list_filter = ("frequency", "active")
    search_fields = ("scrimmage__title",)


@admin.register(PerformanceStat)
class PerformanceStatAdmin(admin.ModelAdmin):
    list_display = ("user", "scrimmage", "created_at")
    search_fields = ("user__email", "scrimmage__title")
    list_filter = ("created_at",)

