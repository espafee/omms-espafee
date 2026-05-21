# Tenant Identifier Production Runbook

Purpose: safely run the Phase 1F tenant identifier audit in production before any Phase 1G uniqueness or sequence migration.

This runbook is read-only. It must not be combined with schema changes, data rewrites, invoice numbering changes, estimate numbering changes, or POE idempotency changes.

## Where To Run

Run from the Render backend production shell, or any production shell using the same deployed code, database, settings, and environment variables as the OMMS backend service.

Expected working directory:

```bash
/opt/render/project/src
```

If the Render shell opens elsewhere, first locate the Django project root containing `manage.py`.

## Current Access Status

As of 2026-05-21, production audit execution is still pending because this Codex environment does not have:

- Render CLI access
- Render dashboard shell access
- a production `DATABASE_URL`
- a safe authenticated job-runner path for Django management commands

Phase 1G remains blocked until an authorized operator runs the commands below in Render and saves the sanitized output.

## Commands

Human-readable output:

```bash
python manage.py audit_tenant_identifiers
```

Machine-readable output:

```bash
python manage.py audit_tenant_identifiers --format json
```

Recommended capture:

```bash
python manage.py audit_tenant_identifiers --format json > tenant_identifier_audit_production_$(date +%Y%m%d_%H%M%S).json
```

If Render shell does not allow file persistence, copy the JSON output into the deployment notes or secure internal launch folder.

## Expected Output

The output should state:

- `constraints_changed: false`
- `numbering_behavior_changed: false`
- identifier targets with record counts
- duplicate group counts
- null tenant counts
- sequence ownership gaps
- Phase 1G recommendations

Sequence ownership gaps are expected. Duplicate groups and null-tenant ownership gaps require review.

## How To Interpret Duplicate Groups

Duplicate groups are normalized by lower-casing identifiers. This catches case-collisions such as:

- `SITE-001`
- `site-001`

Risk meanings:

- `cross-tenant`: the same normalized identifier appears under more than one tenant. This blocks tenant-scoped uniqueness migration until resolved.
- `same-tenant-or-case-collision`: multiple rows share the same normalized identifier inside one tenant or due to case differences. This blocks migration until the rows are cleaned up or explicitly grandfathered.

Current global DB uniqueness may prevent many cross-tenant duplicates today. A zero duplicate result does not remove the need for sequence ownership changes.

## What Blocks Phase 1G

Phase 1G is blocked if production audit shows:

- any duplicate group for a constraint planned for migration
- any business record with unresolved null tenant ownership
- invoices or estimates without a clear tenant path
- POEs with non-empty `client_upload_id` but missing booking/campaign tenant
- import/export jobs with tenant gaps that could expose generated files across tenants
- alert rules/events with ambiguous platform-default versus tenant-override ownership
- saved views or dashboard preferences with tenant gaps
- any uncertainty about whether `SupplierProfile.gstin` should remain globally unique

## What Is Safe To Proceed With

It is safe to proceed to Phase 1G design only if:

- duplicate group count is `0` for the targeted identifier
- null-tenant count is `0` or every row is documented as intentionally platform/global
- invoice sequence ownership has a forward-only migration design
- issued invoice and estimate numbers will remain immutable
- rollback and forward-fix notes exist for the specific constraint being changed
- the migration is scoped to one identifier family at a time

## No-Change / Rollback Guidance

This runbook should not change data. If unexpected output appears:

1. Stop.
2. Do not run migrations that alter uniqueness constraints.
3. Save the JSON output.
4. Document affected models and identifiers.
5. Resolve data ownership or duplicate cleanup in a separate reviewed task.
6. Re-run the audit after cleanup.

If a future Phase 1G migration fails during deployment:

- do not manually edit identifiers in production without a reviewed cleanup plan
- roll back the deployment if schema migration did not complete
- if migration completed but app behavior fails, deploy a forward fix that preserves issued numbers and existing identifiers
- keep the production audit output attached to the incident/deployment record

## Render Checklist

Before running:

- confirm backend service is on the intended Git SHA
- confirm the shell is attached to the backend web service, not a local/dev database
- confirm `python manage.py migrate --check` is clean
- confirm production database target is correct
- confirm no constraint-changing migration is queued in the same release

After running:

- attach human-readable summary to `DEPLOYMENT_CHECKLIST.md` or beta launch notes
- preserve JSON output securely
- mark Phase 1G as blocked or ready per `PHASE_1G_IDENTIFIER_CONSTRAINT_CHECKLIST.md`

## Manual Render Dashboard Steps

1. Open the Render dashboard.
2. Select the `omms-backend` web service.
3. Confirm the latest deployed Git SHA is the intended `main` commit.
4. Open Shell for the backend service.
5. Run `pwd` and confirm the shell is in or can reach the Django project root containing `manage.py`.
6. Run `python manage.py migrate --check`.
7. Run `python manage.py audit_tenant_identifiers`.
8. Run `python manage.py audit_tenant_identifiers --format json`.
9. Copy the sanitized counts into `TENANT_IDENTIFIER_AUDIT_PRODUCTION_RESULT.md`.
10. Do not run any uniqueness migration in the same session.
