from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import Group, GroupMember
from .serializers import GroupSerializer, GroupMemberSerializer

class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().select_related("owner")
    serializer_class = GroupSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        group = serializer.save(owner=self.request.user)
        GroupMember.objects.create(user=self.request.user, group=group, role="organizer")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        group = self.get_object()
        GroupMember.objects.get_or_create(user=request.user, group=group)
        return Response({"detail": "Joined group."})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def leave(self, request, pk=None):
        group = self.get_object()
        GroupMember.objects.filter(user=request.user, group=group).delete()
        return Response({"detail": "Left group."})

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        group = self.get_object()
        members = GroupMember.objects.filter(group=group).select_related("user")
        return Response(GroupMemberSerializer(members, many=True).data)
