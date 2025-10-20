# scrimmages/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, "creator", None) or getattr(obj, "organizer", None)
        return owner == request.user or request.user.is_staff
