# Outdoor Media Management System

Backend scaffold for an Outdoor Media Management System built with Django and Django REST Framework.

## Current Status

The project currently includes:

- Django project structure with apps for `users`, `inventory`, `bookings`, `campaigns`, `poe`, and `billing`
- Custom user model with JWT authentication
- Role-based permissions and client/tenant-aware queryset scoping
- Admin registrations for all apps
- Service and repository layers for scalable business logic
- Initial migrations for all domain apps
- Swagger/OpenAPI docs with `drf-spectacular`
- Docker, PostgreSQL, Redis, and Celery scaffolding
- Automated API access-control tests

Latest verified state:

- `manage.py test` passes with `10` tests
- `manage.py check` previously reported no system issues during test runs

## Project Structure

```text
.
├── apps/
│   ├── billing/
│   ├── bookings/
│   ├── campaigns/
│   ├── inventory/
│   ├── poe/
│   └── users/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── env.py
│   │   ├── local.py
│   │   └── production.py
│   ├── celery.py
│   └── urls.py
├── core/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── manage.py
└── requirements.txt
```

## Bundled Python In Codex

This Codex thread has a bundled Python runtime. Use it directly:

```powershell
$py = "C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $py --version
```

Optional for the current PowerShell session:

```powershell
$env:Path = "C:\Users\Dell\.cache\codex-runtimes\codex-primary-runtime\dependencies\python;" + $env:Path
python --version
```

## Local Setup

Install dependencies:

```powershell
& $py -m pip install -r requirements.txt
```

Copy environment variables:

```powershell
Copy-Item .env.example .env
```

Run migrations:

```powershell
& $py manage.py migrate
```

Start the development server:

```powershell
& $py manage.py runserver
```

## Useful Status Checks

Run Django checks:

```powershell
& $py manage.py check
```

Run tests:

```powershell
& $py manage.py test
```

See applied and pending migrations:

```powershell
& $py manage.py showmigrations
```

Open the Django shell:

```powershell
& $py manage.py shell
```

## API Docs And Admin

With the server running, open:

- Swagger UI: `http://127.0.0.1:8000/api/docs/swagger/`
- ReDoc: `http://127.0.0.1:8000/api/docs/redoc/`
- Schema: `http://127.0.0.1:8000/api/schema/`
- Admin: `http://127.0.0.1:8000/admin/`

## Auth Endpoints

- `POST /api/v1/users/auth/register/`
- `POST /api/v1/users/auth/token/`
- `POST /api/v1/users/auth/token/refresh/`
- `POST /api/v1/users/auth/token/verify/`
- `GET /api/v1/users/auth/me/`

The token endpoint is configured to authenticate with `email` and `password`.

## Docker Setup

This repository includes:

- Django web service
- PostgreSQL
- Redis
- Celery worker
- Celery beat

Start the full stack:

```powershell
docker compose up --build
```

Stop the stack:

```powershell
docker compose down
```

The compose setup uses values from `.env`. The default example points Django to PostgreSQL on the `db` service and Redis on the `redis` service.

## Key Files

- Settings: [config/settings/base.py](C:/Users/Dell/Documents/Codex/2026-04-19-you-are-a-senior-python-backend/config/settings/base.py)
- Root URLs: [config/urls.py](C:/Users/Dell/Documents/Codex/2026-04-19-you-are-a-senior-python-backend/config/urls.py)
- Permissions: [core/permissions.py](C:/Users/Dell/Documents/Codex/2026-04-19-you-are-a-senior-python-backend/core/permissions.py)
- Roles: [core/roles.py](C:/Users/Dell/Documents/Codex/2026-04-19-you-are-a-senior-python-backend/core/roles.py)
- Access-control tests: [apps/users/tests/test_access_control.py](C:/Users/Dell/Documents/Codex/2026-04-19-you-are-a-senior-python-backend/apps/users/tests/test_access_control.py)

## Suggested Next Steps

- Add CI to run `manage.py test` automatically
- Add factory/test utility modules to simplify future tests
- Add seed data or fixtures for demo usage
- Add custom dashboards or reporting endpoints per role
