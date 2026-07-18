import { expect, test, type Page } from "@playwright/test";

type MockTeamUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone_number: string;
  role: string;
  role_label: string;
  region: string;
  reports_to: number | null;
  reports_to_name: string;
  tenant: number;
  tenant_name: string;
  assigned_work_count: number;
  managed_campaign_count: number;
  assigned_work_summary: string;
  last_login: string | null;
  is_active: boolean;
  account_status: "active" | "inactive" | "setup_pending";
  has_usable_password: boolean;
  setup_sent_at: string | null;
  created_at: string;
  updated_at: string;
  setup_delivery?: "sent";
};

const admin = {
  id: 1,
  email: "admin@example.com",
  username: "admin",
  role: "admin",
  organization_name: "Alpha Outdoor",
  is_company_admin: true,
  is_platform_admin: false,
};

async function seedSession(page: Page, profile = admin) {
  await page.addInitScript((storedProfile) => {
    window.localStorage.setItem("omms_access_token", "playwright-access-token");
    window.localStorage.setItem("omms_refresh_token", "playwright-refresh-token");
    window.localStorage.setItem("omms_user", JSON.stringify(storedProfile));
  }, profile);
}

function initialUser(): MockTeamUser {
  return {
    id: 1,
    email: admin.email,
    first_name: "Asha",
    last_name: "Admin",
    full_name: "Asha Admin",
    phone_number: "",
    role: "admin",
    role_label: "Company Admin",
    region: "Jammu",
    reports_to: null,
    reports_to_name: "",
    tenant: 10,
    tenant_name: "Alpha Outdoor",
    assigned_work_count: 0,
    managed_campaign_count: 2,
    assigned_work_summary: "2 managed campaigns",
    last_login: "2026-07-17T08:00:00Z",
    is_active: true,
    account_status: "active",
    has_usable_password: true,
    setup_sent_at: null,
    created_at: "2026-07-01T08:00:00Z",
    updated_at: "2026-07-01T08:00:00Z",
  };
}

async function mockTeamApis(page: Page) {
  const users: MockTeamUser[] = [initialUser()];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1/", "");

    if (path === "users/auth/me/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(admin) });
      return;
    }
    if (path === "observability/operational-mode/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
      return;
    }
    if (path === "team/roles/") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          can_select_tenant: false,
          tenants: [{ id: 10, name: "Alpha Outdoor", slug: "alpha-outdoor" }],
          roles: [
            { key: "company_admin", value: "admin", label: "Company Admin", description: "Manage company access.", capabilities: ["team"] },
            { key: "field_staff", value: "field_staff", label: "Field Staff", description: "Complete assigned field work.", capabilities: ["assigned_work"] },
            { key: "poe_reviewer", value: "poe_reviewer", label: "POE Reviewer", description: "Review proof.", capabilities: ["poe_review"] },
          ],
        }),
      });
      return;
    }
    if (path === "team/users/" && request.method() === "GET") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ count: users.length, next: null, previous: null, results: users }) });
      return;
    }
    if (path === "team/users/" && request.method() === "POST") {
      const input = request.postDataJSON() as Record<string, unknown>;
      const created: MockTeamUser = {
        id: 99,
        email: String(input.email),
        first_name: String(input.first_name),
        last_name: String(input.last_name),
        full_name: `${input.first_name} ${input.last_name}`,
        phone_number: String(input.phone_number ?? ""),
        role: String(input.role),
        role_label: "Field Staff",
        region: String(input.region ?? ""),
        reports_to: null,
        reports_to_name: "",
        tenant: 10,
        tenant_name: "Alpha Outdoor",
        assigned_work_count: 0,
        managed_campaign_count: 0,
        assigned_work_summary: "No active assignments",
        last_login: null,
        is_active: true,
        account_status: "setup_pending",
        has_usable_password: false,
        setup_sent_at: "2026-07-17T09:00:00Z",
        created_at: "2026-07-17T09:00:00Z",
        updated_at: "2026-07-17T09:00:00Z",
        setup_delivery: "sent",
      };
      users.unshift(created);
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      return;
    }
    if (path === "team/users/99/deactivate/" && request.method() === "POST") {
      const target = users.find((user) => user.id === 99)!;
      target.is_active = false;
      target.account_status = "inactive";
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(target) });
      return;
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });
}

