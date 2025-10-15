# app: users
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


# ---------- Profile ----------
class UserProfile(models.Model):
    VISIBILITY = (("public", "Public"), ("private", "Private"), ("followers", "Followers only"))

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=120, blank=True)
    bio = models.CharField(max_length=280, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    cover_photo = models.ImageField(upload_to="covers/", null=True, blank=True)
    location = models.CharField(max_length=120, blank=True)
    website = models.URLField(blank=True)
    pronouns = models.CharField(max_length=50, blank=True)
    dob = models.DateField(null=True, blank=True)
    verified = models.BooleanField(default=False)
    visibility = models.CharField(max_length=20, choices=VISIBILITY, default="public")
    interests = models.JSONField(default=list, blank=True)  # ["basketball","tech"]
    is_creator = models.BooleanField(default=False)
    reputation_points = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    followers = models.ManyToManyField(
        User, through="Follow", related_name="following_profiles", blank=True
    )

    def __str__(self):
        return f"{self.user} Profile"


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="follows")
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="followed_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "profile")


# ---------- Membership & Payments ----------
class MembershipPlan(models.Model):
    INTERVALS = (("month", "Monthly"), ("year", "Yearly"))
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=9, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    interval = models.CharField(max_length=10, choices=INTERVALS, default="month")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} {self.price} {self.currency}/{self.interval}"


class Membership(models.Model):
    STATUS = (("active", "Active"), ("past_due", "Past Due"), ("canceled", "Canceled"), ("expired", "Expired"))

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=12, choices=STATUS, default="active")
    started_at = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()  # when the current paid period ends
    auto_renew = models.BooleanField(default=True)
    next_due_amount = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    next_due_date = models.DateTimeField(null=True, blank=True)
    external_ref = models.CharField(max_length=120, blank=True)  # e.g., Stripe sub id

    def __str__(self):
        return f"{self.user} → {self.plan} ({self.status})"


class Payment(models.Model):
    STATUS = (("succeeded", "Succeeded"), ("failed", "Failed"), ("pending", "Pending"), ("refunded", "Refunded"))
    METHOD = (("card", "Card"), ("bank", "Bank"), ("wallet", "Wallet"), ("cash", "Cash"))

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    membership = models.ForeignKey(Membership, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    method = models.CharField(max_length=12, choices=METHOD, default="card")
    provider = models.CharField(max_length=40, blank=True)         # "stripe","paypal"
    provider_ref = models.CharField(max_length=120, blank=True)    # charge/payment id
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user} ${self.amount} {self.status}"


# ---------- Groups ----------
class Group(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_groups")
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="group_avatars/", null=True, blank=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(User, through="GroupMember", related_name="member_groups", blank=True)


    def __str__(self):
        return self.name


class GroupMember(models.Model):
    ROLES = (("member", "Member"), ("moderator", "Moderator"), ("organizer", "Organizer"))
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=ROLES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "group")


# ---------- Events & RSVP ----------
class Event(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="hosted_events")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    location_name = models.CharField(max_length=160, blank=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_public = models.BooleanField(default=True)
    cover = models.ImageField(upload_to="event_covers/", null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.title


class RSVP(models.Model):
    STATUS = (("going", "Going"), ("interested", "Interested"), ("waitlist", "Waitlist"), ("not_going", "Not Going"), ("checked_in", "Checked-in"))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rsvps")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rsvps")
    status = models.CharField(max_length=16, choices=STATUS, default="interested")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "event")


# ---------- Personal Calendar ----------
class CalendarItem(models.Model):
    KIND = (("personal", "Personal"), ("event", "Event"))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="calendar_items")
    kind = models.CharField(max_length=12, choices=KIND, default="personal")
    title = models.CharField(max_length=160)
    start = models.DateTimeField()
    end = models.DateTimeField()
    notes = models.TextField(blank=True)
    # If kind == "event" you can link:
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("start",)

    def __str__(self):
        return f"{self.title} ({self.kind})"


from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# --------- Notifications ----------
class Notification(models.Model):
    NOTIF_TYPES = (
        ("membership", "Membership"),
        ("payment", "Payment"),
        ("event", "Event"),
        ("message", "Message"),
        ("system", "System"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=NOTIF_TYPES, default="system")
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=255, blank=True)  # deeplink to frontend
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user} - {self.kind} - {self.title}"


# --------- Chat (Threads & Messages) ----------
class MessageThread(models.Model):
    participants = models.ManyToManyField(User, related_name="message_threads", blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # bump on new message

    def __str__(self):
        return f"Thread {self.id}"

class Message(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(User, related_name="read_messages", blank=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"Msg {self.id} by {self.sender}"
