# OMMS Celery Background Jobs

## Production Services

Run OMMS background work as separate Render services:

- Web: Django/Gunicorn web service
- Worker: `celery -A config worker --loglevel=info`
- Beat: `celery -A config beat --loglevel=info`
- Redis: managed Redis instance used by `CELERY_BROKER_URL`

Do not run long background work inside web requests.

## Required Environment Variables

```text
CELERY_BROKER_URL=redis://...
CELERY_RESULT_BACKEND=redis://...
CELERY_TASK_ALWAYS_EAGER=False
OMMS_ENABLE_BACKGROUND_JOBS=True
OMMS_REQUEST_LOG_RETENTION_DAYS=30
CELERY_OVERDUE_CHECK_HOUR=1
CELERY_REQUEST_LOG_CLEANUP_HOUR=2
```

## Scheduled Tasks

- Nightly invoice/payment status refresh
- Nightly API request log cleanup
- Failed notification retry queue every 15 minutes
- Hourly invoice status refresh
- Operational alert threshold evaluation every 10 minutes

## Local Development

Normal Django startup does not require Redis. Only run Celery locally when testing background jobs:

```powershell
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
celery -A config inspect ping
```

If Redis is not available locally, skip Celery runtime validation and use the management commands/services directly.
