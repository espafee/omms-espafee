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
});
