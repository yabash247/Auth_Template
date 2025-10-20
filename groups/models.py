from django.db import models
from django.conf import settings
from django.utils.text import slugify

User = settings.AUTH_USER_MODEL

class Group(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_groups")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            self.slug = base
            i = 1
            while Group.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                i += 1
                self.slug = f"{base}-{i}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class GroupMember(models.Model):
    ROLE_CHOICES = [
        ("organizer", "Organizer"),
        ("member", "Member"),
        ("guest", "Guest"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_memberships")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "group")]

    def __str__(self):
        return f"{self.user} in {self.group}"
