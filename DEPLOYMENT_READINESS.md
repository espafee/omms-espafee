# OMMS Deployment Readiness

This document captures the current deployment requirements for the OMMS beta.

## Current Readiness Summary

- Backend production settings are present and environment-driven.
- Frontend production build is passing.
- Database migrations are in place for the current schema.
- Media uploads are supported, but production needs real media storage and serving.
- Public campaign share links are implemented and working.

## Backend Environment Variables

Required:

- `DJANGO_SETTINGS_MODULE`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`
- `DJANGO_CORS_ALLOWED_ORIGINS`

Strongly recommended in production:

- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SESSION_COOKIE_SECURE`
- `DJANGO_CSRF_COOKIE_SECURE`
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_HSTS_SECONDS`
- `DJANGO_HSTS_INCLUDE_SUBDOMAINS`
- `DJANGO_HSTS_PRELOAD`

JWT / scheduled work:

- `JWT_ACCESS_TOKEN_MINUTES`
- `JWT_REFRESH_TOKEN_DAYS`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CELERY_OVERDUE_CHECK_HOUR`

Static / media:

- `DJANGO_STATIC_URL`
- `DJANGO_STATIC_ROOT`
- `DJANGO_MEDIA_URL`
- `DJANGO_MEDIA_ROOT`

Optional external object storage:

- `DJANGO_DEFAULT_FILE_STORAGE`
- `DJANGO_STATICFILES_STORAGE`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`
- `AWS_S3_ENDPOINT_URL`
- `AWS_S3_CUSTOM_DOMAIN`
- `AWS_DEFAULT_ACL`
- `AWS_QUERYSTRING_AUTH`

## Frontend Environment Variables

Required:

- `NEXT_PUBLIC_API_ROOT`

Optional, but currently supported by the frontend auth client:

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_AUTH_LOGIN_PATH`

Recommended production values:

- `NEXT_PUBLIC_API_ROOT=https://<backend-domain>/api/v1`
- `NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>/api/v1/users`
- `NEXT_PUBLIC_AUTH_LOGIN_PATH=/auth/login/`

## Migrations and Health Commands

Run before every production rollout:

```powershell
python manage.py migrate
python manage.py check
python manage.py showmigrations
```

Pre-release verification:

```powershell
python manage.py test
cd frontend
npm run build
```

## Static and Media Handling

### Static Files

- Django static files should be collected during deployment.
- Run:

```powershell
python manage.py collectstatic --noinput
```

- Production should serve static files from a real web server, CDN, or platform-native static-file layer.

### Media Uploads

- Local filesystem storage works for development and single-instance testing.
- Beta/production should not rely on ephemeral instance storage for user uploads.
- Prefer S3-compatible object storage for:
  - site images
  - media unit images
  - POE evidence uploads

If using S3-compatible storage, set:

- `DJANGO_DEFAULT_FILE_STORAGE`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_ENDPOINT_URL`
- any required bucket region/domain/auth options

## Auth and Security Notes

- JWT auth is enabled for API access.
- Session auth remains enabled for admin and browsable API use.
- Production already enforces:
  - secure secret-key check
  - required allowed-hosts check
  - secure cookie toggles via env
  - optional SSL redirect via env
  - HSTS settings via env
  - `X_FRAME_OPTIONS = DENY`
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`

Before launch, confirm:

- admin credentials are rotated away from any seed/demo defaults
- production secrets are not checked into source control
- CORS only allows trusted frontend origins
- CSRF trusted origins include the real backend/admin origin(s)

## CORS / CSRF

Backend API:

- `DJANGO_CORS_ALLOWED_ORIGINS` must include the deployed frontend origin
- example:
  - `https://app.example.com`

Backend admin / any session-backed form posts:

- `DJANGO_CSRF_TRUSTED_ORIGINS` must include the deployed Django origin(s)
- example:
  - `https://api.example.com`
  - `https://admin.example.com`

## Recommended Hosting

### Backend

Recommended starting point:

- Django API on Render Web Service
- Managed PostgreSQL
- S3-compatible object storage for uploads

Why:

- Render has an official Django deployment guide and supports Git-based auto-deploys and health-checked web services.
- This matches the current Docker/env/migration structure well with minimal platform-specific work.

Official references:

- Render Django guide: [Render Docs](https://render.com/docs/deploy-django)
- Render deploy behavior: [Render Deploys](https://render.com/docs/deploys/)

### Frontend

Recommended starting point:

- Next.js frontend on Vercel

Why:

- Vercel is the native hosting platform for Next.js and supports zero-config Next deployments, preview deployments, and production builds aligned with the current app-router setup.

Official reference:

- Next.js on Vercel: [Vercel Docs](https://vercel.com/docs/frameworks/nextjs)

## Dev vs Production Notes

### Development

- `DEBUG` may be enabled locally.
- Django can serve media files directly when `DEBUG=True`.
- Frontend can use `next dev`.
- Local SQLite may still exist for convenience, but beta/production should use PostgreSQL.

### Production

- `DEBUG=False`
- use PostgreSQL through `DATABASE_URL`
- use collected static files
- use durable media storage
- use restricted CORS origins
- use secure cookies and HTTPS-aware settings
- avoid running `next dev`; use a production build and runtime only

## Beta Launch Blockers To Verify Before Go-Live

- Production secrets are set to non-default values.
- Database is PostgreSQL, not local SQLite.
- Media uploads write to durable storage.
- Static files are collected and served correctly.
- Public share-link flow is tested on the real deployed domains.
- CORS and CSRF origins match the deployed frontend/backend hosts exactly.
