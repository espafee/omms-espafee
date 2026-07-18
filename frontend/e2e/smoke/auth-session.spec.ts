import { expect, type Page, test } from "@playwright/test";

const adminUser = {
  id: 1,
  email: "admin@omms.test",
  username: "admin",
  role: "admin",
  is_active: true,
};

const dashboardProfile = {
  role: "admin",
  role_label: "Admin",
  active_widgets: ["campaign_performance", "assigned_work"],
  hidden_widgets: [],
  can_customize: true,
  can_view_finance: false,
  can_view_operations: true,
  available_widgets: [
    {
      key: "campaign_performance",
      label: "Campaign performance",
      category: "campaigns",
      description: "Active campaigns and POE completion.",
      href: "/campaigns",
      is_visible: true,
      is_required: false,
      sort_order: 0,
    },
    {
      key: "assigned_work",
      label: "Assigned work",
      category: "field",
      description: "Current field assignments.",
      href: "/poe/capture",
      is_visible: true,
      is_required: true,
      sort_order: 1,
    },
  ],
};

async function seedSession(page: Page, access = "valid-access") {
  await page.addInitScript(({ user, token }) => {
    window.localStorage.setItem("omms_access_token", token);
    window.localStorage.setItem("omms_user", JSON.stringify(user));
  }, { user: adminUser, token: access });
}

function dashboardPayload(path: string) {
  const payloads: Record<string, unknown> = {
    "users/auth/me/": adminUser,
    "observability/dashboard-profile/": dashboardProfile,
    "campaigns/summary/": {
      total_campaigns: 1,
      active_campaigns: 1,
      draft_campaigns: 0,
      completed_campaigns: 0,
      total_budget: "100000.00",
      active_budget: "100000.00",
      total_bookings: 0,
      live_bookings: 0,
      approved_assets: 0,
    },
    "bookings/summary/": {
      total_bookings: 0,
      pending_bookings: 0,
      confirmed_bookings: 0,
      live_bookings: 0,
      completed_bookings: 0,
      cancelled_bookings: 0,
      unique_media_units: 0,
      total_booked_value: "0.00",
      live_booked_value: "0.00",
    },
    "billing/invoices/summary/": {
      total_estimated: "0.00",
      total_approved_estimates: "0.00",
      total_invoices: 0,
      draft_invoices: 0,
      issued_invoices: 0,
      due_soon_invoices: 0,
      overdue_invoices: 0,
      paid_invoices: 0,
      partially_paid_invoices: 0,
      payment_count: 0,
      total_invoiced: "0.00",
      overdue_amount: "0.00",
      total_paid: "0.00",
      payments_received_this_month: "0.00",
      total_collected: "0.00",
      outstanding_amount: "0.00",
      outstanding_balance: "0.00",
      collection_efficiency_percentage: 0,
      average_days_to_payment: null,
      overdue_age_buckets: [],
      top_overdue_clients: [],
      payment_trend: [],
    },
  };
  return payloads[path] ?? { count: 0, next: null, previous: null, results: [] };
}

async function routeDashboardApi(page: Page, options: {
  expiredAccessToken?: string;
  refreshStatus?: number;
  refreshAbort?: boolean;
  delayRefreshMs?: number;
  logoutRevokesRefresh?: boolean;
  onRefresh?: () => void;
  onLogout?: () => void;
} = {}) {
  let isLoggedOut = false;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api\/v1\/?/, "");
    if (path === "users/auth/token/refresh/") {
      options.onRefresh?.();
      if (options.refreshAbort) {
        await route.abort("failed");
        return;
      }
      if (isLoggedOut && options.logoutRevokesRefresh) {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Refresh session expired. Please sign in again.", code: "session_expired" }),
        });
        return;
      }
      if (options.delayRefreshMs) {
        await new Promise((resolve) => setTimeout(resolve, options.delayRefreshMs));
      }
      if (options.refreshStatus && options.refreshStatus >= 400) {
        await route.fulfill({
          status: options.refreshStatus,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Refresh session expired. Please sign in again.", code: "session_expired" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ access: "fresh-access", user: adminUser, expires_in: 1200 }),
      });
      return;
    }
    if (path === "users/auth/logout/") {
      isLoggedOut = true;
      options.onLogout?.();
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    if (options.expiredAccessToken && request.headers().authorization === `Bearer ${options.expiredAccessToken}`) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Given token not valid for any token type" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(dashboardPayload(path)),
    });
  });
}

test("login page restores a valid cookie session before showing the form", async ({ page }) => {
  let refreshCalls = 0;
  await routeDashboardApi(page, { onRefresh: () => { refreshCalls += 1; } });

  await page.goto("/login");

  await expect(page.getByText("Checking your session...")).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByTestId("admin-executive-dashboard")).toBeVisible();
  expect(refreshCalls).toBe(1);
});

test("expired access token triggers one silent refresh and retries protected requests", async ({ page }) => {
  await seedSession(page, "expired-access");
  let refreshCalls = 0;
  await routeDashboardApi(page, {
    expiredAccessToken: "expired-access",
    delayRefreshMs: 100,
    onRefresh: () => { refreshCalls += 1; },
  });

  await page.goto("/dashboard");

  await expect(page.getByTestId("admin-executive-dashboard")).toBeVisible();
  await expect.poll(() => refreshCalls).toBe(1);
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("omms_access_token"))).toBe("fresh-access");
});

test("temporary refresh network failure does not immediately clear the session", async ({ page }) => {
  await seedSession(page, "expired-access");
  await routeDashboardApi(page, { expiredAccessToken: "expired-access", refreshAbort: true });

  await page.goto("/dashboard");

  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("omms_access_token"))).toBe("expired-access");
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("omms_user"))).not.toBeNull();
});

test("invalid refresh session redirects to login with inactivity expiry message", async ({ page }) => {
  await routeDashboardApi(page, { refreshStatus: 401 });

  await page.goto("/login");

  await expect(page.getByText("Your session expired after 72 hours of inactivity. Please sign in again.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("explicit logout clears local state and revokes the current server session", async ({ page }) => {
  await seedSession(page, "valid-access");
  let logoutCalls = 0;
  await routeDashboardApi(page, { logoutRevokesRefresh: true, onLogout: () => { logoutCalls += 1; } });

  await page.goto("/dashboard");
  await expect(page.getByTestId("admin-executive-dashboard")).toBeVisible();
  await page.locator(".sidebar-button").click();

  await expect(page).toHaveURL(/\/login$/);
  await expect.poll(() => logoutCalls).toBe(1);
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("omms_access_token"))).toBeNull();
  await expect(page.getByText("Your session expired after 72 hours of inactivity. Please sign in again.")).toHaveCount(0);
});
