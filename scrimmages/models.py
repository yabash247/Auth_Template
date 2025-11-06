from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL

from django.contrib.contenttypes.fields import GenericRelation
from media.models import MediaRelation
media_relations = GenericRelation(MediaRelation)

from organizations.models import Location  # 👈 add this import at the top




# ============================================================
# ✅ Scrimmage Category (user-suggested, admin-approved)
#   - Unapproved categories are visible only to their creator.
#   - Approved names must be globally unique.
# ============================================================
class ScrimmageCategory(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="scrimmage_categories"
    )
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["approved", "created_at"]),
        ]
        constraints = [
            # Prevent two approved categories with the same name
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(approved=True),
                name="uniq_public_category_name",
            ),
            # A user can propose the same name only once
            models.UniqueConstraint(
                fields=["name", "created_by"],
                name="uniq_user_category_proposal",
            ),
        ]

    def __str__(self) -> str:
        return self.name


# ============================================================
# ✅ Scrimmage Type (user-created, admin-approved)
#   - Linked to a Category.
#   - Optional on Scrimmage (acts like a format: "3v3", "Hackathon").
#   - Unapproved types are visible only to their creator.
# ============================================================
class ScrimmageType(models.Model):
    category = models.ForeignKey(
        ScrimmageCategory, on_delete=models.CASCADE, related_name="types"
    )
    name = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="scrimmage_types",
        null=True,
        blank=True
    )
    approved = models.BooleanField(default=False)
    # Optional: schema for dynamic/extra fields the frontend may render
    custom_field_schema = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["category__name", "name"]
        indexes = [
            models.Index(fields=["approved", "category"]),
        ]
        constraints = [
            # Prevent duplicate public type names within a category
            models.UniqueConstraint(
                fields=["category", "name"],
                condition=Q(approved=True),
                name="uniq_public_type_per_category",
            ),
            # A user can propose the same (category, name) only once
            models.UniqueConstraint(
                fields=["category", "name", "created_by"],
                name="uniq_user_type_proposal",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.category.name} · {self.name}"


# ============================================================
# ✅ Scrimmage (Meetup-style)
#   - Visibility, location (map-ready), scheduling
#   - Capacity, waitlist, entry fee, teams JSON
#   - Ratings aggregates
#   - Credit gating supported via business logic in views/payments
# ============================================================
class Scrimmage(models.Model):
    VISIBILITY = (
        ("public", "Public"),
        ("members", "Members"),
        ("private", "Private"),
    )
    STATUS = (
        ("draft", "Draft"),
        ("upcoming", "Upcoming"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    host = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="hosted_scrimmages"
    )
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrimmages",
    )
    league = models.ForeignKey(
        "leagues.League",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrimmages",
    )

    category = models.ForeignKey(
        ScrimmageCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrimmages",
    )
    scrimmage_type = models.ForeignKey(
        ScrimmageType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrimmages",
        help_text="Optional format/type (e.g., 3v3, hackathon, cookoff).",
    )

    visibility = models.CharField(max_length=10, choices=VISIBILITY, default="public")

    # Location (map-friendly)
    #location_name = models.CharField(max_length=160, blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrimmages",
        help_text="Select an organization location for this scrimmage."
    )
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Schedule
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    # Capacity
    max_participants = models.PositiveIntegerField(default=20)
    waitlist_enabled = models.BooleanField(default=True)

    # Payments
    entry_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    currency = models.CharField(max_length=6, default="USD")
    credit_required = models.BooleanField(
        default=False,
        help_text="True when creator lacked credits; publish after payment/credit.",
    )
    is_paid = models.BooleanField(
        default=False, help_text="Derived from entry_fee > 0"
    )

    # Flexible team structure
    # Example: {"Team A": [user_id,...], "Team B": [user_id,...]}
    teams = models.JSONField(default=dict, blank=True)

    # Ratings aggregate
    rating_avg = models.FloatField(default=0)
    rating_count = models.PositiveIntegerField(default=0)

    # Lifecycle
    status = models.CharField(max_length=10, choices=STATUS, default="draft")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    media_relations = GenericRelation(
        MediaRelation, 
        related_query_name='scrimmage',
        content_type_field="content_type",
        object_id_field="object_id"
    )

    class Meta:
        ordering = ["start_datetime"]
        indexes = [
            models.Index(fields=["status", "start_datetime"]),
            models.Index(fields=["visibility", "start_datetime"]),
            models.Index(fields=["category", "start_datetime"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"

    def clean(self):
        # Only check if both dates are provided
        if self.start_datetime and self.end_datetime and self.end_datetime <= self.start_datetime:
            raise ValidationError("End time must be after start time.")

    def save(self, *args, **kwargs):
        self.is_paid = (self.entry_fee or 0) > 0
        super().save(*args, **kwargs)

    def get_media_by_context(self, context_name: str):
        """
        Retrieve approved media for this scrimmage filtered by placement context.
        Example: scrimmage.get_media_by_context('icon')
        """
        return self.media_relations.filter(
            app_name="scrimmages",
            model_name="scrimmage",
            context_name=context_name,
            approved=True,
        ).select_related("media")

    # 🟨 REORDERED for clarity (spots_taken and spots_left grouped last)
    @property
    def spots_taken(self) -> int:
        return self.rsvps.filter(
            status__in=["going", "checked_in", "completed", "pending_payment"]
        ).count()

    @property
    def spots_left(self) -> int:
        taken = self.rsvps.filter(
            status__in=["going", "checked_in", "completed"]
        ).count()
        return max(self.max_participants - taken, 0)


# ============================================================
# ✅ RSVP (attendance, role, feedback, rating, waitlist)
# ============================================================
class ScrimmageRSVP(models.Model):
    STATUS = (
        ("interested", "Interested"),
        ("pending_payment", "Pending Payment"),
        ("waitlisted", "Waitlisted"),
        ("going", "Going"),
        ("checked_in", "Checked In"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )
    ROLE = (
        ("player", "Player"),
        ("coach", "Coach"),
        ("referee", "Referee"),
        ("observer", "Observer"),
    )

    scrimmage = models.ForeignKey(
        Scrimmage, on_delete=models.CASCADE, related_name="rsvps"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="scrimmage_rsvps"
    )

    status = models.CharField(max_length=20, choices=STATUS, default="interested")
    role = models.CharField(max_length=16, choices=ROLE, default="player")

    team_name = models.CharField(max_length=50, blank=True, null=True)
    score = models.CharField(max_length=50, blank=True, null=True)

    # Post-event feedback & rating
    feedback = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    checked_in_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["scrimmage", "status", "created_at"]),
            models.Index(fields=["user", "scrimmage"]),
        ]
        unique_together = ("scrimmage", "user")

    def __str__(self) -> str:
        return f"{self.user} → {self.scrimmage} [{self.status}/{self.role}]"


# ============================================================
# ✅ Participant Media (host moderation + limits via views)
# ============================================================
class ScrimmageMedia(models.Model):
    scrimmage = models.ForeignKey(
        Scrimmage, on_delete=models.CASCADE, related_name="media_files"
    )
    uploader = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uploaded_scrimmage_media"
    )
    media = models.ForeignKey(
        "media.Media", on_delete=models.CASCADE, related_name="scrimmage_links"
    )

    caption = models.CharField(max_length=255, blank=True)
    approved = models.BooleanField(default=True)
    file_size = models.BigIntegerField(default=0)  # bytes
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["scrimmage", "approved", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.scrimmage.title} – {self.uploader}"


# ============================================================
# ✅ Recurrence Rule (manual mgmt command/cron support)
#   - Use a management command to scan active rules and create
#     the next occurrence(s) based on frequency/interval.
# ============================================================
class RecurrenceRule(models.Model):
    FREQ = (("weekly", "Weekly"), ("monthly", "Monthly"))

    scrimmage = models.OneToOneField(
        Scrimmage, on_delete=models.CASCADE, related_name="recurrence_rule"
    )
    frequency = models.CharField(max_length=20, choices=FREQ)
    interval = models.PositiveIntegerField(default=1)  # every N weeks/months
    day_of_week = models.CharField(max_length=9, blank=True)  # e.g., "saturday"
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    # Behavior flags
    auto_generate = models.BooleanField(
        default=True, help_text="When processed, create next occurrences automatically."
    )
    suggest_similar = models.BooleanField(
        default=True, help_text="Suggest this pattern in create forms."
    )

    class Meta:
        indexes = [
            models.Index(fields=["active", "frequency", "interval"]),
        ]

    def __str__(self) -> str:
        return f"{self.scrimmage.title} · {self.frequency}/{self.interval}"


# ============================================================
# ✅ Templates (shareable; admin-approved to go public)
#   - base_settings can store any fields used to prefill a Scrimmage.
# ============================================================
class ScrimmageTemplate(models.Model):
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="scrimmage_templates"
    )
    title = models.CharField(max_length=255)
    scrimmage_type = models.ForeignKey(
        ScrimmageType, on_delete=models.SET_NULL, null=True, blank=True
    )

    base_settings = models.JSONField(
        default=dict, blank=True, help_text="Prefill payload for creating scrimmages."
    )

    # Sharing & approval
    is_shared = models.BooleanField(
        default=False, help_text="Visible to others if approved."
    )
    approved = models.BooleanField(
        default=False, help_text="Admin approval required for public use."
    )
    is_public = models.BooleanField(
        default=False, help_text="Listed in global template library once approved."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_shared", "approved", "is_public"]),
        ]

    def __str__(self) -> str:
        return self.title


# ============================================================
# ✅ Performance Statistics (sports/creative scoring)
# ============================================================
class PerformanceStat(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="performance_stats"
    )
    scrimmage = models.ForeignKey(
        Scrimmage, on_delete=models.CASCADE, related_name="stats"
    )
    metrics = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("user", "scrimmage")]

    def __str__(self) -> str:
        return f"Stats for {self.user} – {self.scrimmage}"
