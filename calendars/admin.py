from django.contrib import admin
from .models import CalendarItem

@admin.register(CalendarItem)
class CalendarItemAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "start", "end")
    list_filter = ("kind",)
    search_fields = ("title",)
