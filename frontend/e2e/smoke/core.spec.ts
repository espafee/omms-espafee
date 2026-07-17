import { expect, test } from "@playwright/test";

async function seedAdminSession(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("omms_access_token", "playwright-access-token");
    window.localStorage.setItem("omms_refresh_token", "playwright-refresh-token");
    window.localStorage.setItem(
      "omms_user",
      JSON.stringify({ id: 1, email: "admin@example.com", username: "admin", role: "admin" }),
    );
  });
}

test.describe("OMMS web smoke", () => {
  test("public shell routes respond without server errors", async ({ request }) => {
    for (const path of ["/login", "/estimate/example-token", "/report-issue/example-token"]) {
      const response = await request.get(path);
      expect(response.status(), `${path} should not 500`).toBeLessThan(500);
    }
  });

  test("protected workflow routes are available to the app shell", async ({ request }) => {
    for (const path of ["/dashboard", "/inventory", "/campaigns", "/bookings", "/billing", "/poe", "/operations", "/notifications", "/training"]) {
      const response = await request.get(path);
      expect(response.status(), `${path} should render or redirect cleanly`).toBeLessThan(500);
    }
  });

  test("invoice detail route exists for finance workflow deep links", async ({ request }) => {
    const response = await request.get("/billing/invoices/1");
    expect(response.status()).toBeLessThan(500);
  });

  test("login handles invalid credentials and successful redirect", async ({ page }) => {
    await page.route("**/api/v1/users/auth/login/", async (route) => {
      const body = route.request().postDataJSON() as { email?: string };
      if (body.email === "admin@example.com") {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            access: "playwright-access-token",
            refresh: "playwright-refresh-token",
            user: { id: 1, email: "admin@example.com", role: "admin" },
          }),
        });
        return;
      }
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "No active account found with the given credentials" }),
      });
    });

    await page.goto("/login");
    await page.getByLabel("Email").fill("wrong@example.com");
    await page.getByLabel("Password").fill("bad-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Invalid email or password. Please try again.")).toBeVisible();

    await page.getByLabel("Email").fill("admin@example.com");
    await page.getByLabel("Password").fill("DemoPass123!");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("sidebar navigation exposes every major module including Training", async ({ page }) => {
    await seedAdminSession(page);
    await page.route("**/api/v1/**", async (route) => {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "QA mock unavailable" }) });
    });

    await page.goto("/dashboard");
    for (const testId of [
      "sidebar-dashboard",
      "sidebar-inventory",
      "sidebar-campaigns",
      "sidebar-bookings",
      "sidebar-poe",
      "sidebar-billing",
      "sidebar-notifications",
      "sidebar-operations",
      "sidebar-training",
      "sidebar-setup",
    ]) {
      await expect(page.getByTestId(testId)).toBeVisible();
    }
  });

  test("inventory All Sites list renders filters and row actions", async ({ page }) => {
    await seedAdminSession(page);
    const adminUser = { id: 1, email: "admin@example.com", username: "admin", role: "admin" };
    const sites = [
      {
        id: 1,
        name: "Airport Road Billboard",
        code: "SITE-001",
        site_type: "billboard",
        address: "Airport Road",
        city: "Jammu",
        state: "Jammu and Kashmir",
        latitude: null,
        longitude: null,
        owner: 1,
        primary_image: null,
        image_gallery: [],
        created_at: "2026-05-01T00:00:00Z",
        updated_at: "2026-05-01T00:00:00Z",
      },
    ];
    const units = [
      {
        id: 1,
        site: 1,
        unit_code: "UNIT-001",
        face_count: 1,
        width: "20.00",
        height: "10.00",
        status: "available",
        is_illuminated: true,
        monthly_rate: "50000.00",
        facing_direction: "North",
        site_type: "single_side",
        primary_image: null,
        image_gallery: [],
        created_at: "2026-05-01T00:00:00Z",
        updated_at: "2026-05-01T00:00:00Z",
      },
    ];
    const allSites = [
      {
        id: 1,
        site_id: 1,
        site_code: "SITE-001",
        unit_ids: [1],
        unit_codes: ["UNIT-001"],
        title: "Airport Road Billboard",
        address: "Airport Road",
        city: "Jammu",
        state: "Jammu and Kashmir",
        media_type: "billboard",
        dimensions: "20.00 x 10.00",
        facing_direction: "North",
        unit_site_type: "single_side",
        status: "available",
        thumbnail_url: null,
        created_at: "2026-05-01T00:00:00Z",
        updated_at: "2026-05-02T00:00:00Z",
      },
    ];

    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace("/api/v1/", "");
      const paginated = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
      const payloadByPath: Record<string, unknown> = {
        "users/auth/me/": adminUser,
        "inventory/sites/": paginated(sites),
        "inventory/units/": paginated(units),
        "inventory/sites/all-sites/": paginated(allSites),
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(payloadByPath[path] ?? paginated([])),
      });
    });

    await page.goto("/inventory");

    await expect(page.getByRole("heading", { name: "All Sites" })).toBeVisible();
    const allSitesTable = page.locator(".all-sites-table");
    await expect(allSitesTable.getByText("SITE-001")).toBeVisible();
    await expect(allSitesTable.getByText("UNIT-001")).toBeVisible();
    await expect(allSitesTable).toContainText("Airport Road");
    await page.locator("#site-list-search").fill("Airport");
    await page.locator("#site-list-city").selectOption("Jammu");
    await page.locator("#site-list-status").selectOption("available");
    await page.locator("#site-list-media-type").selectOption("billboard");
    await page.locator("#site-list-unit-site-type").selectOption("single_side");
    await allSitesTable.getByRole("button", { name: "Edit" }).click();
    await expect(page.getByRole("heading", { name: "Editing Media Unit: UNIT-001" })).toBeVisible();
  });

  test("admin can open Training module and request PDF guides", async ({ page }) => {
    await seedAdminSession(page);
    let downloadRequested = false;
    await page.route("**/api/v1/training/documents/master-manual/download/", async (route) => {
      downloadRequested = true;
      await route.fulfill({
        contentType: "application/pdf",
        headers: {
          "Content-Disposition": "inline; filename=OMMS_Master_Training_Manual.pdf",
        },
        body: "%PDF-1.4\n%%EOF",
      });
    });

    await page.goto("/training");

    await expect(page.getByRole("heading", { name: "Training and help center" })).toBeVisible();
    await expect(page.getByTestId("training-card-master-manual")).toBeVisible();
    await expect(page.getByTestId("training-card-admin-super-admin")).toBeVisible();

    await page.getByTestId("training-download-master-manual").click();
    await expect.poll(() => downloadRequested).toBe(true);
  });

  test("unauthenticated users are redirected away from Training", async ({ page }) => {
    await page.goto("/training");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("operations page renders audit timeline without global audit warning", async ({ page }) => {
    await seedAdminSession(page);
    const adminUser = { id: 1, email: "admin@example.com", username: "admin", role: "admin" };
    const systemHealth = {
      status: "healthy",
      api_status: "healthy",
      database: { ok: true, diagnostic_queries_ok: true },
      redis: { configured: true },
      celery: { enabled: true, broker_configured: true, eager: false, mode: "enabled", worker_ready: "unknown", beat_configured: true },
      recent_failed_requests: 0,
      recent_slow_requests: 0,
      recent_failed_background_jobs: 0,
      active_jobs: 0,
      last_successful_import: null,
      last_successful_export: null,
      signals: [],
      deployment: { environment_name: "test", git_commit: "playwright", app_version: "test" },
      environment_mode: { mode: "normal", label: "Normal", message: "", is_write_blocking: false, updated_at: null, updated_by_email: null },
    };
    const summary = {
      poe: { total_poes: 0, suspicious_count: 0, outside_geofence_count: 0, missing_gps_count: 0, duplicate_replacement_count: 0, pending_review_count: 0, overdue_review_count: 0, trends_by_date: [], recent_suspicious: [] },
      poe_sla: {
        warning_count: 0,
        breach_count: 0,
        oldest_pending: null,
        unassigned_count: 0,
        reviewer_workload: [],
        suspicious_unresolved_count: 0,
        thresholds: { pending_warning_hours: 24, pending_breach_hours: 48, suspicious_warning_hours: 12, suspicious_breach_hours: 24, reviewer_overload_threshold: 10 },
      },
      kpis: {
        active_jobs: 0,
        failed_jobs: 0,
        suspicious_poes: 0,
        pending_poe_reviews: 0,
        poe_sla_warnings: 0,
        poe_sla_breaches: 0,
        notifications_today: 0,
        failed_requests: 0,
        active_users_today: 1,
        campaigns_running: 0,
        campaigns_ending_soon: 0,
        campaigns_poe_risk: 0,
        campaigns_billing_risk: 0,
        critical_campaigns: 0,
        invoice_collection_rate: 0,
        overdue_invoices: 0,
        overdue_invoice_value: "0.00",
        export_activity_today: 0,
      },
      billing_intelligence: { overdue_invoice_count: 0, overdue_amount: "0.00", collection_efficiency_percentage: 0, overdue_age_buckets: [], payment_trend: [], top_overdue_clients: [] },
      campaign_performance: { summary: { active_campaigns: 0, ending_soon_count: 0, poe_risk_count: 0, billing_risk_count: 0, critical_count: 0 }, campaigns: [], risk_distribution: [], poe_completion_trend: [], operational_health_trend: [] },
      charts: { import_export_trend: [], request_trend: [], poe_status_distribution: [], poe_rejection_trend: [], billing_trend: [], operations_activity: [], notification_volume: [], load_distribution: [], poe_reviewer_workload: [], overdue_age_buckets: [], payment_trend: [], campaign_risk_distribution: [], campaign_poe_completion_trend: [], campaign_operational_health_trend: [] },
      timeline: [],
      recent_critical_alerts: [],
      active_jobs: [],
      system_health: systemHealth,
      warnings: [],
    };

    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace("/api/v1/", "");
      if (path === "users/auth/me/") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(adminUser) });
        return;
      }
      if (path === "observability/operations-summary/") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(summary) });
        return;
      }
      if (path === "observability/audit-events/") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ count: 1, next: null, previous: null, results: [{ id: 1, event_type: "system.health", entity_type: "system", entity_id: "", severity: "info", actor_email: null, summary: "System healthy", created_at: new Date().toISOString() }] }),
        });
        return;
      }
      if (path === "observability/diagnostics/") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ system_health: systemHealth }) });
        return;
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }) });
    });

    await page.goto("/operations");

    await expect(page.getByRole("heading", { name: "Recent audit timeline" })).toBeVisible();
    await expect(page.getByText("system.health")).toBeVisible();
    await expect(page.getByText("Audit timeline could not be refreshed.")).toHaveCount(0);
    await expect(page.getByText("Audit timeline is temporarily unavailable.")).toHaveCount(0);
  });
});
