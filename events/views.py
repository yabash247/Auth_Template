from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Event
from .serializers import EventSerializer
from payments.utils import bulk_refund

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.select_related("host", "group").order_by("start")
    serializer_class = EventSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAuthenticatedOrReadOnly()]
    
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        event = self.get_object()
        event.status = "cancelled"
        event.save(update_fields=["status"])
        results = bulk_refund("event", event.id)
        return Response({"detail": "Event cancelled, refunds processed.", "results": results})
