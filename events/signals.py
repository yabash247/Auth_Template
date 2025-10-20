# events/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Event
from payments.utils import process_auto_payment
from decimal import Decimal

@receiver(post_save, sender=Event)
def auto_charge_event_entry_fee(sender, instance, created, **kwargs):
    """
    When an event is created and marked auto-pay, charge the host or participants (future extension).
    """
    if created and instance.entry_fee > 0 and instance.auto_pay_enabled:
        # For now, charge the event creator (host)
        user = instance.host
        result = process_auto_payment(
            user=user,
            amount=Decimal(instance.entry_fee),
            app_source="event",
            related_id=instance.id,
            description=f"Event setup fee for {instance.title}",
            organizer=instance.host,  # host collects fee if you wish, or set to None
            organizer_fee_percent=instance.organizer_fee_percent,
            organizer_fee_flat=instance.organizer_fee_flat,
        )
        print(f"[Event AutoPay] {user.email}: {result}")
