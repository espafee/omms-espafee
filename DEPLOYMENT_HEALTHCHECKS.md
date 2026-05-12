# OMMS Deployment Health Checks

## Public Health

Render health check path:

```text
/health/
```

Response does not expose secrets and only confirms the app is alive.

## Admin Diagnostics

Authenticated admin endpoint:

```text
/api/v1/observability/diagnostics/
```

Diagnostics include:

- database connectivity
- cache connectivity
- Celery broker configured flag
- background job enable flag
- request logging settings
- recent slow requests
- recent 500 responses
- recent critical alerts
- notification retry health

Diagnostics intentionally do not expose secrets, credentials, tokens, passwords, or raw environment values.

## Render Checklist

- Web service health path: `/health/`
- Worker command: `celery -A config worker --loglevel=info`
- Beat command: `celery -A config beat --loglevel=info`
- Redis configured via `CELERY_BROKER_URL`
- `DJANGO_ALLOWED_HOSTS`, CORS, CSRF trusted origins, and secure cookie settings configured for production domains
- `OMMS_GIT_COMMIT` can be set during deploy to identify the running version
