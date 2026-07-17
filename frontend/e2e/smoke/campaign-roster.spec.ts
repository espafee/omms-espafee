import { expect, test, type Page } from "@playwright/test";

const adminUser = {
  id: 1,
  email: "admin@example.com",
  username: "admin",
  role: "admin",
};

const performance = {
  campaign_id: 1,
  campaign_name: "",
  campaign_code: "",
  risk_status: "on_track",
  poe_completion_percentage: 75,
  booked_sites_count: 2,
  sites_with_approved_poe: 1,
  sites_missing_poe: 1,
  pending_poe_count: 1,
  suspicious_poe_count: 0,
  invoice_generated: true,
  billing_status: "issued",
  payment_collection_status: "pending",
  payment_completion_percentage: 40,
  has_overdue_invoice: false,
  operational_delay_indicators: [],
  pending_amount: "60000.00",
  overdue_amount: "0.00",
  is_ending_soon: false,
};

const campaigns = [
  {
    id: 2,
    name: "Completed City Launch",
    code: "CITY-002",
    client: 10,
    account_manager: 1,
    start_date: "2025-01-01",
    end_date: "2025-01-31",
    budget: "180000.00",
    status: "active",
    effective_status: "ended",
    is_ended: true,
    is_ongoing: false,
    is_upcoming: false,
    objective: "Completed urban awareness campaign.",
    assets: [],
    performance: { ...performance, campaign_id: 2, campaign_name: "Completed City Launch", campaign_code: "CITY-002" },
    created_at: "2026-01-01T08:00:00Z",
    updated_at: "2026-01-01T08:00:00Z",
  },
  {
    id: 1,
    name: "Live Metro Reach",
    code: "METRO-001",
    client: 10,
    account_manager: 1,
    start_date: "2026-01-01",
    end_date: "2027-12-31",
    budget: "100000.00",
    status: "active",
    effective_status: "ongoing",
    is_ended: false,
    is_ongoing: true,
    is_upcoming: false,
    objective: "Grow commuter reach.",
    assets: [],
    performance: { ...performance, campaign_name: "Live Metro Reach", campaign_code: "METRO-001" },
    created_at: "2026-02-01T08:00:00Z",
    updated_at: "2026-02-01T08:00:00Z",
  },
];

async function seedAdminSession(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("omms_access_token", "playwright-access-token");
    window.localStorage.setItem("omms_refresh_token", "playwright-refresh-token");
    window.localStorage.setItem(
      "omms_user",
      JSON.stringify({ id: 1, email: "admin@example.com", username: "admin", role: "admin" }),
    );
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (value: string) => {
          window.localStorage.setItem("playwright_clipboard", value);
        },
      },
    });
  });
}

async function mockCampaignApis(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1/", "");

    if (path === "users/auth/me/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(adminUser) });
      return;
    }
    if (path === "campaigns/") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ count: campaigns.length, next: null, previous: null, results: campaigns }),
      });
      return;
    }
    if (path === "campaigns/summary/") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          total_campaigns: 2,
          active_campaigns: 1,
          draft_campaigns: 0,
          completed_campaigns: 1,
          total_budget: "280000.00",
          active_budget: "100000.00",
          total_bookings: 2,
          live_bookings: 1,
          approved_assets: 0,
          ending_soon_count: 0,
          campaigns_at_risk: 0,
          campaigns_poe_risk: 0,
          campaigns_billing_risk: 0,
          critical_campaigns: 0,
        }),
      });
      return;
    }
    if (path === "campaigns/access-links/") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          count: 2,
          next: null,
          previous: null,
          results: [
            {
              id: 101,
              campaign: 1,
              public_path: "/campaigns/public/live-token/",
              link_status: "active",
              token_prefix: "live-tok",
              is_active: true,
              expires_at: null,
              revoked_at: null,
              created_by: 1,
              revoked_by: null,
              last_accessed_at: null,
              created_at: "2026-02-01T08:00:00Z",
              updated_at: "2026-02-01T08:00:00Z",
            },
            {
              id: 102,
              campaign: 2,
              public_path: "/campaigns/public/ended-token/",
              link_status: "ended",
              token_prefix: "ended-to",
              is_active: true,
              expires_at: null,
              revoked_at: null,
              created_by: 1,
              revoked_by: null,
              last_accessed_at: null,
              created_at: "2026-01-01T08:00:00Z",
              updated_at: "2026-01-01T08:00:00Z",
            },
          ],
        }),
      });
      return;
    }
    if (path === "campaigns/2/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(campaigns[0]) });
      return;
    }
    if (path === "observability/operational-mode/") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }),
      });
      return;
    }
    if (path === "users/clients/" || path === "users/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ count: 0, results: [] }) });
      return;
    }

    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });
}

test.describe("campaign roster", () => {
  test("uses effective lifecycle, filters ended campaigns, and keeps internal detail available", async ({ page }) => {
    await seedAdminSession(page);
    await mockCampaignApis(page);
    await page.goto("/campaigns");

    const rows = page.locator(".campaign-roster-table tbody tr");
    await expect(rows).toHaveCount(2);
    await expect(rows.first()).toContainText("Live Metro Reach");
    await expect(page.getByText("Ongoing campaigns")).toBeVisible();

    await page.getByRole("button", { name: "Ended", exact: true }).click();
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText("Completed City Launch");
    await expect(rows.first()).toContainText("Campaign ended · public access closed");
    await expect(rows.first()).toHaveClass(/campaign-row-ended/);

    await page.getByRole("link", { name: "View Completed City Launch" }).click();
    await expect(page).toHaveURL(/\/campaigns\/2$/);
    await expect(page.getByRole("heading", { name: "Completed City Launch" })).toBeVisible();
    await expect(page.getByText("Administrative status")).toBeVisible();
  });

  test("copies an active share link without navigation or scroll movement", async ({ page }) => {
    await seedAdminSession(page);
    await mockCampaignApis(page);
    await page.goto("/campaigns");

    const ongoingRow = page.locator(".campaign-roster-table tbody tr").filter({ hasText: "Live Metro Reach" });
    await expect(ongoingRow).toBeVisible();
    await ongoingRow.scrollIntoViewIfNeeded();
    const beforeUrl = page.url();
    const beforeScroll = await page.evaluate(() => window.scrollY);

    await ongoingRow.getByRole("button", { name: "Copy", exact: true }).click();

    await expect(ongoingRow.getByText("Link copied", { exact: true })).toBeVisible();
    await expect.poll(() => page.url()).toBe(beforeUrl);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(beforeScroll);
    await expect.poll(() => page.evaluate(() => window.localStorage.getItem("playwright_clipboard"))).toContain(
      "/campaigns/public/live-token/",
    );
  });
});
