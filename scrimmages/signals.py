from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings

from .models import (
    Scrimmage,
    ScrimmageRSVP,
    ScrimmageMedia,
    RecurrenceRule,
)
from datetime import timedelta

# Optional imports for integrations
try:
    from notifications.models import Notification
except ImportError:
    Notification = None

try:
    from calendars.models import CalendarItem
except ImportError:
    CalendarItem = None

try:
    from payments.models import Payment
except ImportError:
    Payment = None


# ============================================================
# ✅ Helper functions
# ============================================================

def create_notification(user, title,  body, url=None, kind="scrimmage"):
    """Utility: create a notification if the Notifications app exists."""
    if Notification:
        Notification.objects.create(
            user=user,
            kind=kind,
            title=title,
            body=body,
            url=url or "",
        )


def create_calendar_entry(user, scrimmage):
    """Utility: create a CalendarItem if Calendars app exists."""
    if CalendarItem:
        CalendarItem.objects.get_or_create(
            user=user,
            kind="scrimmage",
            title=scrimmage.title,
            start=scrimmage.start_datetime,
            end=scrimmage.end_datetime,
            #defaults={"description": scrimmage.description or ""},
        )


# ============================================================
# ✅ Scrimmage creation → Calendar + Notifications
# ============================================================
@receiver(post_save, sender=Scrimmage)
def handle_scrimmage_created(sender, instance: Scrimmage, created, **kwargs):
    if created:
        # Add scrimmage to host's calendar
        create_calendar_entry(instance.host, instance)

        # Notify host (and potentially group or league)
        create_notification(
            user=instance.host,
            title=f"New scrimmage created: {instance.title}",
            body="A new scrimmage has been added to your calendar.",
            url=f"/scrimmages/{instance.id}/",
        )

        # Optionally, notify members of a group or league
        if instance.group and hasattr(instance.group, "members"):
            for member in instance.group.members.exclude(id=instance.host.id):
                create_notification(
                    member,
                    title="New Group Scrimmage",
                    body=f"{instance.host} created a new scrimmage '{instance.title}' in your group.",
                    url=f"/scrimmages/{instance.id}/",
                )


# ============================================================
# ✅ RSVP created or updated → Calendar + Notifications
# ============================================================
@receiver(post_save, sender=ScrimmageRSVP)
def handle_rsvp_updated(sender, instance: ScrimmageRSVP, created, **kwargs):
    scrimmage = instance.scrimmage
    user = instance.user

    # Add to user's calendar when confirmed "going"
    if instance.status == "going":
        create_calendar_entry(user, scrimmage)
        create_notification(
            user,
            title="RSVP Confirmed",
            body=f"You are confirmed for scrimmage '{scrimmage.title}'.",
            url=f"/scrimmages/{scrimmage.id}/",
        )

    # Handle auto-promotion from waitlist
    if instance.status == "waitlisted":
        if scrimmage.spots_left > 0:
            instance.status = "going"
            instance.save(update_fields=["status"])
            create_notification(
                user,
                title="Promoted to Going",
                body=f"A spot opened up for '{scrimmage.title}'. You're now marked as going!",
                url=f"/scrimmages/{scrimmage.id}/",
            )

    # Optional: refund trigger if cancelled
    if instance.status == "cancelled" and scrimmage.is_paid and Payment:
        payments = Payment.objects.filter(
            user=user, scrimmage_id=scrimmage.id, status="succeeded"
        )
        for pay in payments:
            pay.refund(reason="User cancelled RSVP")
        create_notification(
            user,
            title="RSVP Cancelled",
            body=f"Your RSVP for '{scrimmage.title}' was cancelled. Refund initiated if applicable.",
            url=f"/scrimmages/{scrimmage.id}/",
        )


# ============================================================
# ✅ Media uploaded → Notify host & participants
# ============================================================
@receiver(post_save, sender=ScrimmageMedia)
def handle_media_uploaded(sender, instance: ScrimmageMedia, created, **kwargs):
    if not created:
        return
    scrimmage = instance.scrimmage
    uploader = instance.uploader

    # Notify host
    create_notification(
        scrimmage.host,
        title="New Media Upload",
        body=f"{uploader} uploaded new media to '{scrimmage.title}'.",
        url=f"/scrimmages/{scrimmage.id}/",
    )

    # Notify all participants except uploader
    participants = scrimmage.rsvps.filter(
        status__in=["going", "checked_in", "completed"]
    ).exclude(user=uploader)
    for rsvp in participants:
        create_notification(
            rsvp.user,
            title="New Scrimmage Media",
            body=f"New highlight uploaded to '{scrimmage.title}'.",
            url=f"/scrimmages/{scrimmage.id}/",
        )


# ============================================================
# ✅ RecurrenceRule handler → auto-generate next event
# ============================================================
@receiver(post_save, sender=RecurrenceRule)
def handle_recurrence_rule(sender, instance: RecurrenceRule, created, **kwargs):
    """
    When RecurrenceRule is saved and active, generate next occurrence(s)
    if auto_generate=True.
    This logic can also be called manually by a management command.
    """
    if not instance.auto_generate or not instance.active:
        return

    base = instance.scrimmage
    freq = instance.frequency
    interval = instance.interval or 1

    if freq == "weekly":
        delta = timedelta(weeks=interval)
    else:
        delta = timedelta(days=30 * interval)

    next_start = base.start_datetime + delta
    next_end = base.end_datetime + delta

    # Prevent duplication: only create if no upcoming copy
    exists = Scrimmage.objects.filter(
        host=base.host,
        title=base.title,
        start_datetime__date=next_start.date(),
    ).exists()
    if exists:
        return

    new_scrimmage = Scrimmage.objects.create(
        host=base.host,
        title=base.title,
        description=base.description,
        category=base.category,
        scrimmage_type=base.scrimmage_type,
        visibility=base.visibility,
        location_name=base.location_name,
        address=base.address,
        latitude=base.latitude,
        longitude=base.longitude,
        start_datetime=next_start,
        end_datetime=next_end,
        max_participants=base.max_participants,
        entry_fee=base.entry_fee,
        currency=base.currency,
        credit_required=False,
        is_paid=base.is_paid,
        teams=base.teams,
        status="upcoming",
    )

    create_notification(
        base.host,
        title="Recurring Scrimmage Generated",
        body=f"A new occurrence of '{base.title}' has been created automatically.",
        url=f"/scrimmages/{new_scrimmage.id}/",
    )
    create_calendar_entry(base.host, new_scrimmage)


# ============================================================
# ✅ Scrimmage deleted → cleanup
# ============================================================
@receiver(post_delete, sender=Scrimmage)
def handle_scrimmage_deleted(sender, instance: Scrimmage, **kwargs):
    if CalendarItem:
        CalendarItem.objects.filter(
            title=instance.title, user=instance.host, kind="scrimmage"
        ).delete()

    if Notification:
        Notification.objects.filter(
            url__icontains=f"/scrimmages/{instance.id}/"
        ).delete()
