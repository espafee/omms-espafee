# Outdoor Media Management System (OMMS)

OMMS is a full-stack platform for managing outdoor media operations: inventory, campaigns, bookings, proof of execution, billing, and client reporting. It is built with Django REST Framework on the backend and Next.js on the frontend.

The project currently works as an operating system for an outdoor media company and provides a strong base for becoming a scalable SaaS product for media owners, agencies, and advertisers.

## Product Overview

Outdoor media businesses usually manage site inventory, client campaigns, booking calendars, creative assets, installation evidence, and invoices across disconnected tools. OMMS brings those workflows into one system.

The platform supports:

- Media site and media unit management
- Site and unit image galleries
- Campaign creation and tracking
- Client-specific campaign visibility
- Booking management with date conflict validation
- Proof-of-execution capture and verification
- Public read-only campaign sharing through secure access tokens
- Invoice, invoice line, and payment tracking
- Role-based access for internal teams and clients
- API documentation through Swagger and ReDoc
- Background processing through Celery and Redis

## Core Users

- Admins: manage users, inventory, campaigns, access links, and system data.
- Sales teams: create campaigns, manage clients, and handle campaign workflows.
- Operations teams: manage inventory, upload site/unit images, capture POE, and verify execution.
- Finance teams: manage invoices and payments.
- Clients: view only their campaigns, bookings, POE records, and billing data.
- Public viewers: access safe read-only campaign reports through tokenized links.

## Technology Stack

### Backend

- Python
- Django
- Django REST Framework
- Simple JWT authentication
- PostgreSQL
- Celery
- Redis
- drf-spectacular for OpenAPI docs
- django-filter for filtering APIs
- Pillow for image handling

### Frontend

- Next.js 14
- React 18
- TypeScript
- Tailwind/PostCSS tooling
- JWT-based API access

### Infrastructure

- Docker
- Docker Compose
- Gunicorn
- PostgreSQL container
- Redis container
- Celery worker
- Celery beat scheduler

## Project Structure

```text
.
├── apps/
│   ├── billing/       # Invoices, invoice lines, payments, billing summaries
│   ├── bookings/      # Media unit bookings and availability validation
│   ├── campaigns/     # Campaigns, campaign assets, public access tokens
│   ├── inventory/     # Media sites, media units, rate cards, image galleries
│   ├── poe/           # Proof of execution records, media, verification logs
│   └── users/         # Custom user model, auth, client directory
├── config/
│   ├── settings/      # Base, local, production, and env settings
│   ├── celery.py      # Celery application
│   ├── urls.py        # Root URL routing
│   ├── asgi.py
│   └── wsgi.py
├── core/
│   ├── models.py      # Shared timestamp model
│   ├── permissions.py # Role-based permission class
│   ├── repositories.py
│   ├── services.py
│   ├── roles.py
│   └── viewsets.py
├── frontend/
│   ├── app/           # Next.js app routes
│   ├── components/    # Shared UI components
│   └── package.json
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── manage.py
├── requirements.txt
└── README.md
```

## Backend Architecture

The backend follows a modular Django architecture. Each domain app owns its models, serializers, views, repositories, services, URLs, admin registration, migrations, and tests.

The project uses a service and repository layer:

- Repositories handle queryset construction and access scoping.
- Services hold business rules and write workflows.
- ViewSets expose REST endpoints and delegate business logic to services.

This keeps the project easier to extend as business logic grows.

## Authentication And Authorization

Authentication uses JWT tokens through `djangorestframework-simplejwt`.

Main auth endpoints:

- `POST /api/v1/users/auth/register/`
- `POST /api/v1/users/auth/token/`
- `POST /api/v1/users/auth/token/refresh/`
- `POST /api/v1/users/auth/token/verify/`
- `GET /api/v1/users/auth/me/`

Authorization is role-based and object-aware. The shared `RoleBasedPermission` class checks:

- Whether the user is authenticated
- Whether the user's role can access the view
- Whether the user's role can perform write actions
- Whether the user has object-level access through the service/repository layer

Supported roles:

- `admin`
- `sales`
- `operations`
- `finance`
- `client`

## Domain Modules

### Users

The users app provides:

- Custom user model
- Email-based login
- Role field
- Organization name field
- Client directory endpoints
- Current user endpoint
- JWT token customization

Clients are represented as users with the `client` role.

