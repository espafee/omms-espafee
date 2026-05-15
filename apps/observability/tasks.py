from celery import shared_task

from .models import ImportExportJob
from .services import cleanup_old_request_logs, evaluate_alert_thresholds, notification_retry_job, process_export_job, process_inventory_sites_import, refresh_invoice_status_job


@shared_task
def cleanup_old_api_request_logs(days=None):
    return {"deleted": cleanup_old_request_logs(days=days)}


@shared_task
def retry_failed_notifications(limit=50):
    return {"queued": notification_retry_job(limit=limit)}


@shared_task
def refresh_invoice_statuses():
    return {"updated": refresh_invoice_status_job()}


@shared_task
def evaluate_operational_alert_thresholds():
    events = evaluate_alert_thresholds()
    return {"created_alerts": len(events), "alert_ids": [event.id for event in events]}


@shared_task
def process_inventory_import_job(job_id, actor_id=None):
    from django.contrib.auth import get_user_model

    actor = None
    if actor_id:
        actor = get_user_model().objects.filter(id=actor_id).first()
    job = ImportExportJob.objects.get(id=job_id)
    updated = process_inventory_sites_import(job, actor=actor)
    return {
        "job_id": updated.id,
        "status": updated.status,
        "rows_success": updated.rows_success,
        "rows_updated": updated.rows_updated,
        "rows_skipped": updated.rows_skipped,
        "rows_failed": updated.rows_failed,
    }


@shared_task
def process_export_job_task(job_id, actor_id=None):
    from django.contrib.auth import get_user_model

    actor = None
    if actor_id:
        actor = get_user_model().objects.filter(id=actor_id).first()
    job = ImportExportJob.objects.get(id=job_id)
    updated = process_export_job(job, actor=actor)
    return {
        "job_id": updated.id,
        "status": updated.status,
        "resource_type": updated.resource_type,
        "rows_success": updated.rows_success,
        "rows_failed": updated.rows_failed,
    }
