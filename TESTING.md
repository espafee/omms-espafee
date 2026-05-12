# OMMS Testing Architecture

## Backend Django Tests

Run backend tests from the project root:

```powershell
cd C:\Users\Dell\Documents\Codex\omms-project
python manage.py test
```

`manage.py test` uses `core.test_runner.BackendOnlyDiscoverRunner`, which defaults discovery to the backend `apps` package. This prevents Python unittest discovery from scanning frontend tooling, Playwright specs, `node_modules`, `.next`, or browser artifacts.

Useful targeted runs:

```powershell
python manage.py test apps.billing.tests
python manage.py test apps.poe.tests
python manage.py test apps.issues
```

## Pytest Compatibility

`pytest.ini` is configured for future pytest usage:

- `testpaths = apps`
- frontend and generated artifact folders are excluded with `norecursedirs`
- Python test naming stays `tests.py`, `test_*.py`, or `*_tests.py`

Do not place backend Python tests under repo-root `tests/` unless the test runner is updated intentionally.

## Frontend Checks

Run frontend checks from the frontend workspace:

```powershell
cd C:\Users\Dell\Documents\Codex\omms-project\frontend
npm run lint
npm run build
```

These checks are independent of Django discovery and should not be invoked by backend test commands.

## Playwright Smoke Tests

Playwright specs live only under:

```text
frontend/e2e/smoke
```

Run smoke tests separately:

```powershell
cd C:\Users\Dell\Documents\Codex\omms-project\frontend
npx playwright test
```

By default, Playwright starts the local Next.js dev server on `http://127.0.0.1:3100`. To test a hosted deployment instead:

```powershell
$env:PLAYWRIGHT_BASE_URL="https://omms.vercel.app"
npx playwright test
```

Playwright reports, screenshots, videos, traces, and test results are frontend-scoped and gitignored.

## CI/CD Recommendation

Keep backend, frontend, and E2E phases separate:

- Backend job: install Python dependencies, then run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, and `python manage.py test`.
- Frontend job: install Node dependencies, then run `npm run lint` and `npm run build`.
- E2E job: run `npx playwright test` after frontend dependencies are installed and the target app is available.

Do not mix Python test discovery and Playwright discovery in the same command phase.
