from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, FINANCE, OPERATIONS
from core.viewsets import ServiceModelViewSet
from core.services import BaseService
from core.repositories import BaseRepository

from .models import EmailNotificationLog, Notification, NotificationPreference
from .serializers import EmailNotificationLogSerializer, NotificationPreferenceSerializer, NotificationSerializer


class EmailNotificationLogRepository(BaseRepository):
    model = EmailNotificationLog
    select_related = ("campaign", "booking", "poe_record", "poe_media", "issue")


class NotificationPreferenceRepository(BaseRepository):
    model = NotificationPreference
    select_related = ("user",)

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) not in {ADMIN, FINANCE, OPERATIONS} and not getattr(user, "is_superuser", False):
            queryset = queryset.filter(user=user)
        return queryset


class NotificationRepository(BaseRepository):
    model = Notification
    select_related = ("recipient",)

    def scope_queryset(self, queryset, user=None):
        if not user:
            return queryset.none()
        if getattr(user, "is_superuser", False) or getattr(user, "role", None) in {ADMIN, FINANCE, OPERATIONS}:
            return queryset.filter(Q(recipient=user) | Q(recipient__isnull=True, recipient_role__in=["", getattr(user, "role", "")]))
        return queryset.filter(recipient=user)


class EmailNotificationLogService(BaseService):
    repository_class = EmailNotificationLogRepository


class NotificationPreferenceService(BaseService):
    repository_class = NotificationPreferenceRepository

    def create(self, actor=None, **validated_data):
        if actor and getattr(actor, "role", None) not in {ADMIN, FINANCE, OPERATIONS} and not getattr(actor, "is_superuser", False):
            validated_data["user"] = actor
        return super().create(actor=actor, **validated_data)


class NotificationInboxService(BaseService):
    repository_class = NotificationRepository

    def mark_read(self, instance, *, actor=None):
        instance.is_read = True
        instance.read_at = timezone.now()
        instance.save(update_fields=["is_read", "read_at", "updated_at"])
        return instance


class EmailNotificationLogViewSet(ServiceModelViewSet):
    serializer_class = EmailNotificationLogSerializer
    permission_classes = [RoleBasedPermission]
    service_class = EmailNotificationLogService
    allowed_roles = (ADMIN, FINANCE, OPERATIONS)
    write_roles = (ADMIN, FINANCE)
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["notification_type", "status", "campaign", "booking", "poe_record", "issue"]
    search_fields = ["event_key", "recipient_email", "subject", "error_message"]
    ordering_fields = ["created_at", "sent_at", "next_retry_at", "retry_count"]


class NotificationPreferenceViewSet(ServiceModelViewSet):
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [RoleBasedPermission]
    service_class = NotificationPreferenceService
    allowed_roles = ALL_ROLES
    write_roles = ALL_ROLES
    filterset_fields = ["user", "notification_type", "email_enabled"]
    ordering_fields = ["notification_type", "updated_at"]


class NotificationViewSet(ServiceModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [RoleBasedPermission]
    service_class = NotificationInboxService
    allowed_roles = ALL_ROLES
    write_roles = ALL_ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["event_type", "severity", "is_read", "delivery_status"]
    search_fields = ["title", "message"]
    ordering_fields = ["created_at", "severity"]

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Notifications are created by system events."}, status=405)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread_count": self.get_queryset().filter(is_read=False).count()})

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        updated = self.get_service().mark_read(self.get_object(), actor=request.user)
        return Response(self.get_serializer(updated).data)
