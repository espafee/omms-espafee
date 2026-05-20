# OMMS Deployment Checklist

Generated: 2026-05-20
Last smoke update: 2026-05-20

Legend: `[x]` verified, `[ ]` pending, `[!]` attention/blocker.

## Pre-Deployment

- [x] Confirm launch branch is `main` and clean.
- [ ] Confirm latest backend commit is deployed. Public backend is reachable, but authenticated diagnostics/commit metadata were not available without admin credentials.
- [x] Confirm latest frontend commit is deployed to Vercel for `https://omms.vercel.app`.
- [ ] Confirm mobile release build uses the latest pushed mobile commit. Source is pushed; release build/APK was not generated in this smoke pass.
- [!] Rotate all demo/admin credentials. Requires production admin access and is still pending.
- [ ] Confirm production `DJANGO_SECRET_KEY` is strong and not the default placeholder. Public checks cannot expose this; confirm in Render/env dashboard.
- [ ] Confirm `DJANGO_DEBUG=false`. Public behavior suggests production mode, but confirm in Render/env dashboard.
- [ ] Confirm `DJANGO_ALLOWED_HOSTS` includes the backend domain. Public backend responds on `https://omms-backend.onrender.com`; confirm exact env value in Render.
- [!] Confirm `DJANGO_CORS_ALLOWED_ORIGINS` includes only trusted frontend/mobile origins. `https://omms.vercel.app` is allowed; `https://www.vistaaitech.com` is not currently allowed.
- [ ] Confirm `DJANGO_CSRF_TRUSTED_ORIGINS` includes trusted backend/admin origins. Requires Render/env dashboard access.
- [!] Confirm `NEXT_PUBLIC_API_ROOT` points to the production backend `/api/v1`. `https://omms.vercel.app` is correctly wired to `https://omms-backend.onrender.com/api/v1`; `https://www.vistaaitech.com/omms/login` appears wired to `https://omms.vercel.app`, which is not the backend API.
- [ ] Confirm `FRONTEND_PUBLIC_BASE_URL` points to the production frontend. Requires backend env/diagnostics access.
- [ ] Confirm `OMMS_BACKEND_PUBLIC_BASE_URL` points to the production backend. Requires backend env/diagnostics access.
- [ ] Confirm `OMMS_ENVIRONMENT_NAME`, `OMMS_APP_VERSION`, and `OMMS_GIT_COMMIT` are populated. Requires authenticated diagnostics or Render env access.

## Backend Release

- [x] Run `python manage.py check`.
- [x] Run `python manage.py migrate --plan`.
- [x] Apply migrations locally with `python manage.py migrate` where needed.
- [x] Confirm local `python manage.py migrate --check` exits successfully.
- [ ] Run production `python manage.py collectstatic --noinput` during backend deploy.
- [x] Confirm public `/health/` returns healthy at `https://omms-backend.onrender.com/health/`.
- [ ] Confirm admin diagnostics endpoint works for admin users. Endpoint is protected and returns `401` without credentials as expected.
- [ ] Confirm `observability.0012_operationalmode` is applied in production. Local migration is applied; production requires Render/database verification.

## Storage

- [ ] Configure durable media storage for site images, media unit images, and POE evidence. Requires production env/storage verification.
- [ ] Configure private document storage for invoices, contracts, receipts, reports, and training-sensitive files. Requires production env/storage verification.
- [ ] Confirm signed private URLs do not expose storage secrets. Backend tests cover this locally; production storage still needs smoke validation.
- [ ] Confirm upload size limits and object-storage permissions.

## Background Jobs

- [ ] Configure `CELERY_BROKER_URL`. Local Celery report is valid; production Redis URL requires Render/env verification.
- [ ] Configure `CELERY_RESULT_BACKEND`. Local Celery report is valid; production backend requires Render/env verification.
- [x] Start web process. Public backend web process is responding.
- [ ] Start Celery worker: `celery -A config worker --loglevel=info`. Requires Render worker verification.
- [ ] Start Celery beat: `celery -A config beat --loglevel=info`. Requires Render beat verification.
- [ ] Confirm Operations System Status shows Redis configured and worker readiness acceptable. Requires admin login.
- [ ] Run a small export job and confirm completion/download. Requires admin login.
- [ ] Run a small import preview and confirm no records are created before confirmation. Requires admin login.

## Frontend Release

- [x] Run `npm run lint`.
- [x] Run `npm run build`.
- [x] Run `npx playwright test`.
- [x] Deploy production frontend. `https://omms.vercel.app` is Ready on Vercel.
- [x] Confirm public app routes load on `https://omms.vercel.app`.
- [ ] Confirm Operations page does not show global error banners after login. Requires admin login.

## Mobile Release

- [x] Run `npm install`.
- [x] Run `npm run lint`.
- [x] Run `npx tsc --noEmit`.
- [x] Run `npx expo-doctor`.
- [ ] Generate internal Android build/APK when release candidate is selected.
- [ ] Test login, assigned work, POE upload, issue report, admin summary, and maintenance/read-only blocking against production. Requires production account credentials.
- [!] Review Expo/Metro dependency audit findings before public release. Current audit has 6 moderate findings requiring planned Expo SDK upgrade.

## Security And Role Matrix

- [ ] Admin can access Operations, diagnostics, maintenance mode, training, imports/exports, and dashboard customization. Requires production admin credentials.
- [ ] Operations can access POE, inventory operations, jobs, alerts, and non-finance operational analytics. Requires production operations credentials.
- [ ] Finance can access billing, invoices, payments, collection risk, and finance training. Requires production finance credentials.
- [ ] Field staff can access assigned work and POE upload only. Requires production field credentials.
- [ ] Client/user can access only allowed campaign, invoice/statement, and training visibility. Requires production client credentials.
- [x] Hidden dashboard widgets do not trigger unauthorized data fetches in local Playwright/backend validation.
- [x] Operational search permission behavior is covered locally; production role smoke still requires credentials.

## Post-Deployment Smoke

- [ ] Login succeeds with admin account. Requires production admin credentials.
- [ ] Operations summary loads. Requires production admin credentials.
- [ ] Dashboard customization save/restore works. Requires production admin credentials.
- [ ] Training guide download works. Endpoint is protected and returns `401` without credentials as expected; authenticated download requires production credentials.
- [ ] Notification preferences save/read. Requires production credentials.
- [ ] Maintenance mode can be read and updated by admin. Endpoint is protected and returns `401` without credentials as expected; safe update requires production admin credentials.
- [ ] Non-admin write is blocked in read-only mode. Requires production non-admin/admin credentials.
- [ ] Import Excel template downloads. Endpoint is protected and returns `401` without credentials as expected; authenticated download requires production credentials.
- [ ] Export job completes and file downloads. Requires production admin credentials and Celery worker verification.
- [ ] Mobile field POE upload works against production API. Requires production field credentials and release/test build configuration.

## Rollback Plan

- [ ] Keep previous backend deployment available.
- [ ] Keep previous frontend Vercel deployment available for promotion rollback.
- [ ] Snapshot database before migrations.
- [ ] Do not roll back database schema blindly after writes; use forward-fix unless rollback has been rehearsed.
- [ ] Pause Celery beat before emergency rollback if scheduled jobs are causing issues.
