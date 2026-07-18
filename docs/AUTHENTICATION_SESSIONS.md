# OMMS Authentication Sessions

## Root Cause Fixed

OMMS previously stored both JWT access and refresh tokens in browser `localStorage`. The frontend also cleared the local auth state immediately whenever a protected API request returned `401`. That meant normal access-token expiry, frontend reloads, browser restarts, temporary backend failures, or refresh-token handling drift could present as a full logout.

## Session Model

- Access tokens are short lived. The default is `20` minutes through `ACCESS_TOKEN_LIFETIME_MINUTES`.
- Refresh persistence is an opaque server-side `AuthRefreshSession`.
- The browser stores only the refresh-session secret in an HttpOnly cookie named `omms_refresh_session` by default.
- The cookie max age is `72` hours by default.
- The 72-hour rule is rolling inactivity: the session expires only after 72 consecutive hours without successful authenticated server activity or refresh.
- Active users can stay signed in beyond 72 total hours because successful authenticated requests update `last_activity_at`.

## Cookie Strategy

The refresh cookie is set with:

- `HttpOnly`
- `Secure` when `AUTH_REFRESH_COOKIE_SECURE=True`
- `SameSite` from `AUTH_REFRESH_COOKIE_SAMESITE`
- `Path=/`
- `Max-Age` from `REFRESH_COOKIE_MAX_AGE_SECONDS`

Production cross-site frontend/API deployments should use `AUTH_REFRESH_COOKIE_SAMESITE=None`, `AUTH_REFRESH_COOKIE_SECURE=True`, `DJANGO_CORS_ALLOW_CREDENTIALS=True`, and explicit trusted frontend origins in CORS/CSRF settings.

## Refresh Behavior

The frontend uses one central refresh mechanism:

- A protected API `401` attempts one silent refresh.
- Concurrent `401` responses share the same refresh request.
- The original request retries once after refresh succeeds.
- A temporary refresh network error does not clear local auth state.
- Auth is cleared only when the backend rejects the refresh session as expired, revoked, invalid, or tied to an inactive user.

## Logout

Explicit logout calls `/api/v1/users/auth/logout/`, revokes the current refresh session, clears the cookie, clears local access/user state, and broadcasts the logout to other tabs.

## Environment Variables

- `ACCESS_TOKEN_LIFETIME_MINUTES=20`
- `SESSION_INACTIVITY_TIMEOUT_HOURS=72`
- `REFRESH_COOKIE_MAX_AGE_SECONDS=259200`
- `AUTH_REFRESH_COOKIE_NAME=omms_refresh_session`
- `AUTH_REFRESH_COOKIE_DOMAIN=`
- `AUTH_REFRESH_COOKIE_SAMESITE=None`
- `AUTH_REFRESH_COOKIE_SECURE=True`

## Manual Smoke Test

1. Sign in and confirm the dashboard loads.
2. Refresh the browser and confirm the user remains signed in.
3. Close and reopen the browser and confirm the user remains signed in.
4. Let the access token expire, then perform an authenticated action and confirm silent refresh succeeds.
5. Open OMMS in two tabs, log out from one tab, and confirm the other tab clears auth.
6. Simulate a temporary API or refresh network failure and confirm the user is not immediately logged out.
7. With a controlled low inactivity timeout, confirm a genuinely inactive session redirects to login with: `Your session expired after 72 hours of inactivity. Please sign in again.`
