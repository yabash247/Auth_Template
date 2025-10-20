from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class MessageThread(models.Model):
    title = models.CharField(max_length=255)
    participants = models.ManyToManyField(User, related_name="message_threads")
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"Thread {self.pk}"


class Message(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages_sent")
    body = models.TextField()
    read_by = models.ManyToManyField(User, related_name="messages_read", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender}: {self.body[:40]}"
