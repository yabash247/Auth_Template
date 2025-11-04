# scrimmages/admin.py
from django.contrib import admin
from .models import (
    Scrimmage,
    ScrimmageRSVP,
    ScrimmageCategory,
    ScrimmageType,
    ScrimmageTemplate,
    RecurrenceRule,
    PerformanceStat,
)

# Inline participation display
class ScrimmageParticipationInline(admin.TabularInline):
    model = ScrimmageRSVP
    extra = 0


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
    inlines = [ScrimmageParticipationInline]

    fieldsets = (
        ("General", {
            "fields": (
                "title", "description", "scrimmage_type"
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
                "status", "visibility"
            )
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.host_id:
            obj.host = request.user
        super().save_model(request, obj, form, change)


@admin.register(ScrimmageTemplate)
class ScrimmageTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "is_shared", "created_at")
    search_fields = ("title",)
    list_filter = ("is_shared",)


@admin.register(RecurrenceRule)
class RecurrenceRuleAdmin(admin.ModelAdmin):
    list_display = ("scrimmage", "frequency", "interval", "active")


@admin.register(PerformanceStat)
class PerformanceStatAdmin(admin.ModelAdmin):
    list_display = ("user", "scrimmage", "created_at")
    search_fields = ("user__email", "scrimmage__title")
