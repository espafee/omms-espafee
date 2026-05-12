from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, FINANCE, OPERATIONS
from core.viewsets import ServiceModelViewSet
from core.services import BaseService
from core.repositories import BaseRepository

from .models import EmailNotificationLog, NotificationPreference
from .serializers import EmailNotificationLogSerializer, NotificationPreferenceSerializer


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


class EmailNotificationLogService(BaseService):
    repository_class = EmailNotificationLogRepository


class NotificationPreferenceService(BaseService):
    repository_class = NotificationPreferenceRepository

    def create(self, actor=None, **validated_data):
        if actor and getattr(actor, "role", None) not in {ADMIN, FINANCE, OPERATIONS} and not getattr(actor, "is_superuser", False):
            validated_data["user"] = actor
        return super().create(actor=actor, **validated_data)


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
