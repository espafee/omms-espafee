from celery import shared_task
from django.utils import timezone

from .models import Invoice


@shared_task
def mark_overdue_invoices():
    today = timezone.localdate()
    overdue_queryset = Invoice.objects.filter(
        due_date__lt=today,
        status__in=[Invoice.Status.DRAFT, Invoice.Status.ISSUED, Invoice.Status.PARTIALLY_PAID],
    )
    updated_count = overdue_queryset.update(status=Invoice.Status.OVERDUE)
    return {"updated_invoices": updated_count, "run_date": str(today)}
