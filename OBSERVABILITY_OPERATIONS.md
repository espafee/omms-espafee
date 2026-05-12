# OMMS Observability and Operations

## Purpose

This layer gives OMMS a safe operational intelligence foundation without logging sensitive payloads.

## API Request Logging

- Middleware: `apps.observability.middleware.ApiRequestLoggingMiddleware`
- Model: `ApiRequestLog`
- Captures method, path, status, duration, user, company snapshot, category, IP, user agent, and optional query timing.
- Does not log passwords, OTPs, bearer tokens, request bodies, uploaded files, or auth headers.
- Slow threshold: `OMMS_SLOW_REQUEST_MS`
- Retention: `OMMS_REQUEST_LOG_RETENTION_DAYS`
- Cleanup:

```powershell
py manage.py cleanup_api_request_logs --days 30
```

## Audit Timeline

- Model: `AuditEvent`
- Service: `record_audit_event(...)`
- Current events include invoice activity, payment/credit events, POE uploads/reviews, site GPS lock, issue reporting, and issue escalation.
- API:
  - `GET /api/v1/observability/audit-events/`
  - supports event, entity, actor, severity, search, and date-range filters.

## Notification Center

- Model: `Notification`
- API:
  - `GET /api/v1/notifications/inbox/`
  - `GET /api/v1/notifications/inbox/unread-count/`
  - `POST /api/v1/notifications/inbox/<id>/mark-read/`
- Frontend page:
  - `/notifications`

## POE Analytics

- API:
  - `GET /api/v1/observability/poe-analytics/`
- Tracks suspicious POEs, outside geofence, missing GPS, duplicate/replacement POEs, pending review, overdue review, trends, and drill-down records.
- Frontend page:
  - `/operations`

## Diagnostics

- API:
  - `GET /api/v1/observability/diagnostics/`
- Admin-only.
- Reports database/cache health, slow request threshold, recent slow requests, recent 500s, and Celery-ready status.
- Does not expose secrets.

## Background Jobs

Celery is already configured. The current foundation includes task-ready functions for:

- notification retry
- invoice status refresh
- old request-log cleanup

Local worker:

```powershell
celery -A config worker -l info
```

Scheduled cleanup can run through Celery Beat later, or via management command today.

## Upload Retry and Idempotency

- POE records now accept `client_upload_id`.
- Repeated POE create requests with the same non-empty `client_upload_id` return the existing record.
- Frontend POE uploads generate a client upload key and retry evidence uploads safely.

## Import / Export Foundation

- Model: `ImportExportJob`
- Inventory site CSV export and review-first import validation are implemented.
- Import preview validates rows and stores errors without creating records.

## Dashboard Caching

- Campaign, booking, and billing dashboard summaries use tenant/user-scoped cache keys.
- Cache timeout: `OMMS_DASHBOARD_CACHE_SECONDS`
- Mutations bump a dashboard cache version so financial/POE/campaign changes invalidate aggregate snapshots.
