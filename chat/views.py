from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import MessageThread, Message
from .serializers import MessageThreadSerializer, MessageSerializer
from notifications.models import Notification

class MessageThreadViewSet(viewsets.ModelViewSet):
    serializer_class = MessageThreadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MessageThread.objects.filter(participants=self.request.user).prefetch_related("participants", "messages")

    def perform_create(self, serializer):
        thread = serializer.save()
        pids = self.request.data.get("participants", [])
        from django.contrib.auth import get_user_model
        User = get_user_model()
        thread.participants.add(self.request.user, *User.objects.filter(id__in=pids))
        thread.save()

    @action(detail=True, methods=["post"])
    def add_participant(self, request, pk=None):
        thread = self.get_object()
        pid = request.data.get("user_id")
        if not pid:
            return Response({"detail": "user_id required"}, status=400)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        thread.participants.add(get_object_or_404(User, id=pid))
        return Response({"detail": "Participant added"})

    @action(detail=True, methods=["post"])
    def remove_participant(self, request, pk=None):
        thread = self.get_object()
        pid = request.data.get("user_id")
        if not pid:
            return Response({"detail": "user_id required"}, status=400)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        thread.participants.remove(get_object_or_404(User, id=pid))
        return Response({"detail": "Participant removed"})


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        thread_id = self.request.query_params.get("thread")
        qs = Message.objects.filter(thread__participants=self.request.user)
        if thread_id:
            qs = qs.filter(thread_id=thread_id)
        return qs.select_related("thread", "sender")

    def perform_create(self, serializer):
        thread_id = self.request.data.get("thread")
        thread = get_object_or_404(MessageThread, id=thread_id, participants=self.request.user)
        msg = serializer.save(sender=self.request.user, thread=thread)
        others = thread.participants.exclude(id=self.request.user.id)
        for u in others:
            Notification.objects.create(
                user=u,
                kind="message",
                title="New message",
                body=msg.body[:140],
                url=f"/messages?thread={thread.id}",
            )
        thread.save()

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        msg = self.get_object()
        msg.read_by.add(request.user)
        return Response({"detail": "Message marked as read"})
