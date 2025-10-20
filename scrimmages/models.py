# scrimmages/models.py
from __future__ import annotations
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


class ScrimmageCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "category"
            self.slug = base if not ScrimmageCategory.objects.filter(slug=base).exists() else f"{base}-{self.pk or ''}".strip("-")
        return super().save(*args, **kwargs)

    def __str__(self): return self.name


class ScrimmageType(models.Model):
    """
    Each type can define its dynamic field schema.
    Example schema (you own the format):
    {
      "player_level": {"py_type":"str","choices":["Beginner","Intermediate","Pro"],"required":true},
      "min_age":{"py_type":"int","ge":8,"le":60},
      "referee_required":{"py_type":"bool","required":false, "default": false}
    }
    """
    category = models.ForeignKey(ScrimmageCategory, on_delete=models.CASCADE, related_name="types")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    custom_field_schema = models.JSONField(default=dict, blank=True)  # creator form generator + validator

    class Meta:
        unique_together = [("category", "name")]
        ordering = ["category__name", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.category.name}-{self.name}")[:150] or "type"
            slug = base
            i = 1
            while ScrimmageType.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        return super().save(*args, **kwargs)

    def __str__(self): return f"{self.category.name} · {self.name}"


class Scrimmage(models.Model):
    VISIBILITY = [("public", "Public"), ("private", "Private")]
    STATUS = [("draft","Draft"),("published","Published"),("cancelled","Cancelled")]

    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scrimmages_created")
    group = models.ForeignKey("groups.Group", null=True, blank=True, on_delete=models.SET_NULL, related_name="scrimmages")

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)

    # NEW: taxonomy + dynamic fields
    scrimmage_type = models.ForeignKey(ScrimmageType, on_delete=models.PROTECT, related_name="scrimmages")
    custom_fields = models.JSONField(default=dict, blank=True)  # validated against scrimmage_type.custom_field_schema

    # Location (shared object lives in organizations app)
    location = models.ForeignKey("organizations.Location", null=True, blank=True, on_delete=models.SET_NULL, related_name="scrimmages")
    location_name = models.CharField(max_length=255, blank=True)  # snapshot for history
    address = models.CharField(max_length=512, blank=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    is_recurring = models.BooleanField(default=False)
    # If you also want raw RRULE text for iCal export:
    rrule = models.CharField(max_length=255, blank=True)

    max_participants = models.PositiveIntegerField(default=10)
    visibility = models.CharField(max_length=10, choices=VISIBILITY, default="public")
    tags = models.JSONField(default=list, blank=True)

    # monetization
    entry_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    team_pay_enabled = models.BooleanField(default=False)
    organizer_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    organizer_fee_flat = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    prize_pool_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    CATEGORY_CHOICES = [
        ("basketball", "Basketball"),
        ("football", "Football"),
        ("soccer", "Soccer"),
        ("volleyball", "Volleyball"),
        ("other", "Other"),
    ]

    category = models.CharField(
        max_length=32,
        choices=CATEGORY_CHOICES,
        default="basketball"
    )

    status = models.CharField(max_length=12, choices=STATUS, default="published")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta: ordering = ["start_time"]

    def __str__(self): return self.title

    def clean(self):
        # simple time sanity
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})

        # validate custom_fields with Pydantic (see helper below)
        from .validators import validate_custom_fields
        errors = validate_custom_fields(self.scrimmage_type, self.custom_fields)
        if errors:
            raise ValidationError({"custom_fields": errors})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "scrimmage"
            slug = base
            i = 1
            while Scrimmage.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)






class RecurrenceRule(models.Model):
    FREQ = [("weekly","Weekly"),("monthly","Monthly")]
    scrimmage = models.OneToOneField(Scrimmage, on_delete=models.CASCADE, related_name="recurrence_rule")
    frequency = models.CharField(max_length=20, choices=FREQ)
    interval = models.PositiveIntegerField(default=1)         # every N weeks/months
    day_of_week = models.CharField(max_length=9, blank=True)  # e.g., "saturday"
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self): return f"{self.scrimmage.title} · {self.frequency}/{self.interval}"


class ScrimmageTemplate(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scrimmage_templates")
    title = models.CharField(max_length=255)
    scrimmage_type = models.ForeignKey(ScrimmageType, on_delete=models.CASCADE)
    base_settings = models.JSONField(default=dict, blank=True)  # everything to clone: times, fees, rules, custom_fields, location_id snapshot
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.title


class ScrimmageParticipation(models.Model):
    ROLES = [("player","Player"),("coach","Coach"),("referee","Referee"),("observer","Observer")]
    STATUS = [("invited","Invited"),("confirmed","Confirmed"),("declined","Declined"),("checked_in","Checked In")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scrimmage_participations")
    scrimmage = models.ForeignKey(Scrimmage, on_delete=models.CASCADE, related_name="participants")
    role = models.CharField(max_length=16, choices=ROLES, default="player")
    status = models.CharField(max_length=16, choices=STATUS, default="confirmed")
    rating = models.FloatField(default=0)
    notes = models.TextField(blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user","scrimmage")]
        ordering = ["-joined_at"]

    def __str__(self): return f"{self.user} → {self.scrimmage} ({self.status})"



class League(models.Model):
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leagues")
    group = models.ForeignKey("groups.Group", null=True, blank=True, on_delete=models.SET_NULL, related_name="leagues")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    category = models.CharField(max_length=32, choices=Scrimmage.CATEGORY_CHOICES, default="basketball")
    description = models.TextField(blank=True)
    rules = models.TextField(blank=True)
    commitment_level = models.CharField(max_length=100, blank=True)

    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    max_teams = models.PositiveIntegerField(default=16)
    team_size_min = models.PositiveIntegerField(default=3)
    team_size_max = models.PositiveIntegerField(default=10)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "league"
            self.slug = base
            i = 1
            Model = self.__class__
            while Model.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                i += 1
                self.slug = f"{base}-{i}"
        super().save(*args, **kwargs)


class LeagueTeam(models.Model):
    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name="teams",
        null=True,     # ✅ add this
        blank=True,    # ✅ add this
    )
    # tie teams to Groups (your existing team container), or use a plain name
    group = models.ForeignKey("groups.Group", null=True, blank=True, on_delete=models.SET_NULL, related_name="league_teams")
    name = models.CharField(max_length=255, blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="owned_league_teams")

    join_code = models.CharField(max_length=12, blank=True)

    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    draws = models.PositiveIntegerField(default=0)
    points = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("league", "name")]
        ordering = ["-points", "name"]

    def __str__(self):
        return self.name or (self.group.name if self.group_id else f"Team {self.pk}")


class PerformanceStat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="performance_stats")
    scrimmage = models.ForeignKey(Scrimmage, on_delete=models.CASCADE, related_name="stats")
    metrics = models.JSONField(default=dict, blank=True)  # sport/instrument specific
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("user", "scrimmage")]
