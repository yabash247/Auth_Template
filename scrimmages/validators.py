import json
from django.core.exceptions import ValidationError
from django.utils import timezone


# ============================================================
# ✅ Dynamic Field Validation for ScrimmageType Schemas
# ============================================================

def validate_custom_fields(scrimmage_type, custom_fields: dict) -> dict:
    """
    Validate scrimmage.custom_fields against scrimmage_type.custom_field_schema.

    The schema format should look like:
        {
          "player_level": {"py_type":"str","choices":["Beginner","Intermediate","Pro"],"required":true},
          "min_age":{"py_type":"int","ge":8,"le":60},
          "referee_required":{"py_type":"bool","default":false}
        }
    Returns a dict of validation errors, or {} if valid.
    """

    errors = {}
    if not scrimmage_type or not scrimmage_type.custom_field_schema:
        return errors

    schema = scrimmage_type.custom_field_schema or {}
    fields = custom_fields or {}

    for field_name, field_def in schema.items():
        py_type = field_def.get("py_type", "str")
        required = field_def.get("required", False)
        choices = field_def.get("choices")
        ge = field_def.get("ge")
        le = field_def.get("le")

        # Required field check
        if required and field_name not in fields:
            errors[field_name] = "This field is required."
            continue

        # Skip validation if not provided and not required
        if field_name not in fields:
            continue

        value = fields[field_name]

        # Type validation
        if py_type == "int":
            if not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    errors[field_name] = "Must be an integer."
                    continue
            if ge is not None and value < ge:
                errors[field_name] = f"Must be ≥ {ge}."
            if le is not None and value > le:
                errors[field_name] = f"Must be ≤ {le}."

        elif py_type == "float":
            if not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    errors[field_name] = "Must be a number."
                    continue
            if ge is not None and value < ge:
                errors[field_name] = f"Must be ≥ {ge}."
            if le is not None and value > le:
                errors[field_name] = f"Must be ≤ {le}."

        elif py_type == "bool":
            if not isinstance(value, bool):
                if str(value).lower() in ["true", "1", "yes"]:
                    value = True
                elif str(value).lower() in ["false", "0", "no"]:
                    value = False
                else:
                    errors[field_name] = "Must be a boolean value."

        elif py_type == "str":
            if not isinstance(value, str):
                errors[field_name] = "Must be a string."

        # Choice validation
        if choices and value not in choices:
            errors[field_name] = f"Must be one of {choices}."

    return errors


# ============================================================
# ✅ Time Validation for Scrimmages
# ============================================================

def validate_scrimmage_dates(start_datetime, end_datetime):
    """Ensure end is after start and both are in the future."""
    if not start_datetime or not end_datetime:
        return
    if end_datetime <= start_datetime:
        raise ValidationError("End time must be after start time.")
    if start_datetime < timezone.now():
        raise ValidationError("Start time cannot be in the past.")


# ============================================================
# ✅ Media Upload Validation
# ============================================================

def validate_media_upload(user, scrimmage, file_size_bytes: int, max_files_per_user=5, max_total_bytes=50 * 1024 * 1024):
    """
    Enforce media upload limits:
    - max_files_per_user per scrimmage
    - max_total_bytes total per user
    """
    from .models import ScrimmageMedia

    user_uploads = ScrimmageMedia.objects.filter(scrimmage=scrimmage, uploader=user)
    total_files = user_uploads.count()
    total_bytes = sum(u.file_size for u in user_uploads)

    if total_files >= max_files_per_user:
        raise ValidationError(
            f"You've reached the upload limit ({max_files_per_user} files per scrimmage)."
        )

    if total_bytes + file_size_bytes > max_total_bytes:
        raise ValidationError(
            f"Total upload size exceeds {max_total_bytes / (1024 * 1024):.1f} MB limit."
        )


# ============================================================
# ✅ RSVP Role / Rating Validation
# ============================================================

def validate_rsvp_data(data):
    """Ensure rating is between 1–5 and role is valid."""
    valid_roles = {"player", "coach", "referee", "observer"}
    valid_status = {
        "interested",
        "pending_payment",
        "waitlisted",
        "going",
        "checked_in",
        "completed",
        "cancelled",
    }

    role = data.get("role")
    rating = data.get("rating")
    status = data.get("status")

    if role and role not in valid_roles:
        raise ValidationError(f"Invalid role: {role}. Must be one of {valid_roles}.")
    if status and status not in valid_status:
        raise ValidationError(f"Invalid status: {status}. Must be one of {valid_status}.")
    if rating is not None and not (1 <= int(rating) <= 5):
        raise ValidationError("Rating must be between 1 and 5.")


# ============================================================
# ✅ Waitlist Auto-Promotion Helper
# ============================================================

def promote_next_waitlisted(scrimmage):
    """
    Promote the earliest waitlisted RSVP if a slot opens.
    To be called in signals or post-delete hooks.
    """
    from .models import ScrimmageRSVP

    available_slots = scrimmage.spots_left
    if available_slots <= 0:
        return

    waitlisted = (
        ScrimmageRSVP.objects.filter(scrimmage=scrimmage, status="waitlisted")
        .order_by("created_at")[:available_slots]
    )
    for rsvp in waitlisted:
        rsvp.status = "going"
        rsvp.save(update_fields=["status"])
