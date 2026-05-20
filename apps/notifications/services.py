from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError
from django.utils import timezone

from apps.bookings.models import Booking
from apps.campaigns.services import CampaignAccessTokenService
from apps.billing.models import Invoice, Payment
from apps.issues.models import Issue
from apps.poe.models import ProofOfExecution
from apps.poe.models import ProofOfExecutionMedia
from apps.tenants.services import get_user_tenant, is_platform_super_admin

from .models import EmailNotificationLog, Notification, NotificationPreference


def build_frontend_public_url(path: str) -> str:
    base = settings.FRONTEND_PUBLIC_BASE_URL.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def get_client_recipient(campaign) -> tuple[str, str]:
    client = campaign.client
    email = (getattr(client, "email", "") or "").strip()
    name = (
        getattr(client, "organization_name", "")
        or getattr(client, "first_name", "")
        or getattr(client, "username", "")
        or email
    ).strip()
    return email, name


def ensure_campaign_public_link(campaign, *, actor=None) -> str:
    token_service = CampaignAccessTokenService()
    access_token, _raw_token, _created = token_service.create_token(campaign=campaign, actor=actor)
    if not access_token.public_path:
        raise ValueError("Campaign share token did not produce a public path.")
    return build_frontend_public_url(access_token.public_path)


def format_booking_label(booking: Booking) -> str:
    site = booking.media_unit.site
    return (
        f"- {site.name} ({site.code}) / {booking.media_unit.unit_code}"
        f" | {site.city}, {site.state}"
        f" | {booking.start_date:%d-%m-%Y} to {booking.end_date:%d-%m-%Y}"
    )


def format_poe_location(media: ProofOfExecutionMedia) -> str:
    booking = media.poe_record.booking
    site = booking.media_unit.site
    return f"{site.name} ({site.code}) / {booking.media_unit.unit_code}"


@dataclass
class NotificationResult:
    log: EmailNotificationLog
    created: bool


