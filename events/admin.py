from django.contrib import admin
from .models import Event, RSVP

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "host", "start", "end", "is_public", "status")
    search_fields = ("title", "description", "location_name")
    list_filter = ("is_public", "status", "start")
    ordering = ("-start",)

@admin.register(RSVP)
class RSVPAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__email", "event__title")
