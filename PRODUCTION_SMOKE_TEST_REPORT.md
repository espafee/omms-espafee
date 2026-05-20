# OMMS Production Smoke Test Report

Generated: 2026-05-20
Last updated: 2026-05-21

## Summary

Production smoke validation was executed against the currently discoverable OMMS deployment surfaces:

- Web app: `https://omms.vercel.app`
- Alternate app path: `https://www.vistaaitech.com/omms/login`
- Backend API: `https://omms-backend.onrender.com`
- Additional Vercel project: `https://frontend-seven-alpha-68.vercel.app`

Result: **Conditional launch readiness.**

`https://omms.vercel.app` is deployed and wired to the Render backend API. The backend public health endpoint is healthy. Local backend/frontend/mobile validation passed.

VistaAi `/omms/login` has since been corrected to a redirect/launch page for `https://omms.vercel.app/login`, so the remaining blockers are backend infrastructure proof and authenticated role smoke.

## Commands And Results

### Backend Local Final Check

| Command | Result |
| --- | --- |
| `python manage.py check` | Passed |
| `python manage.py migrate --check` | Passed after local `observability.0012_operationalmode` was applied |
| `python manage.py test apps --verbosity 1 --parallel 4 --keepdb` | Passed, 278 tests |
| `python manage.py makemigrations --check --dry-run` | Passed, no changes detected |
| `celery -A config report` | Passed locally; Redis broker/result backend configured for local default |

### Frontend Local Final Check

| Command | Result |
| --- | --- |
| `npm run lint` | Passed |
| `npm run build` | Passed |
| `npx playwright test` | Passed, 9 tests |
| `npm audit --audit-level=moderate --json` | Passed, 0 moderate/high/critical findings |

### Mobile Final Check

| Command | Result |
| --- | --- |
| `npm install` | Passed |
| `npm run lint` | Passed |
| `npx expo-doctor` | Passed, 17/17 checks |
| `npx tsc --noEmit` | Passed |
| `npm audit --audit-level=moderate --json` | 6 moderate Expo/Metro transitive findings; planned Expo SDK upgrade recommended |

## Production Endpoint Smoke

| Check | URL | Result |
| --- | --- | --- |
| Backend public health | `https://omms-backend.onrender.com/health/` | Passed, `{"status":"ok","service":"omms","alive":true}` |
| Backend observability health | `https://omms-backend.onrender.com/api/v1/observability/health/` | Passed, public health response |
| Backend OpenAPI schema | `https://omms-backend.onrender.com/api/schema/` | Passed, `200` |
| Backend invalid login request | `https://omms-backend.onrender.com/api/v1/users/auth/login/` | Passed, returned expected `401` for invalid account |
| Protected training download unauthenticated | `https://omms-backend.onrender.com/api/v1/training/documents/master-manual/download/` | Passed security check, returned `401` |
| Protected import template unauthenticated | `https://omms-backend.onrender.com/api/v1/observability/import-export-jobs/inventory-sites/import-template/` | Passed security check, returned `401` |
| Protected operational mode unauthenticated | `https://omms-backend.onrender.com/api/v1/observability/operational-mode/` | Passed security check, returned `401` |
| Vercel OMMS app login route | `https://omms.vercel.app/login` | Passed, `200` |
| Vercel OMMS app operations route | `https://omms.vercel.app/operations` | Passed, `200` public shell |
| Vercel frontend alias login route | `https://frontend-seven-alpha-68.vercel.app/login` | Passed, `200`, but built with local API root and should not be used as production |
| VistaAi OMMS login route | `https://www.vistaaitech.com/omms/login` | Passed, redirects to `https://omms.vercel.app/login` and no longer embeds the app iframe |

## Vercel Deployment Findings

### `omms` Project

- Production URL: `https://omms.vercel.app`
- Deployment status: Ready
- Deployment ID: `dpl_CSPknGY3dhY1wbmE3JJGRAeAQGeH`
- Build created: 2026-05-20 14:32 IST
- Frontend JavaScript contains `https://omms-backend.onrender.com/api/v1`, which is the expected backend API root.

### `frontend` Project

