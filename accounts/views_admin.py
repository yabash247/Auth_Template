# accounts/views_admin.py
from axes.utils import reset
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from rest_framework import permissions, status, views
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

User = get_user_model()

@api_view(["POST"])
@permission_classes([IsAdminUser])
def unlock_user(request):
    email = request.data.get("email")
    if not email:
        return Response({"detail": "Email required"}, status=400)
    reset(username=email)
    return Response({"detail": f"Lockout reset for {email}"})



class AdminOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff or request.user.is_superuser

class AccountActionView(views.APIView):
    permission_classes = [AdminOnly]

    def post(self, request, user_id, action):
        user = get_object_or_404(User, id=user_id)

        if action == "lock":
            user.lock()
            return Response({"detail": f"User {user.email} locked"}, status=200)
        elif action == "unlock":
            user.unlock()
            return Response({"detail": f"User {user.email} unlocked"}, status=200)
        elif action == "soft_delete":
            user.soft_delete()
            return Response({"detail": f"User {user.email} soft deleted"}, status=200)
        elif action == "restore":
            user.restore()
            return Response({"detail": f"User {user.email} restored"}, status=200)
        elif action == "hard_delete":
            user_email = user.email
            user.hard_delete()
            return Response({"detail": f"User {user_email} permanently deleted"}, status=200)
        else:
            return Response({"detail": "Invalid action"}, status=400)
