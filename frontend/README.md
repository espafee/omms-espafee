# Frontend

Minimal Next.js frontend scaffold for JWT login.

## Setup

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Run the Django backend separately on port `8000`. The backend is configured to allow browser requests from the Next.js dev server on port `3000`.

## Environment

- `NEXT_PUBLIC_API_ROOT=http://127.0.0.1:8000/api/v1`
- `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1/users`
- `NEXT_PUBLIC_AUTH_LOGIN_PATH=/auth/login/`

## Pages

- `/login`
- `/dashboard`

## Behavior

- Email and password are posted to the backend login endpoint
- JWT access token is stored in `localStorage`
- The user is redirected to `/dashboard` after successful login
- Dashboard cards load live campaign, booking, and billing summaries
