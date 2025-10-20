# scrimmages/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
from .models import Scrimmage, ScrimmageParticipation
from payments.utils import process_auto_payment
from decimal import Decimal

def _get_model(app_label, model_name):
    return apps.get_model(app_label, model_name)


@receiver(post_save, sender=ScrimmageParticipation)
def auto_charge_entry_fee(sender, instance, created, **kwargs):
    """
    When a user joins a scrimmage, auto-charge entry fee if auto-pay is enabled.
    """
    scrimmage = instance.scrimmage
    user = instance.user

    if created and scrimmage.entry_fee > 0 and scrimmage.auto_pay_enabled:
        result = process_auto_payment(
            user=user,
            amount=scrimmage.entry_fee,
            app_source="scrimmage",
            related_id=scrimmage.id,
            description=f"Entry fee for {scrimmage.title}",  # 👈 ← COMMA HERE
            organizer=scrimmage.creator,                     # organizer receiving fee
            organizer_fee_percent=scrimmage.organizer_fee_percent,
            organizer_fee_flat=scrimmage.organizer_fee_flat,
            team_pay=scrimmage.team_pay_enabled,
            charge_account=scrimmage.creator if scrimmage.team_pay_enabled else None,
        )
        print(f"[Scrimmage AutoPay] {user.email}: {result}")


@receiver(post_save, sender=Scrimmage)
def create_event_calendar_and_thread(sender, instance: Scrimmage, created, **kwargs):
    if not created:
        return

    # --- Create Event (events app) ---
    try:
        Event = _get_model("events", "Event")
        event = Event.objects.create(
            host=instance.creator,
            group=instance.group,
            title=instance.title,
            description=instance.description,
            location_name=instance.location_name,
            address=instance.address,
            start=instance.start_time,
            end=instance.end_time,
            is_public=(instance.visibility == "public"),
            tags=instance.tags,
        )
    except Exception as e:
        print(f"[scrimmages] Skipped Event creation: {e}")
        event = None

    # --- Calendar entry (calendar app) ---
    try:
        CalendarItem = _get_model("calendars", "CalendarItem")  # if your calendar app label differs, adjust here
        CalendarItem.objects.create(
            user=instance.creator,
            kind="event",
            title=instance.title,
            start=instance.start_time,
            end=instance.end_time,
            event_id=getattr(event, "id", None),
        )
    except Exception as e:
        print(f"[scrimmages] Skipped CalendarItem creation: {e}")

    # --- Chat thread (chat app) ---
    try:
        MessageThread = _get_model("chat", "MessageThread")
        thread = MessageThread.objects.create(title=f"Scrimmage: {instance.title}")
        # add creator + current group members (if any)
        thread.participants.add(instance.creator)
        if instance.group_id:
            GroupMember = _get_model("groups", "GroupMember")
            for gm in GroupMember.objects.filter(group=instance.group).select_related("user"):
                thread.participants.add(gm.user)
        thread.save()
    except Exception as e:
        print(f"[scrimmages] Skipped MessageThread creation: {e}")

    # --- Notification to creator (notifications app) ---
    try:
        Notification = _get_model("notifications", "Notification")
        Notification.objects.create(
            user=instance.creator,
            kind="scrimmage",
            title="Scrimmage created",
            body=f"'{instance.title}' was created for {instance.start_time:%b %d, %Y %I:%M%p}.",
            url=f"/scrimmages/{instance.slug}",
        )
    except Exception as e:
        print(f"[scrimmages] Skipped Notification creation: {e}")
