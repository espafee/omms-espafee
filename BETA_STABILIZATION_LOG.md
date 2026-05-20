# OMMS Controlled Beta Stabilization Log

Started: 2026-05-20

## Milestone 1: Production Surface And API Routing Verification

Status: **Conditional / blocker identified**

### Verified Surfaces

- Backend API health: `https://omms-backend.onrender.com/health/`
  - Result: healthy JSON response.
- OMMS Vercel app: `https://omms.vercel.app`
  - Result: Vercel production deployment is Ready.
  - API root embedded in frontend bundle: `https://omms-backend.onrender.com/api/v1`.
- VistaAi website: `https://www.vistaaitech.com`
  - Owner project: `trustdial-website`, not the OMMS Vercel project.
  - Result: website deployment is Ready but separate from OMMS.

### Blocker

`https://www.vistaaitech.com/omms/login` loads a shell, but the built JavaScript points API calls at `https://omms.vercel.app`, not at the Render backend API. Since `https://omms.vercel.app/api/v1/...` is a frontend route and returns `404`, the VistaAi `/omms` path is not launch-ready.

Backend CORS currently allows `https://omms.vercel.app`. It does not currently allow `https://www.vistaaitech.com`.

### Safe Launch Options

1. **Launch controlled beta at `https://omms.vercel.app`**
   - Lowest risk.
   - Backend API routing is already correct.
   - Still requires production migrations, Redis/Celery, storage, and authenticated role smoke.

2. **Redirect `https://www.vistaaitech.com/omms/*` to `https://omms.vercel.app/*`**
   - Fast operational fix.
   - Does not preserve the VistaAi URL in the browser.
   - Avoids complex cross-project Next.js asset proxying.

3. **Create a proper VistaAi `/omms` hosted app path**
   - Requires a deliberate architecture decision.
   - Options include deploying OMMS with a compatible `basePath`/asset strategy or implementing path-based proxying at an infrastructure layer that can also handle Next.js static assets.
   - Must add `https://www.vistaaitech.com` to backend CORS/CSRF if the browser origin remains VistaAi.

### Deferred / Requires Access

- Production migration proof for `observability.0012_operationalmode`.
- Render worker/beat verification.
- Redis/Celery queue health verification.
- Durable media/private document storage verification.
- Authenticated role-based smoke.
- Production credential rotation proof.

## Current Beta Recommendation

Use `https://omms.vercel.app` for the first controlled beta. VistaAi `/omms/login` now redirects into this canonical app.

## Milestone 2: VistaAi OMMS Login Launch Path Stabilized

Status: **deployed / verified**

### Chosen Launch Path

`https://www.vistaaitech.com/omms/login` is now treated as a lightweight VistaAi launch page that redirects users to `https://omms.vercel.app/login`.

This is the safer controlled-beta approach because:

- `https://omms.vercel.app` is already built with the correct API root: `https://omms-backend.onrender.com/api/v1`.
- Redirecting keeps the browser origin on the OMMS app, so existing backend CORS/CSRF rules for `https://omms.vercel.app` remain valid.
- The VistaAi site no longer embeds the OMMS app in an iframe where API root and cross-origin behavior can drift.

### CORS Decision

No backend CORS/CSRF expansion is required for this fix because VistaAi is not making authenticated OMMS API calls. Users are redirected to the canonical OMMS beta app before login and API traffic.

### Production Verification

- Deployed `trustdial-website` production deployment `dpl_G22uXikyQzhhbCcJPkzHRsfDR9an`.
- Verified `https://www.vistaaitech.com/omms/login` renders the launch message and redirects to `https://omms.vercel.app/login`.
- Verified the live VistaAi page no longer contains an iframe and does not call `https://omms.vercel.app/api/v1`.

## Milestone 3: Render Backend Public Readiness Smoke

Status: **partially verified / Render dashboard access still required**

Date: 2026-05-21

### Public Production Checks Completed

- `GET https://omms-backend.onrender.com/health/`
  - Result: `200`, `{"status":"ok","service":"omms","alive":true}`.
- `GET https://omms-backend.onrender.com/api/schema/`
  - Result: `200`, OpenAPI schema served successfully.
  - Schema contains recent operational routes: `operational-mode`, inventory import template, dashboard profile, import confirm, and import/export retry.
- `GET https://omms-backend.onrender.com/api/docs/swagger/`
  - Result: `200`, Swagger UI loads.
