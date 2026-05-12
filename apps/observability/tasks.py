from celery import shared_task

from .services import cleanup_old_request_logs, evaluate_alert_thresholds, notification_retry_job, refresh_invoice_status_job


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