- Production URL: `https://frontend-seven-alpha-68.vercel.app`
- Deployment status: Ready
- Deployment ID: `dpl_5NiyBaZ3Jte1C2DEQXdbbnLRwNEj`
- Vercel env list reports no environment variables configured for this project.
- Frontend JavaScript contains `http://127.0.0.1:8000/api/v1`; this deployment should not be treated as production until env vars are configured and redeployed.

### `vistaaitech.com/omms` Path

- `https://www.vistaaitech.com/omms/login` now redirects to `https://omms.vercel.app/login`.
- The path no longer embeds OMMS in an iframe and no longer attempts `https://omms.vercel.app/api/v1` calls.
- Backend CORS does not need `https://www.vistaaitech.com` for this redirect-based beta launch path.

## CORS/CSRF Findings

Verified CORS behavior:

- Origin `https://omms.vercel.app` is allowed by `https://omms-backend.onrender.com`.
- Origin `https://www.vistaaitech.com` is not currently returned as an allowed origin.

Implication:

- `https://omms.vercel.app` can call the backend directly.
- `https://www.vistaaitech.com/omms/login` is no longer an API-calling origin for OMMS; it hands users into the canonical app before login.

## Migration Status

- Local migration state is clean after applying `observability.0012_operationalmode`.
- Production migration state could not be proven without Render/database/admin access.
- Production deploy must run `python manage.py migrate` and verify `python manage.py migrate --check`.

## Redis/Celery Status

- Local Celery config loads successfully and registers the expected beat schedule.
- Production Redis/Celery worker/beat readiness could not be verified without Render worker logs or authenticated diagnostics.
- Public backend health only proves the web process is alive.

## Storage Status

- Protected PDF/template endpoints correctly reject unauthenticated requests.
- Actual private media/PDF storage backend configuration could not be verified without environment or authenticated download access.
- Durable object storage remains a production checklist item.

## Role-Based Smoke

Authenticated role-based smoke was not completed because production credentials were not available in this session.

Repeatable role matrix prepared for beta execution:

- Admin: login, dashboard, dashboard customization, Operations, System Status, maintenance-mode visibility without changing mode, Training PDFs, Inventory Import Template, operational search.
- Operations: login, POE review, POE SLA indicators, operations/campaign risk, import preview if permitted, alerts/escalations, no finance-only leakage.
- Finance: login, billing, invoices, collection efficiency/overdue analytics, finance alerts, no field-only/admin-only controls.
- Field staff: login, assigned work, POE upload flow, maintenance/read-only messaging, no finance/admin operations data.
- Client, if available: login, client-safe campaign/POE/invoice data only, no operations/admin intelligence.

Authenticated endpoint smoke plan:

- Training PDF authenticated download.
- Inventory Import Template authenticated download.
- Import preview with clearly marked beta/test Excel; do not confirm import unless approved.
- Export job start only after Celery worker verification and with safe test data/account.
- Notification inbox.
- Dashboard profile save/restore.
- Operational search role scoping.

Execution status: **pending production credentials**.

## Mobile Beta Smoke

- Mobile API root is controlled by `EXPO_PUBLIC_API_BASE_URL`.
- For beta builds, set `EXPO_PUBLIC_API_BASE_URL=https://omms-backend.onrender.com/api/v1`.
- Local mobile validation passed: install, lint, Expo Doctor, and TypeScript.
- Authenticated mobile login, assigned work, POE upload screen, and admin dashboard smoke remain pending because production mobile credentials/build were not available.

## Launch Recommendation

Recommended status: **CONDITIONAL GO for `https://omms.vercel.app` after production migrations, Redis/Celery worker/beat, storage, and authenticated role smoke are verified.**

## Required Fixes Before Public Launch

1. Apply production migrations and confirm `observability.0012_operationalmode`.
2. Verify production Redis/Celery worker/beat in Render.
3. Verify durable media/private document storage.
4. Complete authenticated role-based smoke with real production accounts.
5. Run safe authenticated import preview/export job smoke with marked beta data.
6. Rotate or document rotation of admin/demo credentials.
7. Plan mobile Expo SDK upgrade for moderate transitive audit findings.

## Controlled Beta Update

The safest beta entrypoint is currently `https://omms.vercel.app`. VistaAi `/omms/login` now safely redirects to that canonical app.
