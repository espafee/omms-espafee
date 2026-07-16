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
};

const defaultProfile = {
  role: "admin",
  role_label: "Admin",
  active_widgets: ["campaign_performance", "billing_risk", "assigned_work"],
  hidden_widgets: [],
  can_customize: true,
  can_view_finance: true,
  can_view_operations: true,
  available_widgets: [
    {
      key: "campaign_performance",
      label: "Campaign performance",
      category: "campaigns",
      description: "Active campaigns, delivery health, and POE completion.",
      href: "/campaigns",
      is_visible: true,
      is_required: false,
      sort_order: 0,
    },
    {
      key: "billing_risk",
      label: "Billing risk",
      category: "finance",
      description: "Overdue invoices, collection efficiency, and payment risk.",
      href: "/billing",
      is_visible: true,
      is_required: false,
      sort_order: 1,
    },
    {
      key: "assigned_work",
      label: "Assigned work",
      category: "field",
      description: "Current field assignments and site tasks.",
      href: "/poe/capture",
      is_visible: true,
      is_required: true,
      sort_order: 2,
    },
    {
      key: "unknown_future_widget",
      label: "Future widget",
      category: "future",
      description: "A future widget that older frontends should ignore.",
      href: "/dashboard",
      is_visible: true,
      is_required: false,
      sort_order: 3,
    },
  ],
};

async function seedAdminSession(page: Page) {
  await page.addInitScript((user) => {
    window.localStorage.setItem("omms_access_token", "playwright-access-token");
    window.localStorage.setItem("omms_user", JSON.stringify(user));
  }, adminUser);
}

async function mockDashboardApi(page: Page) {
  let profileState = structuredClone(defaultProfile);

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/v1\/?/, "");

    if (path === "observability/dashboard-profile/") {
      if (route.request().method() === "PATCH") {
        const body = route.request().postDataJSON() as {
          widgets?: Array<{ widget_key: string; is_visible: boolean; sort_order: number }>;
        };
        const widgetState = new Map((body.widgets ?? []).map((widget) => [widget.widget_key, widget]));
        profileState = {
          ...profileState,
          active_widgets: profileState.available_widgets
            .filter((widget) => widget.is_required || widgetState.get(widget.key)?.is_visible)
            .map((widget) => widget.key),
          hidden_widgets: profileState.available_widgets
            .filter((widget) => !widget.is_required && !widgetState.get(widget.key)?.is_visible)
            .map((widget) => widget.key),
          available_widgets: profileState.available_widgets.map((widget) => ({
            ...widget,
            is_visible: widget.is_required || Boolean(widgetState.get(widget.key)?.is_visible),
            sort_order: widgetState.get(widget.key)?.sort_order ?? widget.sort_order,
          })),
        };
      }
      if (route.request().method() === "POST") {
        profileState = structuredClone(defaultProfile);
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(profileState) });
      return;
    }

    const payloadByPath: Record<string, unknown> = {
      "users/auth/me/": adminUser,
      "campaigns/summary/": campaignSummary,
      "bookings/summary/": bookingSummary,
      "billing/invoices/summary/": billingSummary,
    };

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payloadByPath[path] ?? { count: 0, next: null, previous: null, results: [] }),
    });
  });
}

test("dashboard customization hides, shows, and restores visible sections", async ({ page }) => {
  await seedAdminSession(page);
  await mockDashboardApi(page);

  await page.goto("/dashboard");

  await expect(page.getByTestId("admin-executive-dashboard")).toBeVisible();
  await expect(page.getByTestId("admin-executive-dashboard")).not.toContainText("NaN");
  await expect(page.getByTestId("dashboard-widget-billing_risk")).toBeVisible();
  await expect(page.getByTestId("dashboard-widget-campaign_performance")).toBeVisible();
  await expect(page.getByTestId("dashboard-widget-assigned_work")).toBeVisible();
  await expect(page.getByTestId("dashboard-widget-slot-unknown_future_widget")).toHaveCount(0);
  await expect(page.getByTestId("dashboard-widget-slot-campaign_performance")).toHaveCount(1);
  await expect(page.getByTestId("dashboard-widget-slot-billing_risk")).toHaveCount(1);
  await expect.poll(async () =>
    page.locator('[data-testid^="dashboard-widget-slot-"]').evaluateAll((items) =>
      items.map((item) => item.getAttribute("data-testid")),
    ),
  ).toEqual([
    "dashboard-widget-slot-campaign_performance",
    "dashboard-widget-slot-billing_risk",
    "dashboard-widget-slot-assigned_work",
  ]);

  await page.getByText("Customize dashboard", { exact: true }).click();
  await page.getByLabel(/Billing risk/).uncheck();
  await expect(page.getByText("Dashboard preference saved.")).toBeVisible();
  await expect(page.getByTestId("dashboard-widget-billing_risk")).toBeHidden();

  await page.getByLabel(/Billing risk/).check();
  await expect(page.getByTestId("dashboard-widget-billing_risk")).toBeVisible();

  await page.getByLabel(/Campaign performance/).uncheck();
  await expect(page.getByTestId("dashboard-widget-campaign_performance")).toBeHidden();
  await page.getByRole("button", { name: "Restore defaults" }).click();
  await expect(page.getByText("Dashboard defaults restored.")).toBeVisible();
  await expect(page.getByTestId("dashboard-widget-campaign_performance")).toBeVisible();
});
