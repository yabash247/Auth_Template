from rest_framework import serializers
from .models import CalendarItem

class CalendarItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarItem
        fields = "__all__"

# For FullCalendar-compatible output
class FullCalendarItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    url = serializers.CharField(allow_blank=True)
    color = serializers.CharField()
