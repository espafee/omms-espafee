# OMMS Deployment Checklist

Generated: 2026-05-20

## Pre-Deployment

- [ ] Confirm launch branch is `main` and clean.
- [ ] Confirm latest backend commit is deployed.
- [ ] Confirm latest frontend commit is deployed to Vercel.
- [ ] Confirm mobile release build uses the latest pushed mobile commit.
- [ ] Rotate all demo/admin credentials.
- [ ] Confirm production `DJANGO_SECRET_KEY` is strong and not the default placeholder.
- [ ] Confirm `DJANGO_DEBUG=false`.
- [ ] Confirm `DJANGO_ALLOWED_HOSTS` includes the backend domain.
- [ ] Confirm `DJANGO_CORS_ALLOWED_ORIGINS` includes only trusted frontend/mobile origins.
- [ ] Confirm `DJANGO_CSRF_TRUSTED_ORIGINS` includes trusted backend/admin origins.
- [ ] Confirm `NEXT_PUBLIC_API_ROOT` points to the production backend `/api/v1`.
- [ ] Confirm `FRONTEND_PUBLIC_BASE_URL` points to the production frontend.
- [ ] Confirm `OMMS_BACKEND_PUBLIC_BASE_URL` points to the production backend.
- [ ] Confirm `OMMS_ENVIRONMENT_NAME`, `OMMS_APP_VERSION`, and `OMMS_GIT_COMMIT` are populated.

## Backend Release

- [ ] Run `python manage.py check`.
- [ ] Run `python manage.py migrate --plan`.
- [ ] Apply migrations with `python manage.py migrate`.
- [ ] Confirm `python manage.py migrate --check` exits successfully.
- [ ] Run `python manage.py collectstatic --noinput`.
- [ ] Confirm `/health/` returns healthy.
- [ ] Confirm admin diagnostics endpoint works for admin users.
- [ ] Confirm `observability.0012_operationalmode` is applied.

## Storage

- [ ] Configure durable media storage for site images, media unit images, and POE evidence.
- [ ] Configure private document storage for invoices, contracts, receipts, reports, and training-sensitive files.
- [ ] Confirm signed private URLs do not expose storage secrets.
- [ ] Confirm upload size limits and object-storage permissions.

## Background Jobs

- [ ] Configure `CELERY_BROKER_URL`.
- [ ] Configure `CELERY_RESULT_BACKEND`.
- [ ] Start web process.
- [ ] Start Celery worker: `celery -A config worker --loglevel=info`.
- [ ] Start Celery beat: `celery -A config beat --loglevel=info`.
- [ ] Confirm Operations System Status shows Redis configured and worker readiness acceptable.
- [ ] Run a small export job and confirm completion/download.
- [ ] Run a small import preview and confirm no records are created before confirmation.

## Frontend Release

- [ ] Run `npm run lint`.
- [ ] Run `npm run build`.
- [ ] Run `npx playwright test`.
- [ ] Deploy production frontend.
- [ ] Confirm `/login`, `/dashboard`, `/operations`, `/training`, `/poe`, `/billing`, `/campaigns`, and `/inventory` load.
- [ ] Confirm Operations page does not show global error banners after login.

## Mobile Release

- [ ] Run `npm install`.
- [ ] Run `npm run lint`.
- [ ] Run `npx tsc --noEmit`.
- [ ] Run `npx expo-doctor`.
- [ ] Generate internal Android build/APK when release candidate is selected.
- [ ] Test login, assigned work, POE upload, issue report, admin summary, and maintenance/read-only blocking.
- [ ] Review Expo/Metro dependency audit findings before public release.

## Security And Role Matrix

- [ ] Admin can access Operations, diagnostics, maintenance mode, training, imports/exports, and dashboard customization.
- [ ] Operations can access POE, inventory operations, jobs, alerts, and non-finance operational analytics.
- [ ] Finance can access billing, invoices, payments, collection risk, and finance training.
- [ ] Field staff can access assigned work and POE upload only.
- [ ] Client/user can access only allowed campaign, invoice/statement, and training visibility.
- [ ] Hidden dashboard widgets do not trigger unauthorized data fetches.
- [ ] Operational search does not return finance data to unauthorized roles.

## Post-Deployment Smoke

- [ ] Login succeeds with admin account.
- [ ] Operations summary loads.
- [ ] Dashboard customization save/restore works.
- [ ] Training guide download works.
- [ ] Notification preferences save/read.
- [ ] Maintenance mode can be read and updated by admin.
- [ ] Non-admin write is blocked in read-only mode.
- [ ] Import Excel template downloads.
- [ ] Export job completes and file downloads.
- [ ] Mobile field POE upload works against production API.

## Rollback Plan

- [ ] Keep previous backend deployment available.
- [ ] Keep previous frontend Vercel deployment available for promotion rollback.
- [ ] Snapshot database before migrations.
- [ ] Do not roll back database schema blindly after writes; use forward-fix unless rollback has been rehearsed.
- [ ] Pause Celery beat before emergency rollback if scheduled jobs are causing issues.
