from celery import shared_task
from django.utils import timezone

from .models import Invoice
from .services import refresh_invoice_payment_statuses


@shared_task
def mark_overdue_invoices():
    today = timezone.localdate()
    update_queryset = Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
    updated_count = refresh_invoice_payment_statuses(queryset=update_queryset)
    return {"updated_invoices": updated_count, "run_date": str(today)}