### Inventory

The inventory app manages outdoor media assets.

Main entities:

- `MediaSite`: a physical location or placement group
- `MediaUnit`: an individual bookable face/unit
- `RateCard`: pricing for a media unit over a date range
- `MediaSiteImage`: image gallery for a site
- `MediaUnitImage`: image gallery for a unit

Inventory supports:

- Site type classification
- Location fields
- GPS coordinates
- Ownership assignment
- Primary image selection
- Image uploads
- Client-scoped inventory visibility

### Campaigns

The campaigns app manages advertiser/client campaigns.

Main entities:

- `Campaign`
- `CampaignAsset`
- `CampaignAccessToken`

Campaign features include:

- Client ownership
- Account manager assignment
- Campaign status tracking
- Budget tracking
- Creative asset management
- Approved asset filtering
- Secure public campaign sharing
- Token expiry and revocation

Public campaign links expose a safe, read-only payload and avoid exposing sensitive fields such as campaign budget, client object details, internal remarks, and private verification fields.

### Bookings

The bookings app links campaigns to media units over date ranges.

Main entity:

- `Booking`

Booking features include:

- Campaign-to-unit assignment
- Start and end dates
- Booked rate
- Booking status lifecycle
- Date validation
- Overlap prevention for confirmed/live bookings
- Client-scoped access
- Booking summary endpoints

### Proof Of Execution (POE)

The POE app manages evidence that a campaign has been executed in the field.

Main entities:

- `ProofOfExecution`
- `ProofOfExecutionMedia`
- `ProofOfExecutionVerificationLog`

POE features include:

- Execution date
- Capture timestamp
- GPS latitude/longitude
- Image/media upload
- Verification status
- Verification score
- Verification notes
- Verification audit logs

Current verification checks:

- Whether uploaded GPS coordinates are near the booked site
- Whether capture time falls inside the booking window
- Whether proof media is attached

The verification engine includes placeholders for future AI-based image comparison, OCR, and visible brand/content validation.

### Billing

The billing app manages campaign invoicing.

Main entities:

- `Invoice`
- `InvoiceLine`
- `Payment`

Billing features include:

- Invoice status tracking
- Invoice line items
- Payment records
- Payment-based invoice status updates
- Billing summaries
- Background task for marking overdue invoices

## API Documentation

When the backend server is running, API documentation is available at:

- Swagger UI: `http://127.0.0.1:8000/api/docs/swagger/`
- ReDoc: `http://127.0.0.1:8000/api/docs/redoc/`
- OpenAPI schema: `http://127.0.0.1:8000/api/schema/`
- Django admin: `http://127.0.0.1:8000/admin/`

## API Base Routes

```text
/api/v1/users/
/api/v1/inventory/
/api/v1/bookings/
/api/v1/campaigns/
/api/v1/poe/
/api/v1/billing/
```

## Frontend Overview

The frontend is a Next.js application under `frontend/`.

Current page areas include:

- `/login`
- `/dashboard`
- `/inventory`
- `/campaigns`
- `/bookings`
- `/poe`
- `/poe/capture`
- `/billing`
- `/campaigns/public/[token]`

The UI is built around an authenticated application shell with module navigation, role display, dashboard summaries, and module-specific pages.

Important note: the current frontend imports helper modules from `@/lib/...`. If those files are not present, the frontend build will need the missing API helper layer restored or recreated.

## Environment Variables

Start from `.env.example` and create a local `.env`.