test.describe("Team and access", () => {
  test("company admin creates field staff and removes access without losing the row", async ({ page }) => {
    await seedSession(page);
    await mockTeamApis(page);
    await page.goto("/settings/team");

    await expect(page.getByRole("heading", { name: "Team & access" })).toBeVisible();
    await page.getByRole("button", { name: "Add team member" }).click();
    const dialog = page.getByRole("dialog", { name: "Add team member" });
    await expect(dialog.getByRole("option", { name: "Platform Admin" })).toHaveCount(0);
    await dialog.getByLabel("First name").fill("Ravi");
    await dialog.getByLabel("Last name").fill("Field");
    await dialog.getByLabel("Email").fill("ravi.field@alpha.test");
    await dialog.getByLabel("Role").selectOption("field_staff");
    await dialog.getByLabel("Region / location").fill("Jammu");
    await dialog.getByRole("button", { name: "Add team member" }).click();

    const newRow = page.locator(".team-table tbody tr").filter({ hasText: "ravi.field@alpha.test" });
    await expect(newRow).toContainText("Setup pending");
    page.once("dialog", (confirmation) => confirmation.accept());
    await newRow.getByRole("button", { name: "Remove access" }).click();
    await expect(newRow).toContainText("Access removed");
    await expect(newRow.getByRole("button", { name: "Restore access" })).toBeVisible();
  });

  test("mobile team cards remain usable at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedSession(page);
    await mockTeamApis(page);
    await page.goto("/settings/team");

    await expect(page.locator(".team-table-wrap")).toBeHidden();
    const mobileCard = page.locator(".team-mobile-card").filter({ hasText: "admin@example.com" });
    await expect(mobileCard).toBeVisible();
    await expect(mobileCard.getByText("Company Admin")).toBeVisible();
    await expect(mobileCard.getByText("Jammu")).toBeVisible();
    await expect(mobileCard.getByText("Actions")).toBeVisible();
  });

  test("unauthorized roles do not see Team navigation", async ({ page }) => {
    const financeProfile = {
      id: 7,
      email: "finance@example.com",
      username: "finance",
      role: "finance",
      organization_name: "Alpha Outdoor",
      is_company_admin: false,
      is_platform_admin: false,
    };
    await seedSession(page, financeProfile);
    await page.route("**/api/v1/**", async (route) => {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Mock unavailable" }) });
    });
    await page.goto("/dashboard");
    await expect(page.getByTestId("sidebar-team")).toHaveCount(0);
  });

  test("specialist navigation matches backend role boundaries", async ({ page }) => {
    const inventoryProfile = {
      id: 8,
      email: "inventory@example.com",
      username: "inventory",
      role: "inventory_manager",
      organization_name: "Alpha Outdoor",
      is_company_admin: false,
      is_platform_admin: false,
    };
    await seedSession(page, inventoryProfile);
    await page.route("**/api/v1/**", async (route) => {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Mock unavailable" }) });
    });
    await page.goto("/dashboard");

    await expect(page.getByTestId("sidebar-inventory")).toBeVisible();
    await expect(page.getByTestId("sidebar-campaigns")).toBeVisible();
    await expect(page.getByTestId("sidebar-bookings")).toBeVisible();
    await expect(page.getByTestId("sidebar-billing")).toHaveCount(0);
    await expect(page.getByTestId("sidebar-operations")).toHaveCount(0);
    await expect(page.getByTestId("sidebar-team")).toHaveCount(0);
  });
});
