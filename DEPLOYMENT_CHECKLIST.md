# OMMS Deployment Checklist

Generated: 2026-05-20
Last smoke update: 2026-05-21

Legend: `[x]` verified, `[ ]` pending, `[!]` attention/blocker.

## Controlled Beta Surface Decision

- [x] Verify `https://omms.vercel.app` API routing. The app bundle points to `https://omms-backend.onrender.com/api/v1`.
- [x] Fix or avoid `https://www.vistaaitech.com/omms/login` for beta launch. The VistaAi path is now a redirect/launch page to `https://omms.vercel.app/login`.
- [x] If VistaAi remains the marketing URL, avoid API calls from `www.vistaaitech.com` for beta by redirecting into the canonical OMMS app.
- [x] Communicate `https://omms.vercel.app` as the current controlled beta application entrypoint.

## Pre-Deployment

- [x] Confirm launch branch is `main` and clean.
- [!] Confirm latest backend commit is deployed. Public schema contains recent routes from current code, but exact deployed Git SHA still requires Render dashboard or authenticated diagnostics.
- [x] Confirm latest frontend commit is deployed to Vercel for `https://omms.vercel.app`.
- [ ] Confirm mobile release build uses the latest pushed mobile commit. Source is pushed; release build/APK was not generated in this smoke pass.
- [!] Rotate all demo/admin credentials. Requires production admin access and is still pending.
- [ ] Confirm production `DJANGO_SECRET_KEY` is strong and not the default placeholder. Requires Render/env dashboard.
- [ ] Confirm `DJANGO_DEBUG=false`. Public behavior suggests production mode, but exact value requires Render/env dashboard.
- [x] Confirm `DJANGO_ALLOWED_HOSTS` includes the backend domain. Public backend responds on `https://omms-backend.onrender.com`.
- [x] Confirm `DJANGO_CORS_ALLOWED_ORIGINS` includes the required trusted beta frontend origin. `https://omms.vercel.app` is allowed; `https://www.vistaaitech.com` is not required for OMMS API traffic after the redirect fix.
- [ ] Confirm `DJANGO_CSRF_TRUSTED_ORIGINS` includes trusted backend/admin origins. Requires Render/env dashboard access.
- [x] Confirm `NEXT_PUBLIC_API_ROOT` points to the production backend `/api/v1`. `https://omms.vercel.app` is correctly wired to `https://omms-backend.onrender.com/api/v1`; the VistaAi `/omms/login` path redirects to the canonical app instead of making API calls.
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
- [x] Confirm public OpenAPI schema loads at `https://omms-backend.onrender.com/api/schema/`.
- [x] Confirm public Swagger UI loads at `https://omms-backend.onrender.com/api/docs/swagger/`.
- [ ] Confirm admin diagnostics endpoint works for admin users. Endpoint is protected and returns `401` without credentials as expected.
- [!] Confirm `observability.0012_operationalmode` is applied in production. Local migration is applied and production schema exposes the operational-mode endpoint, but database migration proof still requires Render shell/database verification.

## Storage

- [ ] Configure durable media storage for site images, media unit images, and POE evidence. Requires production env/storage verification.
- [ ] Configure private document storage for invoices, contracts, receipts, reports, and training-sensitive files. Requires production env/storage verification.
- [ ] Confirm signed private URLs do not expose storage secrets. Backend tests cover this locally; production storage still needs smoke validation.
- [ ] Confirm upload size limits and object-storage permissions.

## Background Jobs

- [!] Configure `CELERY_BROKER_URL`. Local Celery report is valid; production Redis URL requires Render/env verification.
- [!] Configure `CELERY_RESULT_BACKEND`. Local Celery report is valid; production backend requires Render/env verification.
- [x] Start web process. Public backend web process is responding.
- [ ] Start Celery worker: `celery -A config worker --loglevel=info`. Requires Render worker verification.
- [ ] Start Celery beat: `celery -A config beat --loglevel=info`. Requires Render beat verification.
- [ ] Confirm Operations System Status shows Redis configured and worker readiness acceptable. Requires admin login.
- [ ] Run a small export job and confirm completion/download. Requires admin login.
- [ ] Run a small import preview and confirm no records are created before confirmation. Requires admin login.
- [ ] Render web command should be `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`.
- [ ] Render worker command should be `celery -A config worker --loglevel=info`.
- [ ] Render beat command should be `celery -A config beat --loglevel=info`.

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

- [!] Admin can access Operations, diagnostics, maintenance mode, training, imports/exports, and dashboard customization. Smoke plan documented; execution requires production admin credentials.
- [!] Operations can access POE, inventory operations, jobs, alerts, and non-finance operational analytics. Smoke plan documented; execution requires production operations credentials.
- [!] Finance can access billing, invoices, payments, collection risk, and finance training. Smoke plan documented; execution requires production finance credentials.
- [!] Field staff can access assigned work and POE upload only. Smoke plan documented; execution requires production field credentials.
- [!] Client/user can access only allowed campaign, invoice/statement, and training visibility. Smoke plan documented; execution requires production client credentials, if client role is enabled.
- [x] Hidden dashboard widgets do not trigger unauthorized data fetches in local Playwright/backend validation.
- [x] Operational search permission behavior is covered locally; production role smoke still requires credentials.

## Post-Deployment Smoke

- [!] Login succeeds with admin account. Requires production admin credentials.
- [!] Operations summary loads. Requires production admin credentials.
- [!] Dashboard customization save/restore works. Requires production admin credentials.
- [!] Training guide download works. Endpoint is protected and returns `401` without credentials as expected; authenticated download requires production credentials.
- [!] Notification preferences save/read. Requires production credentials.
- [!] Maintenance mode can be read by admin. Endpoint is protected and returns `401` without credentials as expected; do not update production mode without explicit approval.
- [!] Non-admin write is blocked in read-only mode. Requires production non-admin/admin credentials and an approved read-only test window.
- [!] Import Excel template downloads. Endpoint is protected and returns `401` without credentials as expected; authenticated download requires production credentials.
- [!] Import preview works with marked beta/test Excel. Do not confirm import unless approved test data is used.
- [!] Export job completes and file downloads. Requires production admin credentials and Celery worker verification.
- [!] Mobile field POE upload screen works against production API. Requires production field credentials and release/test build configuration.

## Rollback Plan

- [ ] Keep previous backend deployment available.
- [ ] Keep previous frontend Vercel deployment available for promotion rollback.
- [ ] Snapshot database before migrations.
- [ ] Do not roll back database schema blindly after writes; use forward-fix unless rollback has been rehearsed.
- [ ] Pause Celery beat before emergency rollback if scheduled jobs are causing issues.
