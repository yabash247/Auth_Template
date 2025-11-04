from rest_framework.permissions import BasePermission, SAFE_METHODS


# ============================================================
# ✅ General helper permissions
# ============================================================

class IsHostOrAdmin(BasePermission):
    """
    Allow access if the user is the scrimmage host or an admin.
    """

    def has_object_permission(self, request, view, obj):
        host = getattr(obj, "host", None)
        return request.user and (request.user.is_staff or host == request.user)


class IsOwnerOrReadOnly(BasePermission):
    """
    Safe methods allowed for all, edits allowed only for owner or admin.
    Used for user-created objects like Category, Type, Template, Media, etc.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, "created_by", None) or getattr(obj, "creator", None) or getattr(obj, "uploader", None)
        return owner == request.user or request.user.is_staff


# ============================================================
# ✅ Scrimmage Permissions
# ============================================================

class ScrimmagePermission(BasePermission):
    """
    - Read: everyone if public, or limited by visibility.
    - Write: only host or admin.
    - Draft scrimmages visible only to host/admin.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            # Public visibility logic
            if obj.visibility == "public":
                return True
            elif obj.visibility == "members":
                # If user belongs to same group or league (optional)
                group = getattr(obj, "group", None)
                league = getattr(obj, "league", None)
                user = request.user
                if not user.is_authenticated:
                    return False
                if user.is_staff or obj.host == user:
                    return True
                if group and hasattr(group, "members") and user in group.members.all():
                    return True
                if league and hasattr(league, "members") and user in league.members.all():
                    return True
                return False
            elif obj.visibility == "private":
                # Private: host or participant only
                if request.user.is_authenticated and (
                    request.user == obj.host or
                    obj.rsvps.filter(user=request.user).exists()
                ):
                    return True
                return False
            return False
        # Write/update/delete: host or admin
        return request.user.is_authenticated and (
            request.user == obj.host or request.user.is_staff
        )


# ============================================================
# ✅ RSVP Permissions
# ============================================================

class RSVPWritePermission(BasePermission):
    """
    Users can create or update their own RSVPs.
    Admins and hosts can view/manage all RSVPs.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return (
            request.user.is_authenticated and
            (obj.user == request.user or obj.scrimmage.host == request.user or request.user.is_staff)
        )


# ============================================================
# ✅ Media Permissions
# ============================================================

class MediaUploadPermission(BasePermission):
    """
    - Authenticated users can upload if they are the host or an active participant.
    - Only uploader or host/admin can edit/delete.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        scrim = getattr(obj, "scrimmage", None)
        if not scrim:
            return False

        # Edit/delete rights
        if obj.uploader == user or scrim.host == user or user.is_staff:
            return True
        return False

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user.is_authenticated:
            return False

        scrimmage_id = view.kwargs.get("scrimmage_pk") or request.data.get("scrimmage")
        if not scrimmage_id:
            return False

        from .models import Scrimmage
        try:
            scrim = Scrimmage.objects.get(id=scrimmage_id)
        except Scrimmage.DoesNotExist:
            return False

        # Upload permission check
        is_host = scrim.host == user
        is_participant = scrim.rsvps.filter(
            user=user, status__in=["going", "checked_in", "completed"]
        ).exists()
        return is_host or is_participant or user.is_staff


# ============================================================
# ✅ Category & Type Permissions
# ============================================================

class CategoryTypePermission(BasePermission):
    """
    - Read: everyone can read approved categories/types.
    - Create: any authenticated user can propose new ones.
    - Update/Delete: only creator or admin.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return obj.approved or obj.created_by == request.user or request.user.is_staff
        return obj.created_by == request.user or request.user.is_staff


# ============================================================
# ✅ Template Permissions
# ============================================================

class TemplatePermission(BasePermission):
    """
    - Everyone can view approved & public templates.
    - Authenticated users can view their own.
    - Only creator or admin can modify or share.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            if obj.is_public or obj.is_shared or obj.creator == request.user:
                return True
            return request.user.is_staff
        return obj.creator == request.user or request.user.is_staff
