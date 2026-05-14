import { expect, type Page, test } from "@playwright/test";

const adminUser = {
  id: 1,
  email: "admin@omms.test",
  username: "admin",
  role: "admin",
  is_active: true,
};

const campaignSummary = {
  total_campaigns: 1,
  active_campaigns: 1,
  draft_campaigns: 0,
  completed_campaigns: 0,
  total_budget: "100000.00",
  active_budget: "100000.00",
  total_bookings: 1,
  live_bookings: 1,
  approved_assets: 0,
};

const bookingSummary = {
  total_bookings: 1,
  pending_bookings: 0,
  confirmed_bookings: 1,
  live_bookings: 1,
  completed_bookings: 0,
  cancelled_bookings: 0,
  unique_media_units: 1,
  total_booked_value: "50000.00",
  live_booked_value: "50000.00",
};

const billingSummary = {
  total_invoices: 0,
  issued_invoices: 0,
  overdue_invoices: 0,
  paid_invoices: 0,
  partially_paid_invoices: 0,
  payment_count: 0,
  total_invoiced: "0.00",
  overdue_amount: "0.00",
  total_paid: "0.00",
  outstanding_amount: "0.00",
};

const campaigns = [
  {
    id: 1,
    name: "Airport Launch",
    code: "CMP-001",
    client: 2,
    account_manager: 1,
    start_date: "2026-05-01",
    end_date: "2026-05-31",
    budget: "100000.00",
    status: "active",
    objective: "Smoke coverage",
    assets: [],
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
  },
];

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

function paginated<T>(results: T[]) {
  return {
    count: results.length,
    next: null,
    previous: null,
    results,
  };
}

async function mockApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/v1\/?/, "");

    const payloadByPath: Record<string, unknown> = {
      "users/auth/me/": adminUser,
      "campaigns/summary/": campaignSummary,
      "bookings/summary/": bookingSummary,
      "billing/invoices/summary/": billingSummary,
      "campaigns/": paginated(campaigns),
      "campaigns/access-links/": paginated([]),
      "users/clients/": paginated([]),
      "inventory/sites/": paginated(sites),
      "inventory/units/": paginated(units),
      "billing/invoices/": paginated([]),
    };

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payloadByPath[path] ?? paginated([])),
    });
  });
}

async function signInWithMockSession(page: Page) {
  await page.addInitScript((user) => {
    window.localStorage.setItem("omms_access_token", "playwright-smoke-token");
    window.localStorage.setItem("omms_user", JSON.stringify(user));
  }, adminUser);
}

test("login page loads", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByRole("heading", { name: "Operate inventory, campaigns, and billing from one place." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("protected routes redirect to login without a session", async ({ page }) => {
  for (const path of ["/dashboard", "/billing", "/inventory", "/campaigns"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  }
});

test.describe("authenticated shell smoke tests", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await signInWithMockSession(page);
  });

  test("dashboard shell and navigation render", async ({ page }) => {
    await page.goto("/dashboard");

    await expect(page.getByRole("heading", { name: "Dashboard overview" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    for (const item of ["Dashboard", "Inventory", "Campaigns", "Bookings", "POE", "Billing", "Setup"]) {
      await expect(page.getByRole("link", { name: item })).toBeVisible();
    }
    await expect(page.getByText("admin@omms.test")).toBeVisible();
  });

  for (const route of [
    { path: "/billing", heading: "Billing desk" },
    { path: "/inventory", heading: "Inventory command" },
    { path: "/campaigns", heading: "Campaign control" },
  ]) {
    test(`${route.heading} page loads`, async ({ page }) => {
      await page.goto(route.path);

      await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    });
  }
});
