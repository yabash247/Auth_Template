from django.db import models
from django.conf import settings
from accounts.models import Policy

class Organization(models.Model):
    name = models.CharField(max_length=128)
    policy = models.ForeignKey(Policy, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

class Membership(models.Model):
    ROLE_CHOICES = [("owner","Owner"), ("admin","Admin"), ("member","Member")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="member")

    class Meta:
        unique_together = ("user", "organization")
