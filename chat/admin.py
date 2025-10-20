from django.contrib import admin
from .models import MessageThread, Message

@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at", "updated_at")

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "thread", "created_at")
