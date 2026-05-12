import { expect, test } from "@playwright/test";

test.describe("OMMS web smoke", () => {
  test("public shell routes respond without server errors", async ({ request }) => {
    for (const path of ["/login", "/estimate/example-token", "/report-issue/example-token"]) {
      const response = await request.get(path);
      expect(response.status(), `${path} should not 500`).toBeLessThan(500);
    }
  });

  test("protected workflow routes are available to the app shell", async ({ request }) => {
    for (const path of ["/dashboard", "/inventory", "/campaigns", "/bookings", "/billing", "/poe", "/operations", "/notifications"]) {
      const response = await request.get(path);
      expect(response.status(), `${path} should render or redirect cleanly`).toBeLessThan(500);
    }
  });

  test("invoice detail route exists for finance workflow deep links", async ({ request }) => {
    const response = await request.get("/billing/invoices/1");
    expect(response.status()).toBeLessThan(500);
  });
});