- Protected unauthenticated endpoint smoke:
  - Training document list: `401`, not `500`.
  - Training PDF download: `401`, not `500`.
  - Inventory import template download: `401`, not `500`.
  - Import/export jobs: `401`, not `500`.
  - Operational mode: `401`, not `500`.

### Local Backend Checks Completed

- `manage.py check`: passed.
- `manage.py migrate --check`: passed.
- `manage.py test apps --verbosity 1 --parallel 4 --keepdb`: passed, 278 tests.
- Local `showmigrations observability` confirms `0012_operationalmode` is applied locally.
- Local Celery config loads and registers Redis transport plus beat schedules.

### What Still Requires Render Dashboard/Shell Access

- Exact deployed backend Git SHA. Public schema proves recent code is deployed, but the public backend does not expose commit metadata.
- Production migration table proof for `observability.0012_operationalmode`.
- Production `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` env values, without revealing secrets.
- Worker service existence/running status.
- Beat service existence/running status.
- Safe end-to-end background job execution in production.
- Authenticated import/export job creation and report download.
- Authenticated Training PDF and Inventory Import Template downloads.

### Required Render Service Commands

- Web: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
- Worker: `celery -A config worker --loglevel=info`
- Beat: `celery -A config beat --loglevel=info`

### Render Dashboard Checklist

1. Open the `omms-backend` Render web service and confirm the latest deployed commit matches GitHub `main`.
2. Open Render shell or deploy logs and run/confirm migration output includes `observability.0012_operationalmode`.
3. Confirm `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are set to managed Redis-compatible URLs.
4. Confirm a separate worker service exists with `celery -A config worker --loglevel=info`.
5. Confirm a separate beat service exists with `celery -A config beat --loglevel=info`.
6. Confirm worker logs show successful broker connection and task registration.
7. Trigger one small authenticated export job and verify it moves from queued/running to completed with a downloadable report.

## Milestone 4: Authenticated Production Role Smoke Plan

Status: **plan ready / execution pending credentials**

Date: 2026-05-21

### Credential Status

No production role credentials were provided in this session. Authenticated browser/API smoke was therefore not executed against production accounts.

### Non-Destructive Role Smoke Plan

Admin / owner:

- Login at `https://omms.vercel.app/login`.
- Confirm dashboard loads.
- Confirm dashboard customization save/restore persists after refresh.
- Confirm Operations dashboard loads without global error banners.
- Confirm System Status is visible.
- Confirm maintenance mode is visible but do not change it without explicit approval.
- Confirm Training Center lists permitted PDFs and one permitted PDF downloads.
- Confirm Inventory Import Template downloads.
- Confirm operational search returns scoped results.

Operations:

- Login.
- Confirm POE review page loads.
- Confirm POE SLA indicators are visible.
- Confirm operations/campaign-risk widgets are visible.
- Confirm import preview is available only if the role permits it.
- Confirm alerts/escalations are visible.
- Confirm finance-only details are not exposed unless this role is explicitly finance-enabled.

Finance:

- Login.
- Confirm billing page loads.
- Confirm invoices are visible.
- Confirm collection efficiency and overdue analytics are visible.
- Confirm finance alerts are visible.
- Confirm field-only/admin-only controls are not exposed.

Field staff:

- Login.
- Confirm assigned work is visible.
- Confirm POE upload flow is visible.
- Confirm maintenance/read-only message is respected.
- Confirm finance/admin operations data is not exposed.

Client, if available:

- Login.
- Confirm only client-safe campaign, approved POE, invoice/statement data is visible.
- Confirm operations/admin intelligence is not exposed.

### Authenticated Endpoint Smoke Plan

- Training PDF authenticated download.
- Inventory Import Template authenticated download.
- Import preview with a clearly marked beta/test Excel file; do not confirm import unless test data is approved.
- Export job start only from a safe test/admin account after worker verification.
- Notification inbox loads.
- Dashboard profile save/restore.
- Operational search role scoping.

### Mobile Beta Smoke Plan

- Confirm beta build has `EXPO_PUBLIC_API_BASE_URL=https://omms-backend.onrender.com/api/v1`.
- Login with field staff credentials.
- Confirm assigned work list.
- Confirm POE upload screen and GPS/photo readiness states.
- Confirm maintenance/read-only blocking is shown if active.
- Login with admin mobile credentials if available and confirm compact admin dashboard.

### Local Validation Completed

- Backend: `manage.py check`, `manage.py migrate --check`, and 278 app tests passed.
- Frontend: lint, build, and 9 Playwright smoke tests passed.
- Mobile: install, lint, Expo Doctor, and TypeScript passed.
