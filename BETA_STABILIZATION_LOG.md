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

Use `https://omms.vercel.app` for the first controlled beta unless/until the VistaAi `/omms` routing is corrected.

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