class NotificationService:
    def _derive_tenant(self, *, tenant=None, recipient=None, campaign=None, booking=None, poe_record=None, issue=None):
        if tenant is not None:
            return tenant
        if recipient is not None and getattr(recipient, "is_authenticated", False):
            return get_user_tenant(recipient)
        if campaign is not None:
            return getattr(campaign, "tenant", None)
        if booking is not None:
            return getattr(getattr(booking, "campaign", None), "tenant", None)
        if poe_record is not None:
            return getattr(getattr(getattr(poe_record, "booking", None), "campaign", None), "tenant", None)
        if issue is not None:
            return getattr(getattr(getattr(issue, "booking", None), "campaign", None), "tenant", None)
        return None

    def _recipient_allows_in_app(self, user, notification_type: str) -> bool:
        if not user:
            return True
        preference = NotificationPreference.objects.filter(user=user, notification_type=notification_type).first()
        return True if preference is None else preference.in_app_enabled

    def create_internal_notification(
        self,
        *,
        recipient=None,
        recipient_role: str = "",
        event_type: str,
        title: str,
        message: str = "",
        severity: str = Notification.Severity.INFO,
        metadata: dict | None = None,
        tenant=None,
    ) -> Notification:
        try:
            from apps.observability.services import get_company_name, scrub_metadata
        except Exception:
            get_company_name = lambda: ""
            scrub_metadata = lambda value: value or {}
        if recipient and not self._recipient_allows_in_app(recipient, event_type):
            return Notification(
                recipient=recipient,
            recipient_role=recipient_role,
            tenant=self._derive_tenant(tenant=tenant, recipient=recipient),
            event_type=event_type,
                title=title[:255],
                message=message,
                severity=severity,
                delivery_status=Notification.DeliveryStatus.INTERNAL,
                metadata=scrub_metadata(metadata or {}),
            )

        return Notification.objects.create(
            recipient=recipient if getattr(recipient, "is_authenticated", False) else recipient,
            recipient_role=recipient_role,
            tenant=self._derive_tenant(tenant=tenant, recipient=recipient),
            company_name=get_company_name(),
            event_type=event_type,
            title=title[:255],
            message=message,
            severity=severity,
            metadata=scrub_metadata(metadata or {}),
        )

    def notify_operations(
        self,
        *,
        event_type: str,
        title: str,
        message: str = "",
        severity: str = Notification.Severity.INFO,
        metadata: dict | None = None,
        tenant=None,
    ) -> Notification:
        return self.create_internal_notification(
            recipient_role="operations",
            event_type=event_type,
            title=title,
            message=message,
            severity=severity,
            metadata=metadata,
            tenant=tenant,
        )

    def _recipient_allows_email(self, user, notification_type: str) -> bool:
        if not user:
            return True
        preference = NotificationPreference.objects.filter(user=user, notification_type=notification_type).first()
        return True if preference is None else preference.email_enabled

    def _get_or_create_log(self, *, event_key: str, notification_type: str, campaign, booking=None, poe_record=None, poe_media=None, issue=None, recipient_email: str, recipient_name: str, subject: str) -> NotificationResult:
        try:
            log, created = EmailNotificationLog.objects.get_or_create(
                event_key=event_key,
                defaults={
                    "notification_type": notification_type,
                    "campaign": campaign,
                    "tenant": self._derive_tenant(campaign=campaign, booking=booking, poe_record=poe_record, issue=issue),
                    "booking": booking,
                    "poe_record": poe_record,
                    "poe_media": poe_media,
                    "issue": issue,
                    "recipient_email": recipient_email,
                    "recipient_name": recipient_name,
                    "subject": subject,
                    "status": EmailNotificationLog.Status.PENDING,
                },
            )
        except IntegrityError:
            log = EmailNotificationLog.objects.get(event_key=event_key)
            created = False
        return NotificationResult(log=log, created=created)

    def _send_logged_email(self, *, log: EmailNotificationLog, created: bool, recipient_email: str, body: str) -> NotificationResult:
        if not created:
            return NotificationResult(log=log, created=False)
        if not recipient_email:
            log.status = EmailNotificationLog.Status.SKIPPED
            log.error_message = "No client email available for this campaign."
            log.save(update_fields=["status", "error_message", "updated_at"])
            return NotificationResult(log=log, created=True)

        try:
            send_mail(
                subject=log.subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
        except Exception as exc:
            log.status = EmailNotificationLog.Status.FAILED
            log.error_message = str(exc)
            log.last_attempt_at = timezone.now()
            log.retry_count += 1
            log.next_retry_at = log.last_attempt_at + timedelta(minutes=min(60, 5 * log.retry_count))
            log.save(update_fields=["status", "error_message", "last_attempt_at", "retry_count", "next_retry_at", "updated_at"])
            return NotificationResult(log=log, created=True)

        log.status = EmailNotificationLog.Status.SENT
        log.sent_at = timezone.now()
        log.last_attempt_at = log.sent_at
        log.next_retry_at = None
        log.error_message = ""
        log.save(update_fields=["status", "sent_at", "last_attempt_at", "next_retry_at", "error_message", "updated_at"])
        return NotificationResult(log=log, created=True)

    def send_campaign_booked_notification(self, booking: Booking, *, actor=None) -> NotificationResult:
        campaign = booking.campaign
        recipient_email, recipient_name = get_client_recipient(campaign)
        subject = "Your Outdoor Media Campaign Has Been Created"
        result = self._get_or_create_log(
            event_key=f"campaign_booked:{campaign.id}",
            notification_type=EmailNotificationLog.NotificationType.CAMPAIGN_BOOKED,
            campaign=campaign,
            booking=booking,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
        )
        if not result.created:
            return result
        if not self._recipient_allows_email(campaign.client, EmailNotificationLog.NotificationType.CAMPAIGN_BOOKED):
            result.log.status = EmailNotificationLog.Status.SKIPPED
            result.log.error_message = "Recipient email notifications disabled for this event."
            result.log.save(update_fields=["status", "error_message", "updated_at"])
            return result
        if not recipient_email:
            return self._send_logged_email(log=result.log, created=True, recipient_email=recipient_email, body="")
        try:
            public_link = ensure_campaign_public_link(campaign, actor=actor)
            bookings = campaign.bookings.select_related("media_unit__site").order_by("start_date", "media_unit__unit_code")
            booking_lines = "\n".join(format_booking_label(item) for item in bookings)
            campaign_range = f"{campaign.start_date:%d-%m-%Y} to {campaign.end_date:%d-%m-%Y}" if campaign.start_date and campaign.end_date else "Not specified"
            body = (
                f"Dear {recipient_name or 'Client'},\n\n"
                f"Your outdoor media campaign has been created successfully.\n\n"
                f"Client: {recipient_name or '-'}\n"
                f"Campaign: {campaign.name}\n"
                f"Campaign Dates: {campaign_range}\n"
                f"Booked Sites / Media Units:\n{booking_lines or '- No bookings listed -'}\n\n"
                f"Campaign Link: {public_link}\n\n"
                f"Regards,\n{settings.NOTIFICATION_COMPANY_NAME}"
            )
        except Exception as exc:
            result.log.status = EmailNotificationLog.Status.FAILED
            result.log.error_message = str(exc)
            result.log.save(update_fields=["status", "error_message", "updated_at"])
            return result
        return self._send_logged_email(log=result.log, created=True, recipient_email=recipient_email, body=body)

    def send_poe_uploaded_notification(self, media: ProofOfExecutionMedia, *, actor=None) -> NotificationResult:
        campaign = media.poe_record.booking.campaign
        recipient_email, recipient_name = get_client_recipient(campaign)
        subject = "Installation Proof Uploaded for Your Campaign"
        result = self._get_or_create_log(
            event_key=f"poe_uploaded:{media.id}",
            notification_type=EmailNotificationLog.NotificationType.POE_UPLOADED,
            campaign=campaign,
            booking=media.poe_record.booking,
            poe_record=media.poe_record,
            poe_media=media,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
        )
        if not result.created:
            return result
        if not self._recipient_allows_email(campaign.client, EmailNotificationLog.NotificationType.POE_UPLOADED):
            result.log.status = EmailNotificationLog.Status.SKIPPED
            result.log.error_message = "Recipient email notifications disabled for this event."
            result.log.save(update_fields=["status", "error_message", "updated_at"])
            return result
        if not recipient_email:
            return self._send_logged_email(log=result.log, created=True, recipient_email=recipient_email, body="")
        try:
            public_link = ensure_campaign_public_link(campaign, actor=actor)
            captured_at = media.captured_at or media.created_at
            body = (
                f"Dear {recipient_name or 'Client'},\n\n"
                f"Installation proof has been uploaded for your campaign.\n\n"
                f"Campaign: {campaign.name}\n"
                f"Installed Site / Media Unit: {format_poe_location(media)}\n"
                f"Upload Timestamp: {captured_at:%d-%m-%Y %H:%M:%S}\n"
                f"Campaign Link: {public_link}\n\n"
                f"You can review the latest proof and campaign status at the link above.\n\n"
                f"Regards,\n{settings.NOTIFICATION_COMPANY_NAME}"
            )
        except Exception as exc:
            result.log.status = EmailNotificationLog.Status.FAILED
            result.log.error_message = str(exc)
            result.log.save(update_fields=["status", "error_message", "updated_at"])
            return result
        return self._send_logged_email(log=result.log, created=True, recipient_email=recipient_email, body=body)

    def log_invoice_issued(self, invoice: Invoice, *, actor=None) -> NotificationResult:
        campaign = invoice.campaign
        recipient_email, recipient_name = get_client_recipient(campaign)
        self.notify_operations(
            event_type=EmailNotificationLog.NotificationType.INVOICE_ISSUED,
            title=f"Invoice issued: {invoice.invoice_number or invoice.pk}",
            message=f"Invoice for {campaign.name} was issued.",
            metadata={"invoice_id": invoice.id, "campaign_id": campaign.id},
            tenant=campaign.tenant,
        )
        return self._get_or_create_log(
            event_key=f"invoice_issued:{invoice.id}",
            notification_type=EmailNotificationLog.NotificationType.INVOICE_ISSUED,
            campaign=campaign,
            booking=None,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=f"Invoice issued: {invoice.invoice_number or invoice.pk}",
        )

    def log_payment_recorded(self, payment: Payment, *, actor=None) -> NotificationResult:
        invoice = payment.invoice
        campaign = invoice.campaign
        recipient_email, recipient_name = get_client_recipient(campaign)
        self.notify_operations(
            event_type=EmailNotificationLog.NotificationType.PAYMENT_RECORDED,
            title=f"Payment recorded: {invoice.invoice_number or invoice.pk}",
            message=f"Payment of {payment.amount} was recorded.",
            metadata={"invoice_id": invoice.id, "payment_id": payment.id},
            tenant=campaign.tenant,
        )
        return self._get_or_create_log(
            event_key=f"payment_recorded:{payment.id}",
            notification_type=EmailNotificationLog.NotificationType.PAYMENT_RECORDED,
            campaign=campaign,
            booking=None,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=f"Payment recorded: {invoice.invoice_number or invoice.pk}",
        )

    def log_suspicious_poe(self, poe_record: ProofOfExecution, *, actor=None) -> NotificationResult:
        campaign = poe_record.booking.campaign
        recipient_email, recipient_name = get_client_recipient(campaign)
        self.notify_operations(
            event_type=EmailNotificationLog.NotificationType.SUSPICIOUS_POE,
            title=f"Suspicious POE detected: {campaign.name}",
            message=poe_record.verification_notes,
            severity=Notification.Severity.WARNING,
            metadata={"poe_record_id": poe_record.id, "campaign_id": campaign.id},
            tenant=campaign.tenant,
        )
        return self._get_or_create_log(
            event_key=f"suspicious_poe:{poe_record.id}:{poe_record.verification_status}",
            notification_type=EmailNotificationLog.NotificationType.SUSPICIOUS_POE,
            campaign=campaign,
            booking=poe_record.booking,
            poe_record=poe_record,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=f"Suspicious POE detected: {campaign.name}",
        )

    def log_issue_reported(self, issue: Issue, *, actor=None) -> NotificationResult:
        campaign = issue.booking.campaign
        recipient_email, recipient_name = get_client_recipient(campaign)
        self.notify_operations(
            event_type=EmailNotificationLog.NotificationType.ISSUE_REPORTED,
            title=f"Issue reported: {campaign.name}",
            message=issue.description[:500],
            severity=Notification.Severity.WARNING if issue.priority in {"high", "critical"} else Notification.Severity.INFO,
            metadata={"issue_id": issue.id, "priority": issue.priority},
            tenant=campaign.tenant,
        )
        return self._get_or_create_log(
            event_key=f"issue_reported:{issue.id}",
            notification_type=EmailNotificationLog.NotificationType.ISSUE_REPORTED,
            campaign=campaign,
            booking=issue.booking,
            issue=issue,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=f"Issue reported: {campaign.name}",
        )

    def log_issue_escalated(self, issue: Issue, *, actor=None) -> NotificationResult:
        campaign = issue.booking.campaign
        recipient_email, recipient_name = get_client_recipient(campaign)
        event_time = issue.escalated_at.isoformat() if getattr(issue, "escalated_at", None) else timezone.now().isoformat()
        self.notify_operations(
            event_type=EmailNotificationLog.NotificationType.ISSUE_ESCALATED,
            title=f"Issue escalated: {campaign.name}",
            message=issue.escalation_reason,
            severity=Notification.Severity.CRITICAL if issue.priority == "critical" else Notification.Severity.WARNING,
            metadata={"issue_id": issue.id, "priority": issue.priority, "sla_status": issue.sla_status},
            tenant=campaign.tenant,
        )
        return self._get_or_create_log(
            event_key=f"issue_escalated:{issue.id}:{event_time}",
            notification_type=EmailNotificationLog.NotificationType.ISSUE_ESCALATED,
            campaign=campaign,
            booking=issue.booking,
            issue=issue,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=f"Issue escalated: {campaign.name}",
        )

    def due_retry_queryset(self):
        return EmailNotificationLog.objects.filter(
            status=EmailNotificationLog.Status.FAILED,
            next_retry_at__lte=timezone.now(),
        ).order_by("next_retry_at", "created_at")

    def mark_due_retries_pending(self, *, limit: int = 50) -> int:
        logs = list(self.due_retry_queryset()[:limit])
        if not logs:
            return 0
        EmailNotificationLog.objects.filter(id__in=[log.id for log in logs]).update(
            status=EmailNotificationLog.Status.PENDING,
            next_retry_at=None,
            updated_at=timezone.now(),
        )
        return len(logs)


def trigger_campaign_booked_notification(booking: Booking, *, actor=None) -> None:
    try:
        NotificationService().send_campaign_booked_notification(booking, actor=actor)
    except Exception:
        # Notification failures must never block booking creation.
        pass


def trigger_poe_uploaded_notification(media: ProofOfExecutionMedia, *, actor=None) -> None:
    try:
        NotificationService().send_poe_uploaded_notification(media, actor=actor)
    except Exception:
        # Notification failures must never block POE media creation.
        pass


def trigger_invoice_issued_notification(invoice: Invoice, *, actor=None) -> None:
    try:
        NotificationService().log_invoice_issued(invoice, actor=actor)
    except Exception:
        pass


def trigger_payment_recorded_notification(payment: Payment, *, actor=None) -> None:
    try:
        NotificationService().log_payment_recorded(payment, actor=actor)
    except Exception:
        pass


def trigger_suspicious_poe_notification(poe_record: ProofOfExecution, *, actor=None) -> None:
    try:
        NotificationService().log_suspicious_poe(poe_record, actor=actor)
    except Exception:
        pass


def trigger_issue_reported_notification(issue: Issue, *, actor=None) -> None:
    try:
        NotificationService().log_issue_reported(issue, actor=actor)
    except Exception:
        pass


def trigger_issue_escalated_notification(issue: Issue, *, actor=None) -> None:
    try:
        NotificationService().log_issue_escalated(issue, actor=actor)
    except Exception:
        pass