Common backend variables include:

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgres://postgres:postgres@db:5432/outdoor_media
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
JWT_ACCESS_TOKEN_MINUTES=60
JWT_REFRESH_TOKEN_DAYS=7
```

Common frontend variables include:

```env
NEXT_PUBLIC_API_ROOT=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1/users
NEXT_PUBLIC_AUTH_LOGIN_PATH=/auth/login/
```

## Local Backend Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Create environment file:

```bash
cp .env.example .env
```

Run migrations:

```bash
python manage.py migrate
```

Create a superuser:

```bash
python manage.py createsuperuser
```

Start the backend:

```bash
python manage.py runserver
```

## Local Frontend Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

The frontend runs on:

```text
http://127.0.0.1:3000
```

The backend should run separately on:

```text
http://127.0.0.1:8000
```

## Docker Setup

Start the full stack:

```bash
docker compose up --build
```

Stop the stack:

```bash
docker compose down
```

Docker services:

- `web`: Django and Gunicorn
- `db`: PostgreSQL
- `redis`: Redis broker/cache
- `celery_worker`: background job worker
- `celery_beat`: scheduled tasks

## Testing

Run backend tests:

```bash
python manage.py test
```

Run Django system checks:

```bash
python manage.py check
```

Existing tests cover:

- Role-based access control
- Client directory permissions
- Inventory image API behavior
- POE media upload behavior
- POE verification behavior
- Public campaign access token behavior

## Data And Access Model

The current data model is role-aware and client-scoped:

- Backoffice users can access operational data based on role.
- Client users can only access data connected to their own campaigns.
- Public users can only access tokenized campaign reports.

This is a good foundation, but it is not yet full SaaS multi-tenancy. A scalable SaaS version should introduce an explicit tenant boundary such as `Organization` or `Workspace`.

## Recommended SaaS Evolution

To turn OMMS into a scalable SaaS product, the next major architecture step is multi-tenancy.

Recommended new models:

- `Organization`
- `OrganizationMembership`
- `Invitation`
- `Plan`
- `Subscription`
- `UsageRecord`
- `AuditLog`

Recommended changes:

- Add `organization` to all tenant-owned business records.
- Scope every repository by the user's organization membership.
- Make codes unique per organization instead of globally.
- Add organization-level roles and permissions.
- Add onboarding for creating a workspace.
- Add invite-based team management.
- Add SaaS subscription billing.
- Add plan limits for users, media units, campaigns, storage, and POE captures.
- Move media storage to S3-compatible object storage.
- Add audit logs for sensitive changes.
- Add CI/CD and production monitoring.

## SaaS Product Opportunities

High-value product features to add:

- Map-based inventory search
- Availability calendar by media unit
- Proposal builder
- Campaign package builder
- Client approval workflows
- Field worker mobile POE capture
- Offline POE capture support
- AI image comparison against inventory references
- OCR and brand validation for creatives
- Automated PDF POE reports
- Invoice PDF generation
- Payment gateway integration
- Occupancy and revenue dashboards
- Agency/client portal
- White-labeled client reporting

## Production Readiness Checklist

Before production launch:

- Add explicit tenant model and tenant-scoped access tests.
- Restore or complete missing frontend API helper modules if needed.
- Add CI for backend tests and frontend build.
- Use managed PostgreSQL.
- Use managed Redis.
- Use S3-compatible storage for media.
- Add CDN for public/media assets.
- Add structured logging.
- Add error tracking such as Sentry.
- Add API rate limiting.
- Add password reset and email verification.
- Use secure cookie-based auth or harden JWT storage strategy.
- Add database backups.
- Add health checks.
- Add deployment documentation.
- Add staging and production environment separation.

## Security Notes

- Write actions should remain permission-checked.
- Public/client-facing features should stay read-only by default.
- Public campaign tokens should remain hashed in the database.
- Sensitive financial and internal operation fields should not be exposed in public endpoints.
- Client users should never be able to mutate inventory, bookings, invoices, or verification records unless explicitly designed.
- Future SaaS tenancy must be enforced at the database/queryset level, not only in the frontend.

## Development Guidelines

- Preserve existing business logic.
- Prefer small, modular changes.
- Keep frontend resilient to null or missing API fields.
- Add or update tests when changing business rules.
- Preserve the existing design language for UI work.
- Avoid mock data unless explicitly requested.
- Keep public and client features token-based and read-only unless a workflow requires otherwise.

## Current Known Gaps

- No explicit organization/tenant model yet.
- SaaS subscription billing is not implemented.
- Frontend API helper files may be missing.
- Media files are stored locally by default.
- AI image comparison and OCR validation are placeholders.
- JWT is currently intended for browser storage; production auth should be reviewed.
- More reporting, audit, and monitoring features are needed for production SaaS.

## Summary

OMMS is already a meaningful foundation for an outdoor media operations platform. It has the right core modules, role-based access, client scoping, public campaign sharing, POE workflows, billing workflows, and background job scaffolding.

The most important next step is to introduce true multi-tenancy through organizations/workspaces. After that, OMMS can evolve into a scalable SaaS product with subscription billing, team management, field workflows, client portals, AI-assisted POE verification, and production-grade infrastructure.
