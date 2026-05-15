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

NOTIFICATION_EVENT_METADATA = {
    EmailNotificationLog.NotificationType.INVENTORY_IMPORT_COMPLETED: ("Imports", "Inventory import completed successfully."),
    EmailNotificationLog.NotificationType.INVENTORY_IMPORT_FAILED: ("Imports", "Inventory import failed or needs intervention."),
    EmailNotificationLog.NotificationType.EXPORT_COMPLETED: ("Exports", "Operational export completed and is ready to download."),
    EmailNotificationLog.NotificationType.EXPORT_FAILED: ("Exports", "Operational export failed or needs intervention."),
    EmailNotificationLog.NotificationType.SUSPICIOUS_POE: ("POE review", "POE was flagged as suspicious."),
    EmailNotificationLog.NotificationType.POE_REJECTED: ("POE review", "POE was rejected during review."),
    EmailNotificationLog.NotificationType.POE_APPROVED: ("POE review", "POE was approved during review."),
    EmailNotificationLog.NotificationType.INVOICE_ISSUED: ("Billing", "Invoice was issued."),
    EmailNotificationLog.NotificationType.PAYMENT_RECORDED: ("Billing", "Payment was recorded."),
    EmailNotificationLog.NotificationType.ALERT_TRIGGERED: ("System", "Operational alert threshold was triggered."),
    EmailNotificationLog.NotificationType.SYSTEM_DIAGNOSTIC_ALERT: ("System", "System diagnostic health alert was raised."),
    EmailNotificationLog.NotificationType.CAMPAIGN_BOOKED: ("Campaigns", "Campaign booking or campaign activity alert."),
    EmailNotificationLog.NotificationType.POE_UPLOADED: ("POE review", "New proof media was uploaded."),
    EmailNotificationLog.NotificationType.ISSUE_REPORTED: ("System", "Field issue was reported."),
    EmailNotificationLog.NotificationType.ISSUE_ESCALATED: ("System", "Field issue was escalated."),
}


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
        muted_event_types = NotificationPreference.objects.filter(
            user=user,
            in_app_enabled=False,
        ).values_list("notification_type", flat=True)
        if getattr(user, "is_superuser", False) or getattr(user, "role", None) in {ADMIN, FINANCE, OPERATIONS}:
            queryset = queryset.filter(Q(recipient=user) | Q(recipient__isnull=True, recipient_role__in=["", getattr(user, "role", "")]))
        else:
            queryset = queryset.filter(recipient=user)
        return queryset.exclude(event_type__in=muted_event_types)


class EmailNotificationLogService(BaseService):
    repository_class = EmailNotificationLogRepository


class NotificationPreferenceService(BaseService):
    repository_class = NotificationPreferenceRepository

    def create(self, actor=None, **validated_data):
        if actor and getattr(actor, "role", None) not in {ADMIN, FINANCE, OPERATIONS} and not getattr(actor, "is_superuser", False):
            validated_data["user"] = actor
        preference, _created = NotificationPreference.objects.update_or_create(
            user=validated_data["user"],
            notification_type=validated_data["notification_type"],
            defaults={
                "in_app_enabled": validated_data.get("in_app_enabled", True),
                "email_enabled": validated_data.get("email_enabled", True),
            },
        )
        return preference


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
    filterset_fields = ["user", "notification_type", "in_app_enabled", "email_enabled"]
    ordering_fields = ["notification_type", "updated_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if "user" not in self.request.query_params:
            queryset = queryset.filter(user=self.request.user)
        return queryset

    @action(detail=False, methods=["get"], url_path="event-types")
    def event_types(self, request):
        return Response(
            {
                "event_types": [
                    {
                        "value": value,
                        "label": label,
                        "category": NOTIFICATION_EVENT_METADATA.get(value, ("Other", ""))[0],
                        "description": NOTIFICATION_EVENT_METADATA.get(value, ("Other", ""))[1],
                    }
                    for value, label in EmailNotificationLog.NotificationType.choices
                ]
            }
        )


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
