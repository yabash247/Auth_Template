from django.contrib import admin
from .models import Group, GroupMember

class GroupMemberInline(admin.TabularInline):
    model = GroupMember
    extra = 0

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name",)
    inlines = [GroupMemberInline]

@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "role", "joined_at")
