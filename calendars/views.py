from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import CalendarItem
from .serializers import CalendarItemSerializer, FullCalendarItemSerializer

class CalendarViewSet(viewsets.ModelViewSet):
    serializer_class = CalendarItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CalendarItem.objects.filter(user=self.request.user).select_related("event")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"])
    def fullcalendar(self, request):
        items = self.get_queryset()
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if start and end:
            items = items.filter(start__lt=end, end__gt=start)
        payload = [
            {
                "id": item.id,
                "title": item.title,
                "start": item.start,
                "end": item.end,
                "url": f"/events/{item.event_id}" if item.event_id else "",
                "color": "#2563eb" if item.kind == "event" else "#10b981",
            }
            for item in items
        ]
        return Response(FullCalendarItemSerializer(payload, many=True).data)
