# scrimmages/admin.py
from django.contrib import admin
from .models import Scrimmage, ScrimmageParticipation, League, LeagueTeam, PerformanceStat

class ScrimmageParticipationInline(admin.TabularInline):
    model = ScrimmageParticipation
    extra = 0


# scrimmages/admin.py
from django.contrib import admin
from .models import ScrimmageCategory, ScrimmageType, Scrimmage, ScrimmageTemplate, RecurrenceRule

@admin.register(ScrimmageCategory)
class ScrimmageCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)


@admin.register(ScrimmageType)
class ScrimmageTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "slug")
    search_fields = ("name", "category__name")
    readonly_fields = ("slug",)
    fieldsets = (
        (None, {"fields": ("category", "name", "custom_field_schema")}),
    )


from django.contrib import admin
from .models import Scrimmage, League
#from .inlines import ScrimmageParticipationInline  # if you use this inline

@admin.register(Scrimmage)
class ScrimmageAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "start_time", "visibility", "status", "creator")
    list_filter = ("category", "visibility", "status", "start_time", "scrimmage_type")
    search_fields = ("title", "description", "address", "scrimmage_type__name")
    readonly_fields = ("slug", "created_at", "updated_at")
    inlines = [ScrimmageParticipationInline]
    prepopulated_fields = {"slug": ("title",)}

    fieldsets = (
        ("General", {
            "fields": (
                "creator", "title", "description", "scrimmage_type", "custom_fields"
            )
        }),
        ("Location & Timing", {
            "fields": (
                "location", "location_name", "start_time", "end_time"
            )
        }),
        ("Financials", {
            "fields": (
                "entry_fee", "currency", "organizer_fee_percent", "prize_pool_amount"
            )
        }),
        ("Meta", {
            "fields": (
                "status", "visibility"
            )
        }),
    )


class ScrimmageParticipationInline(admin.TabularInline):
    model = ScrimmageParticipation
    extra = 1


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "start_date", "end_date", "is_active", "organizer")
    list_filter = ("category", "is_active", "start_date")
    search_fields = ("name", "description", "rules")
    prepopulated_fields = {"slug": ("name",)}



@admin.register(ScrimmageTemplate)
class ScrimmageTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "creator", "is_shared", "created_at")
    search_fields = ("title", "creator__email")
    list_filter = ("is_shared",)


@admin.register(RecurrenceRule)
class RecurrenceRuleAdmin(admin.ModelAdmin):
    list_display = ("scrimmage", "frequency", "interval", "active")







@admin.register(LeagueTeam)
class LeagueTeamAdmin(admin.ModelAdmin):
    list_display = ("name", "league", "wins", "losses", "draws", "points")
    list_filter = ("league",)

@admin.register(PerformanceStat)
class PerformanceStatAdmin(admin.ModelAdmin):
    list_display = ("user", "scrimmage", "created_at")
    search_fields = ("user__email", "scrimmage__title")


