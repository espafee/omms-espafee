import { expect, test, type Page } from "@playwright/test";

const pixel = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
const admin = { id: 1, email: "admin@example.com", username: "admin", role: "admin", tenant: 1, tenant_name: "Alpha Outdoor", is_company_admin: true };
const platformAdmin = { id: 2, email: "platform@example.com", username: "platform", role: "admin", tenant: 99, tenant_name: "OMMS Platform", tenant_type: "platform", is_platform_admin: true, is_superuser: true };

async function seedAdmin(page: Page) {
  await page.addInitScript((profile) => {
    localStorage.setItem("omms_access_token", "planner-test-token");
    localStorage.setItem("omms_user", JSON.stringify(profile));
  }, admin);
}

async function seedPlatformAdmin(page: Page) {
  await page.addInitScript((profile) => {
    localStorage.setItem("omms_access_token", "platform-diagnostics-token");
    localStorage.setItem("omms_user", JSON.stringify(profile));
  }, platformAdmin);
}

async function fillCampaignDates(page: Page, start: string, end: string) {
  const startInput = page.getByLabel("Start date");
  const endInput = page.getByLabel("End date");
  await startInput.fill(start);
  await expect(startInput).toHaveValue(start);
  await endInput.fill(end);
  await expect(endInput).toHaveValue(end);
}

function publicPayload(showRates = false) {
  return {
    count: 1, next: null, previous: null,
    planner: { title: "Acme Live Media Planner", tenant_name: "Alpha Outdoor", client_name: "Acme India", contact_email: "sales@alpha.test", expires_at: "2027-01-01T00:00:00Z", show_rates: showRates, pricing_mode: showRates ? "standard_selling_rate" : "hidden", allow_proposal_submission: true, allow_image_download: false, client_rate_card_available: false },
    filters: { cities: ["Jammu"], locations: ["Central Junction"], formats: ["single_side"], facing_directions: ["North"], illumination: [{ value: "true", label: "Illuminated" }], availability_statuses: ["available"], rate_bounds: { min: showRates ? "50000.00" : null, max: showRates ? "50000.00" : null } },
    meta: { eligible_unit_count: 1, eligible_location_count: 1, unique_location_count: 1, has_campaign_dates: false },
    results: [{ public_id: "62807432-5e10-441f-a0e1-089cf5f42bb8", unit_code: "JMU-001-A", location_name: "Central Junction", public_address: "Central Road", city: "Jammu", region: "Jammu and Kashmir", dimensions: { width: "20.00", height: "10.00" }, display_format: "single_side", facing_direction: "North", is_illuminated: true, availability: { status: "available", label: "Available", reason: "Available for selected dates", conflict_count: 0 }, description: "Premium arterial road visibility.", features: ["High visibility"], primary_photo: { url: pixel, caption: "Main face", is_primary: true }, photos: [{ url: pixel, caption: "Main face", is_primary: true }, { url: pixel, caption: "Street view", is_primary: false }], image_download_allowed: false, monthly_rate: showRates ? "50000.00" : null }],
  };
}

function reconciliationPayload(pageNumber: number) {
  const units = Array.from({ length: 23 }, (_, index) => {
    const locationIndex = index < 4 ? Math.floor(index / 2) : index - 2;
    const locationName = `Planner Location ${String(locationIndex + 1).padStart(2, "0")}`;
    return {
      ...publicPayload(false).results[0],
      public_id: `62807432-5e10-441f-a0e1-089cf5f42b${String(index).padStart(2, "0")}`,
      unit_code: `REC-${String(index + 1).padStart(2, "0")}`,
      location_name: locationName,
      city: "Jammu",
    };
  });
  const results = pageNumber === 1 ? units.slice(0, 10) : pageNumber === 2 ? units.slice(10, 20) : units.slice(20);
  return {
    ...publicPayload(false),
    count: 23,
    next: pageNumber < 3 ? `http://127.0.0.1:8000/api/v1/public/media-planner/reconcile-token/?page=${pageNumber + 1}&page_size=10` : null,
    previous: pageNumber > 1 ? `http://127.0.0.1:8000/api/v1/public/media-planner/reconcile-token/?page=${pageNumber - 1}&page_size=10` : null,
    filters: {
      ...publicPayload(false).filters,
      locations: Array.from(new Set(units.map((unit) => unit.location_name))),
    },
    meta: {
      eligible_unit_count: 23,
      eligible_location_count: 21,
      unique_location_count: 21,
      eligible_count_before_filters: 23,
      location_count_before_filters: 21,
      results_count: 23,
      has_campaign_dates: false,
    },
    results,
  };
}

function emptyPayload(eligibleUnitCount: number, availability = false) {
  return {
    ...publicPayload(false),
    count: 0,
    results: [],
    filters: {
      cities: eligibleUnitCount ? ["Jammu"] : [],
      locations: eligibleUnitCount ? ["Central Junction"] : [],
      formats: eligibleUnitCount ? ["single_side"] : [],
      facing_directions: eligibleUnitCount ? ["North"] : [],
      illumination: eligibleUnitCount ? [{ value: "true", label: "Illuminated" }] : [],
      availability_statuses: availability ? ["booked"] : [],
      rate_bounds: { min: null, max: null },
    },
    meta: { eligible_unit_count: eligibleUnitCount, has_campaign_dates: availability },
  };
}

test("public client selects dates, opens gallery, builds basket and submits proposal", async ({ page }) => {
  const requests: string[] = [];
  let postCount = 0;
  await page.route("**/api/v1/public/media-planner/demo-token/**", async (route) => {
    requests.push(route.request().url());
    if (route.request().method() === "POST") {
      postCount += 1;
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ reference: "PRP-DEMO123", status: "submitted", message: "Proposal submitted" }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(publicPayload(false)) });
  });
  await page.goto("/media-planner/demo-token");
  await expect(page.getByRole("heading", { name: "Acme Live Media Planner" })).toBeVisible();
  expect(requests[0]).not.toContain("All+cities");
  expect(requests[0]).not.toContain("All+availability");
  expect(requests[0]).not.toContain("city=");
  expect(requests[0]).not.toContain("facing=");
  await page.getByLabel("City").selectOption("Jammu");
  await page.getByLabel("Location").selectOption("Central Junction");
  await page.getByLabel("Availability").selectOption("available");
  await page.getByLabel("Format").selectOption("single_side");
  await page.getByLabel("Facing").selectOption("North");
  await page.getByLabel("Illumination").selectOption("true");
  await expect.poll(() => requests.some((url) => url.includes("city=Jammu") && url.includes("location=Central+Junction") && url.includes("availability=available") && url.includes("display_format=single_side") && url.includes("facing=North") && url.includes("illumination=true"))).toBeTruthy();
  await expect(page.getByText("Rate on request")).toBeVisible();
  await page.getByRole("button", { name: "View photos for JMU-001-A" }).click();
  await expect(page.getByText("1 of 2")).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByText("2 of 2")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByText("2 of 2")).toHaveCount(0);
  await page.getByRole("button", { name: "Add to campaign" }).click();
  await expect(page.getByText("1 selected")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByText("1 selected")).toBeVisible();
  await page.getByRole("button", { name: "Request formal estimate" }).click();
  await expect(
    page.getByLabel("Campaign dates").getByText("Select campaign start and end dates before requesting a formal estimate."),
  ).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Create campaign proposal" })).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe("planner-start-date");

  await fillCampaignDates(page, "2026-08-31", "2026-08-01");
  await page.getByRole("button", { name: "Request formal estimate" }).click();
  await expect(page.getByLabel("Campaign dates").getByText("Campaign end date must be on or after the start date.")).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Create campaign proposal" })).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe("planner-end-date");

  await fillCampaignDates(page, "2026-08-01", "2026-08-31");
  await expect.poll(() => requests.some((url) => url.includes("start_date=2026-08-01") && url.includes("end_date=2026-08-31"))).toBeTruthy();
  await page.getByRole("button", { name: "Request formal estimate" }).click();
  const dialog = page.getByRole("dialog", { name: "Create campaign proposal" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("1 selected unit")).toBeVisible();
  await expect(dialog.getByText("Campaign dates: 1 Aug 2026 - 31 Aug 2026")).toBeVisible();
  await dialog.getByRole("button", { name: "Submit proposal" }).click();
  await expect(dialog.getByText("Enter a campaign name.")).toBeVisible();
  await expect(dialog.getByText("Enter the brand or company name.")).toBeVisible();
  expect(postCount).toBe(0);
  await dialog.getByLabel("Campaign name").fill("Summer Launch");
  await dialog.getByLabel("Brand / company").fill("Acme India");
  await dialog.getByLabel("Contact name").fill("Asha Client");
  await dialog.getByLabel("Email").fill("asha@acme.test");
  const submitButton = dialog.locator('button[type="submit"]');
  await submitButton.dblclick();
  await expect(submitButton).toHaveText("Submitting...");
  await expect(page.getByText("Reference PRP-DEMO123")).toBeVisible();
  expect(postCount).toBe(1);
  await expect(page.getByText("0 selected")).toBeVisible();
});

test("public proposal submission failure preserves form values and basket", async ({ page }) => {
  await page.route("**/api/v1/public/media-planner/failure-token/**", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ unit_public_ids: ["One or more selected units are unavailable through this planner link."] }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(publicPayload(false)) });
  });

  await page.goto("/media-planner/failure-token");
  await expect(page.getByRole("heading", { name: "Acme Live Media Planner" })).toBeVisible();
  await fillCampaignDates(page, "2026-08-01", "2026-08-31");
  await page.getByRole("button", { name: "Add to campaign" }).click();
  await page.getByRole("button", { name: "Request formal estimate" }).click();
  const dialog = page.getByRole("dialog", { name: "Create campaign proposal" });
  await dialog.getByLabel("Campaign name").fill("Summer Launch");
  await dialog.getByLabel("Brand / company").fill("Acme India");
  await dialog.getByLabel("Contact name").fill("Asha Client");
  await dialog.getByLabel("Email").fill("asha@acme.test");
  await dialog.getByRole("button", { name: "Submit proposal" }).click();
  await expect(dialog.getByText("One or more selected units are unavailable through this planner link.")).toBeVisible();
  await expect(dialog.getByLabel("Campaign name")).toHaveValue("Summer Launch");
  await expect(dialog.getByLabel("Brand / company")).toHaveValue("Acme India");
  await expect(page.getByLabel("Campaign proposal basket").getByText("1 selected", { exact: true })).toBeVisible();
});

test("public planner shows distinct empty and API failure states", async ({ page }) => {
  await page.route("**/api/v1/public/media-planner/zero-token/**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(emptyPayload(0)) }));
  await page.goto("/media-planner/zero-token");
  await expect(page.getByRole("heading", { name: "No media units are available in this planner" })).toBeVisible();

  await page.route("**/api/v1/public/media-planner/filter-token/**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(emptyPayload(1)) }));
  await page.goto("/media-planner/filter-token");
  await page.getByLabel("City").selectOption("Jammu");
  await expect(page.getByRole("heading", { name: "No media units match these filters" })).toBeVisible();

  await page.route("**/api/v1/public/media-planner/dates-token/**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(emptyPayload(1, true)) }));
  await page.goto("/media-planner/dates-token");
  await fillCampaignDates(page, "2026-08-01", "2026-08-31");
  await page.getByLabel("Availability").selectOption("available");
  await expect(page.getByRole("heading", { name: "No units are available for these dates" })).toBeVisible();

  await page.route("**/api/v1/public/media-planner/fail-token/**", (route) => route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Server unavailable" }) }));
  await page.goto("/media-planner/fail-token");
  await expect(page.getByRole("heading", { name: "Unable to load media units" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("public planner exposes rates only when the link permits them and remains usable at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/public/media-planner/rates-token/**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(publicPayload(true)) }));
  await page.goto("/media-planner/rates-token");
  await expect(page.getByText("INR 50,000 / month")).toBeVisible();
  await expect(page.locator(".planner-unit-card")).toHaveCount(1);
  await expect(page.locator(".planner-basket-bar")).toBeVisible();
});

test("public planner shows advertising-unit and location counts without collapsing duplicate locations", async ({ page }) => {
  const requestedPages: string[] = [];
  await page.route("**/api/v1/public/media-planner/reconcile-token/**", async (route) => {
    const url = new URL(route.request().url());
    requestedPages.push(url.searchParams.get("page") || "1");
    const pageNumber = Number(url.searchParams.get("page") || 1);
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(reconciliationPayload(pageNumber)) });
  });
  await page.goto("/media-planner/reconcile-token");
  await expect(page.getByRole("heading", { name: "23 advertising units across 21 locations" })).toBeVisible();
  await expect(page.getByText("23 eligible advertising units · 21 eligible locations")).toBeVisible();
  await expect(page.locator(".planner-unit-card")).toHaveCount(23);
  await expect(page.getByText("REC-01")).toBeVisible();
  await expect(page.getByText("REC-02")).toBeVisible();
  await expect(page.locator(".planner-unit-card").filter({ hasText: "Planner Location 01" })).toHaveCount(2);
  expect(requestedPages).toEqual(["1", "2", "3"]);
});

test("public planner proposal validation remains reachable on mobile widths", async ({ page }) => {
  await page.route("**/api/v1/public/media-planner/mobile-token-*/**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(publicPayload(false)) }));
  for (const width of [320, 360, 390, 430]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`/media-planner/mobile-token-${width}`);
    await page.getByRole("button", { name: "Add to campaign" }).click();
    await page.getByRole("button", { name: "Request formal estimate" }).click();
    await expect(page.getByLabel("Campaign dates").getByText("Select campaign start and end dates before requesting a formal estimate.")).toBeVisible();
    await fillCampaignDates(page, "2026-08-01", "2026-08-31");
    await page.getByRole("button", { name: "Request formal estimate" }).click();
    const dialog = page.getByRole("dialog", { name: "Create campaign proposal" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Submit proposal" })).toBeVisible();
    await dialog.getByRole("button", { name: "Close" }).click();
  }
});

test("internal inventory thumbnail opens the reusable viewer and restores focus", async ({ page }) => {
  await seedAdmin(page);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1/", "");
    if (path === "users/auth/me/") return route.fulfill({ contentType: "application/json", body: JSON.stringify(admin) });
    if (path === "observability/operational-mode/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    if (path.startsWith("inventory/sites/all-sites/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }) });
    if (path.startsWith("inventory/units/all-units/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify({ count: 1, next: null, previous: null, results: [{ id: 7, public_id: "62807432-5e10-441f-a0e1-089cf5f42bb8", unit_code: "JMU-001-A", location_id: 2, location_name: "Central Junction", location_code: "JMU-001", city: "Jammu", address: "Central Road", location_type: "billboard", face_count: 1, width: "20.00", height: "10.00", status: "available", is_illuminated: true, monthly_rate: "50000.00", facing_direction: "North", site_type: "single_side", is_publicly_listed: true, thumbnail_url: pixel, image_count: 2, created_at: "2026-01-01", updated_at: "2026-01-01" }] }) });
    if (path === "inventory/units/7/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ id: 7, public_id: "62807432-5e10-441f-a0e1-089cf5f42bb8", site: 2, unit_code: "JMU-001-A", face_count: 1, width: "20.00", height: "10.00", status: "available", is_illuminated: true, monthly_rate: "50000.00", facing_direction: "North", site_type: "single_side", is_publicly_listed: true, public_description: "", public_features: [], primary_image: { id: 1, image_url: pixel, caption: "Main face", is_primary: true, uploaded_by: 1, uploaded_at: "2026-01-01", created_at: "2026-01-01", updated_at: "2026-01-01" }, image_gallery: [{ id: 1, image_url: pixel, caption: "Main face", is_primary: true, uploaded_by: 1, uploaded_at: "2026-01-01", created_at: "2026-01-01", updated_at: "2026-01-01" }, { id: 2, image_url: pixel, caption: "Street view", is_primary: false, uploaded_by: 1, uploaded_at: "2026-01-01", created_at: "2026-01-01", updated_at: "2026-01-01" }], created_at: "2026-01-01", updated_at: "2026-01-01" }) });
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });
  await page.goto("/inventory?view=units");
  const thumbnail = page.getByRole("button", { name: "View photos for advertising unit JMU-001-A" });
  await thumbnail.click();
  await expect(page.getByRole("dialog", { name: "JMU-001-A" })).toBeVisible();
  await expect(page.getByText("1 of 2")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(thumbnail).toBeFocused();
});

test("admin generates a one-time secure planner link and sees submitted proposals", async ({ page }) => {
  await seedAdmin(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async () => undefined },
    });
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    if (path === "users/auth/me/") return route.fulfill({ contentType: "application/json", body: JSON.stringify(admin) });
    if (path === "observability/operational-mode/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    if (path === "planner/links/" && request.method() === "POST") {
      const body = request.postDataJSON() as Record<string, unknown>;
      expect(body).not.toHaveProperty("tenant");
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: 2, tenant: 1, tenant_name: "Alpha Outdoor", title: "Client Planner", client: null, client_name: "", allowed_cities: [], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 1, public_path: "/media-planner/one-time-secret", token: "one-time-secret" }) });
    }
    if (path === "planner/links/2/eligible-inventory/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ counts: { base_media_units: 2, tenant_scoped: 2, publicly_listed: 1, operational: 1, allowed_city: 1, date_available: 1, eligible: 1 }, excluded: { not_published: 1, city_not_allowed: 0, inactive: 0, unavailable_for_dates: 0, missing_public_information: 0 }, allowed_cities: [] }) });
    if (path === "planner/links/") return route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
    if (path.startsWith("planner/proposals/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: 4, reference: "PRP-001", client_name: "Acme India", campaign_name: "Summer Launch", brand_company: "Acme", requested_start_date: "2026-08-01", requested_end_date: "2026-08-31", contact_name: "Asha", contact_email: "asha@acme.test", contact_phone: "", billing_gstin: "", notes: "", status: "submitted", submitted_at: "2026-07-18T10:00:00Z", preliminary_subtotal: "0.00", selected_unit_count: 2, availability_conflict_count: 0, assigned_to_name: "Unassigned", estimate_number: null, converted_campaign_code: null, lines: [] }]) });
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });
  await page.goto("/sales/proposals");
  await expect(page.getByText("PRP-001")).toBeVisible();
  await expect(page.getByLabel("Select company")).toHaveCount(0);
  await expect(page.getByText("Company")).toBeVisible();
  await expect(page.getByText("Alpha Outdoor")).toBeVisible();
  await page.getByLabel("Link title").fill("Client Planner");
  const generateButton = page.getByRole("button", { name: "Generate secure link" });
  await generateButton.click();
  await expect(page.getByRole("button", { name: "Link generated" })).toBeVisible();
  await expect(page.locator(".planner-action-feedback")).toHaveText("Link generated");
  await expect(page.locator(".planner-generated-link input")).toHaveValue(/one-time-secret/);
  await expect(page.getByText("1 published eligible unit", { exact: true })).toHaveCount(2);
  await expect(page.getByText("not published")).toBeVisible();
  await expect(page.getByRole("button", { name: "Diagnostics" })).toHaveCount(0);
  await expect(page.getByText("The full token is shown once")).toBeVisible();
  await page.getByRole("button", { name: "Copy link" }).click();
  await expect(page.getByText("Link copied")).toBeVisible();
});

test("platform superadmin selects a tenant before generating a planner link", async ({ page }) => {
  await seedPlatformAdmin(page);
  let generated = false;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    if (path === "users/auth/me/") return route.fulfill({ contentType: "application/json", body: JSON.stringify(platformAdmin) });
    if (path === "observability/operational-mode/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    if (path === "team/roles/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ roles: [], tenants: [{ id: 2, name: "ESPA FEE", slug: "espa-fee" }], can_select_tenant: true }) });
    if (path === "planner/links/" && request.method() === "POST") {
      const body = request.postDataJSON() as Record<string, unknown>;
      expect(body.tenant).toBe(2);
      generated = true;
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: 8, tenant: 2, tenant_name: "ESPA FEE", title: "ESPA Planner", client: null, client_name: "", allowed_cities: ["Jammu"], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 1, public_path: "/media-planner/tenant-secret", token: "tenant-secret" }) });
    }
    if (path === "planner/links/8/eligible-inventory/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ counts: { base_media_units: 11, tenant_scoped: 11, publicly_listed: 11, operational: 11, allowed_city: 11, date_available: 11, eligible: 11 }, excluded: { not_published: 0, city_not_allowed: 0, inactive: 0, unavailable_for_dates: 0, missing_public_information: 0 }, allowed_cities: ["jammu"] }) });
    if (path.startsWith("planner/links/8/eligibility-diagnostics/")) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          service: { git_sha: "abc123def456", build_timestamp: "2026-07-18T07:00:00Z", environment: "production" },
          database: { engine: "postgresql", database_fingerprint: "a1b2c3d4e5f6a7b8", migration_status: { "inventory.0009_mediaunit_is_publicly_listed_and_more": true, "planner.0001_initial": true } },
          link: { id: 8, title: "ESPA Planner", tenant_id: 2, tenant_name: "ESPA FEE", active: true, revoked: false, expired: false, allowed_cities_type: "list", allowed_cities: ["Jammu"], pricing_mode: "hidden", expires_at: null, eligible_count: 11, published_count: 11, excluded_count: 0 },
          pipeline: { all_units: 11, tenant_units: 11, published_units: 11, active_units: 11, operational_units: 11, city_eligible_units: 11, link_restriction_units: 11, date_eligible_units: 11, serializer_eligible_units: 11, final_units: 11 },
          exclusions: { wrong_tenant: 0, unpublished: 0, inactive: 0, wrong_city: 0, parent_inactive: 0, retired: 0, maintenance: 0, missing_public_id: 0, date_unavailable: 0, other: 0 },
          sample_units: [{ code: "ESPA-001", tenant_id: 2, published: true, public_id_present: true, status: "available", city_raw: "Jammu", city_normalized: "jammu", parent_active: true, eligible: true, exclusion_reason: null }],
        }),
      });
    }
    if (path === "planner/links/") {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify(generated ? [{ id: 8, tenant: 2, tenant_name: "ESPA FEE", title: "ESPA Planner", client: null, client_name: "", allowed_cities: ["Jammu"], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 11 }] : []) });
    }
    if (path.startsWith("planner/proposals/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
    if (path.startsWith("public/media-planner/tenant-secret/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify(publicPayload(false)) });
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });

  await page.goto("/sales/proposals");
  const generateButton = page.getByRole("button", { name: "Generate secure link" });
  await expect(page.getByLabel("Select company")).toBeVisible();
  await expect(generateButton).toBeDisabled();
  await page.getByLabel("Select company").selectOption("2");
  await expect(generateButton).toBeEnabled();
  await page.getByLabel("Link title").fill("ESPA Planner");
  await generateButton.click();
  await expect(page.getByText("Company: ESPA FEE")).toBeVisible();
  await expect(page.getByText("11 published eligible units")).toBeVisible();
  await page.getByRole("button", { name: "Diagnostics" }).click();
  const diagnosticsModal = page.getByRole("dialog", { name: "Media planner eligibility diagnostics" });
  await expect(diagnosticsModal).toBeVisible();
  await expect(diagnosticsModal.locator("tbody td").filter({ hasText: "ESPA-001" }).first()).toBeVisible();
  await page.goto("/media-planner/tenant-secret");
  await expect(page.getByRole("heading", { name: "Acme Live Media Planner" })).toBeVisible();
  await expect(page.getByText("JMU-001-A")).toBeVisible();
});

test("recent planner links copy only active public URLs", async ({ page }) => {
  await seedPlatformAdmin(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (value: string) => localStorage.setItem("planner_link_clipboard", value),
      },
    });
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    if (path === "users/auth/me/") return route.fulfill({ contentType: "application/json", body: JSON.stringify(platformAdmin) });
    if (path === "observability/operational-mode/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    if (path === "team/roles/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ roles: [], tenants: [{ id: 2, name: "ESPA FEE", slug: "espa-fee" }], can_select_tenant: true }) });
    if (path === "planner/links/") {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([
          { id: 10, tenant: 2, tenant_name: "ESPA FEE", title: "Active Planner", client: null, client_name: "", allowed_cities: ["Jammu"], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 4, public_path: "/media-planner/active-secret", created_at: "2026-07-18T09:00:00Z", updated_at: "2026-07-18T09:00:00Z" },
          { id: 11, tenant: 2, tenant_name: "ESPA FEE", title: "Active Missing Url", client: null, client_name: "", allowed_cities: [], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 0, created_at: "2026-07-18T09:30:00Z", updated_at: "2026-07-18T09:30:00Z" },
          { id: 12, tenant: 2, tenant_name: "ESPA FEE", title: "Closed Planner", client: null, client_name: "", allowed_cities: [], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: "2026-07-18T10:00:00Z", is_available: false, eligible_unit_count: 0, public_path: "/media-planner/closed-secret", created_at: "2026-07-18T10:00:00Z", updated_at: "2026-07-18T10:00:00Z" },
          { id: 13, tenant: 2, tenant_name: "ESPA FEE", title: "Absolute Planner", client: null, client_name: "", allowed_cities: [], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: "2027-01-01T00:00:00Z", revoked_at: null, is_available: true, eligible_unit_count: 2, public_path: "https://planner.example.com/media-planner/absolute-secret", created_at: "2026-07-18T11:00:00Z", updated_at: "2026-07-18T11:00:00Z" },
          { id: 14, tenant: 2, tenant_name: "ESPA FEE", title: "Expired Planner", client: null, client_name: "", allowed_cities: [], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: "2026-01-01T00:00:00Z", revoked_at: null, is_available: true, eligible_unit_count: 1, public_path: "/media-planner/expired-secret", created_at: "2026-07-18T12:00:00Z", updated_at: "2026-07-18T12:00:00Z" },
        ]),
      });
    }
    if (path.startsWith("planner/links/10/eligibility-diagnostics/")) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          service: { git_sha: "abc123def456", build_timestamp: "2026-07-18T07:00:00Z", environment: "production" },
          database: { engine: "postgresql", database_fingerprint: "a1b2c3d4e5f6a7b8", migration_status: { "planner.0001_initial": true } },
          link: { id: 10, title: "Active Planner", tenant_id: 2, tenant_name: "ESPA FEE", active: true, revoked: false, expired: false, allowed_cities_type: "list", allowed_cities: ["Jammu"], pricing_mode: "hidden", expires_at: null, eligible_count: 11, published_count: 11, excluded_count: 0 },
          pipeline: { all_units: 11, tenant_units: 11, published_units: 11, active_units: 11, operational_units: 11, city_eligible_units: 11, link_restriction_units: 11, date_eligible_units: 11, serializer_eligible_units: 11, final_units: 11 },
          exclusions: { wrong_tenant: 0, unpublished: 0, inactive: 0, wrong_city: 0, parent_inactive: 0, retired: 0, maintenance: 0, missing_public_id: 0, date_unavailable: 0, other: 0 },
          sample_units: [],
        }),
      });
    }
    if (path.startsWith("planner/links/12/eligibility-diagnostics/")) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          service: { git_sha: "abc123def456", build_timestamp: "2026-07-18T07:00:00Z", environment: "production" },
          database: { engine: "postgresql", database_fingerprint: "a1b2c3d4e5f6a7b8", migration_status: { "planner.0001_initial": true } },
          link: { id: 12, title: "Closed Planner", tenant_id: 99, tenant_name: "OMMS Platform", active: false, revoked: true, expired: false, allowed_cities_type: "list", allowed_cities: ["Jammu"], pricing_mode: "hidden", expires_at: null, eligible_count: 0, published_count: 0, excluded_count: 11 },
          pipeline: { all_units: 11, tenant_units: 0, published_units: 0, active_units: 0, operational_units: 0, city_eligible_units: 0, link_restriction_units: 0, date_eligible_units: 0, serializer_eligible_units: 0, final_units: 0 },
          exclusions: { wrong_tenant: 11, unpublished: 0, inactive: 0, wrong_city: 0, parent_inactive: 0, retired: 0, maintenance: 0, missing_public_id: 0, date_unavailable: 0, other: 0 },
          sample_units: [],
        }),
      });
    }
    if (path.startsWith("planner/proposals/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });

  await page.goto("/sales/proposals");
  const table = page.getByRole("table", { name: "Recent planner links" });
  await expect(table).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Planner Link" })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Client / Company" })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Inventory" })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Status" })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Created / Expiry" })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Actions" })).toBeVisible();
  const activeRow = table.locator(".planner-link-row").filter({ hasText: "Active Planner" });
  const missingUrlRow = table.locator(".planner-link-row").filter({ hasText: "Active Missing Url" });
  const closedRow = table.locator(".planner-link-row").filter({ hasText: "Closed Planner" });
  const absoluteRow = table.locator(".planner-link-row").filter({ hasText: "Absolute Planner" });
  const expiredRow = table.locator(".planner-link-row").filter({ hasText: "Expired Planner" });
  const copyButton = activeRow.getByRole("button", { name: "Copy Live Media Planner link" });
  await expect(copyButton).toBeEnabled();
  await expect(copyButton).toHaveAttribute("type", "button");
  await expect(activeRow).toContainText("General client link");
  await expect(activeRow).toContainText("Rates hidden");
  await expect(activeRow).toContainText("ESPA FEE");
  await expect(activeRow).toContainText(/Eligible\s*11/);
  await expect(activeRow).toContainText(/Published\s*11/);
  await expect(activeRow).toContainText(/Excluded\s*0/);
  await expect(activeRow).toContainText("ACTIVE");
  await expect(activeRow).toContainText("No expiry");
  await expect(activeRow.locator(".planner-link-actions button").nth(0)).toHaveText("Copy Link");
  await expect(activeRow.locator(".planner-link-actions button").nth(1)).toHaveText("Diagnostics");
  await expect(activeRow.locator(".planner-link-actions button").nth(2)).toHaveText("Revoke");
  await copyButton.click();
  await expect(copyButton).toHaveText("Copied");
  await expect(activeRow.getByTestId("planner-copy-check-icon")).toBeVisible();
  await expect(page.getByText("Link copied")).toBeVisible();
  const expectedActiveUrl = new URL("/media-planner/active-secret", page.url()).toString();
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("planner_link_clipboard"))).toBe(expectedActiveUrl);
  await expect(copyButton).toHaveText("Copy Link", { timeout: 3000 });
  await expect(activeRow.getByTestId("planner-copy-check-icon")).toHaveCount(0);
  const absoluteCopyButton = absoluteRow.getByRole("button", { name: "Copy Live Media Planner link" });
  await absoluteCopyButton.click();
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("planner_link_clipboard"))).toBe("https://planner.example.com/media-planner/absolute-secret");
  const missingUrlCopyButton = missingUrlRow.getByRole("button", { name: "Copy Live Media Planner link" });
  await expect(missingUrlCopyButton).toBeEnabled();
  await missingUrlCopyButton.click();
  await expect(page.getByText("Unable to copy link. This planner link does not have a copyable public URL. Create a new planner link and try again.")).toBeVisible();
  await expect(closedRow.getByRole("button", { name: "Copy Live Media Planner link" })).toHaveCount(0);
  await expect(closedRow.getByRole("button", { name: "Revoke" })).toHaveCount(0);
  await expect(closedRow.getByRole("button", { name: "Diagnostics" })).toBeVisible();
  await expect(closedRow).toContainText("REVOKED");
  await expect(expiredRow.getByRole("button", { name: "Copy Live Media Planner link" })).toHaveCount(0);
  await expect(expiredRow).toContainText("EXPIRED");
  const warningRow = closedRow.locator("xpath=following-sibling::tr[1]");
  await expect(warningRow).toHaveClass(/planner-link-warning-row/);
  await expect(warningRow).toContainText("Planner tenant does not match published inventory.");

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(activeRow.getByText("Active Planner")).toBeVisible();
  await expect(activeRow.locator(".status-pill", { hasText: "ACTIVE" })).toBeVisible();
  await expect(activeRow.getByText("ESPA FEE")).toBeVisible();
  await expect(activeRow.getByText("Eligible")).toBeVisible();
  await expect(activeRow.getByText("Published")).toBeVisible();
  await expect(activeRow.getByText("Excluded")).toBeVisible();
  await expect(activeRow.getByRole("button", { name: "Copy Live Media Planner link" })).toBeVisible();
  await expect.poll(() =>
    page.locator(".planner-link-history").evaluate((element) => element.scrollWidth <= element.clientWidth + 1),
  ).toBeTruthy();
});

test("recent planner links use textarea fallback when clipboard API rejects", async ({ page }) => {
  await seedPlatformAdmin(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async () => { throw new Error("clipboard unavailable"); } },
    });
    document.execCommand = (command: string) => {
      if (command !== "copy") return false;
      const textarea = document.querySelector("textarea") as HTMLTextAreaElement | null;
      localStorage.setItem("planner_link_clipboard_fallback", textarea?.value || "");
      return true;
    };
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    if (path === "users/auth/me/") return route.fulfill({ contentType: "application/json", body: JSON.stringify(platformAdmin) });
    if (path === "observability/operational-mode/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    if (path === "team/roles/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ roles: [], tenants: [], can_select_tenant: true }) });
    if (path === "planner/links/") return route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: 30, tenant: 2, tenant_name: "ESPA FEE", title: "Fallback Planner", client: null, client_name: "", allowed_cities: [], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 1, public_path: "media-planner/fallback-secret", created_at: "2026-07-18T09:00:00Z", updated_at: "2026-07-18T09:00:00Z" }]) });
    if (path.startsWith("planner/proposals/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });

  await page.goto("/sales/proposals");
  const copyButton = page.getByRole("row", { name: /Fallback Planner/ }).getByRole("button", { name: "Copy Live Media Planner link" });
  await copyButton.click();
  await expect(copyButton).toHaveText("Copied");
  await expect(page.getByText("Link copied")).toBeVisible();
  const expectedUrl = new URL("/media-planner/fallback-secret", page.url()).toString();
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("planner_link_clipboard_fallback"))).toBe(expectedUrl);
});

test("recent planner link copy failure recovers with readable feedback", async ({ page }) => {
  await seedPlatformAdmin(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async () => { throw new Error("clipboard blocked"); } },
    });
    document.execCommand = () => false;
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    if (path === "users/auth/me/") return route.fulfill({ contentType: "application/json", body: JSON.stringify(platformAdmin) });
    if (path === "observability/operational-mode/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    if (path === "team/roles/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ roles: [], tenants: [], can_select_tenant: true }) });
    if (path === "planner/links/") return route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: 31, tenant: 2, tenant_name: "ESPA FEE", title: "Failure Planner", client: null, client_name: "", allowed_cities: [], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 1, public_path: "/media-planner/failure-secret", created_at: "2026-07-18T09:00:00Z", updated_at: "2026-07-18T09:00:00Z" }]) });
    if (path.startsWith("planner/proposals/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });

  await page.goto("/sales/proposals");
  const copyButton = page.getByRole("row", { name: /Failure Planner/ }).getByRole("button", { name: "Copy Live Media Planner link" });
  await copyButton.click();
  await expect(page.getByText("Unable to copy link. Please try again.")).toBeVisible();
  await expect(copyButton).toBeEnabled();
  await expect(copyButton).toHaveText("Copy Link");
});

test("platform superadmin opens planner diagnostics inside media proposals", async ({ page }) => {
  await seedPlatformAdmin(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (value: string) => localStorage.setItem("planner_diagnostics_clipboard", value) },
    });
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    if (path === "observability/operational-mode/") {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    }
    if (path === "planner/links/") {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: 7, title: "Live Media Planner", client: null, client_name: "", allowed_cities: ["Jammu"], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 1 }]) });
    }
    if (path.startsWith("planner/links/7/eligibility-diagnostics/")) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          service: { git_sha: "abc123def456", build_timestamp: "2026-07-18T07:00:00Z", environment: "production" },
          database: { engine: "postgresql", database_fingerprint: "a1b2c3d4e5f6a7b8", migration_status: { "inventory.0009_mediaunit_is_publicly_listed_and_more": true, "planner.0001_initial": true } },
          link: { id: 7, title: "Live Media Planner", tenant_id: 4, tenant_name: "ESPA FEE", active: true, revoked: false, expired: false, allowed_cities_type: "list", allowed_cities: ["Jammu"], pricing_mode: "hidden", expires_at: null, eligible_count: 1, published_count: 1, excluded_count: 1, unique_eligible_locations: 1, unique_excluded_locations: 1 },
          summary: { total_units_inspected: 2, total_publicly_listed: 1, total_eligible: 1, total_excluded: 1, unique_eligible_locations: 1, unique_excluded_locations: 1, eligible_detail_count: 1, excluded_detail_count: 1, detail_limit: 500 },
          pipeline: { all_units: 2, tenant_units: 2, published_units: 1, active_units: 1, operational_units: 1, city_eligible_units: 1, link_restriction_units: 1, date_eligible_units: 1, serializer_eligible_units: 1, final_units: 1 },
          exclusions: { wrong_tenant: 0, unpublished: 1, inactive: 0, wrong_city: 0, parent_inactive: 0, retired: 0, maintenance: 0, missing_public_id: 0, date_unavailable: 0, other: 0 },
          sample_units: [{ code: "ESPA-001", tenant_id: 4, published: true, public_id_present: true, status: "available", city_raw: "Jammu", city_normalized: "jammu", parent_active: true, eligible: true, exclusion_reason: null }],
          eligible_units: [{ id: 1, unit_id: 1, unit_code: "ESPA-001", code: "ESPA-001", title: "ESPA-001", location_id: 1, location_name: "SIDCO Chowk", location_code: "ESPA-SITE", city: "Jammu", region: "Jammu and Kashmir", inventory_type: "single_side", tenant_id: 4, tenant_name: "ESPA FEE", published: true, publicly_listed: true, status: "available", operational_status: "available", availability_status: "available", eligible: true, exclusion_reason: null, actual_value: "", required_value: "", exclusion_reasons: [] }],
          excluded_units: [{ id: 2, unit_id: 2, unit_code: "ESPA-002_1", code: "ESPA-002_1", title: "ESPA-002_1", location_id: 1, location_name: "SIDCO Chowk", location_code: "ESPA-SITE", city: "Jammu", region: "Jammu and Kashmir", inventory_type: "single_side", tenant_id: 4, tenant_name: "ESPA FEE", published: false, publicly_listed: false, status: "available", operational_status: "available", availability_status: "available", eligible: false, exclusion_reason: "unpublished", actual_value: "false", required_value: "true", exclusion_reasons: [{ reason: "unpublished", actual: "false", required: "true" }] }],
        }),
      });
    }
    if (path.startsWith("planner/proposals/")) {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });
  await page.goto("/sales/proposals");
  const table = page.getByRole("table", { name: "Recent planner links" });
  const linkRow = table.locator(".planner-link-row").filter({ hasText: "Live Media Planner" });
  await expect(linkRow).toContainText(/Eligible\s*1/);
  await expect(linkRow).toContainText(/Published\s*1/);
  await page.getByRole("button", { name: "Diagnostics" }).click();
  const diagnosticsModal = page.getByRole("dialog", { name: "Media planner eligibility diagnostics" });
  await expect(diagnosticsModal).toBeVisible();
  await expect(diagnosticsModal.getByText("1 eligible advertising unit across 1 location · 1 excluded")).toBeVisible();
  await expect(diagnosticsModal.locator("tbody td").filter({ hasText: "ESPA-002_1" }).first()).toBeVisible();
  await diagnosticsModal.getByLabel("Reason").selectOption("unpublished");
  await expect(diagnosticsModal.locator("tbody td").filter({ hasText: "ESPA-002_1" }).first()).toBeVisible();
  await diagnosticsModal.getByRole("tab", { name: "Eligible units" }).click();
  await expect(diagnosticsModal.locator("tbody td").filter({ hasText: "ESPA-001" }).first()).toBeVisible();
  await diagnosticsModal.getByRole("tab", { name: "Exclusion summary" }).click();
  await expect(page.getByText("final units")).toBeVisible();
  await expect(page.getByText("DATABASE_URL")).toHaveCount(0);
  await page.getByRole("button", { name: "Copy diagnostic report" }).click();
  await expect(page.getByText("Diagnostic report copied")).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("planner_diagnostics_clipboard"))).toContain("ESPA-001");
});

test("platform diagnostics warns on tenant mismatch and keeps modal open when copy fails", async ({ page }) => {
  await seedPlatformAdmin(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async () => { throw new Error("Denied"); } },
    });
    document.execCommand = () => false;
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    if (path === "observability/operational-mode/") {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    }
    if (path === "team/roles/") {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ roles: [], tenants: [{ id: 2, name: "ESPA FEE", slug: "espa-fee" }], can_select_tenant: true }) });
    }
    if (path === "planner/links/") {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: 9, tenant: 99, tenant_name: "OMMS Platform", title: "Wrong Tenant Planner", client: null, client_name: "", allowed_cities: ["Jammu"], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 0 }]) });
    }
    if (path.startsWith("planner/links/9/eligibility-diagnostics/")) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          service: { git_sha: "abc123def456", build_timestamp: "2026-07-18T07:00:00Z", environment: "production" },
          database: { engine: "postgresql", database_fingerprint: "a1b2c3d4e5f6a7b8", migration_status: { "inventory.0009_mediaunit_is_publicly_listed_and_more": true, "planner.0001_initial": true } },
          link: { id: 9, title: "Wrong Tenant Planner", tenant_id: 99, tenant_name: "OMMS Platform", active: true, revoked: false, expired: false, allowed_cities_type: "list", allowed_cities: ["Jammu"], pricing_mode: "hidden", expires_at: null, eligible_count: 0, published_count: 0, excluded_count: 11 },
          pipeline: { all_units: 11, tenant_units: 0, published_units: 0, active_units: 0, operational_units: 0, city_eligible_units: 0, link_restriction_units: 0, date_eligible_units: 0, serializer_eligible_units: 0, final_units: 0 },
          exclusions: { wrong_tenant: 11, unpublished: 0, inactive: 0, wrong_city: 0, parent_inactive: 0, retired: 0, maintenance: 0, missing_public_id: 0, date_unavailable: 0, other: 0 },
          sample_units: [{ code: "ESPA-001", tenant_id: 2, published: true, public_id_present: true, status: "available", city_raw: "Jammu", city_normalized: "jammu", parent_active: true, eligible: false, exclusion_reason: "wrong_tenant" }],
        }),
      });
    }
    if (path.startsWith("planner/proposals/")) {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });

  await page.goto("/sales/proposals");
  await expect(page.getByText("Planner tenant does not match published inventory.")).toBeVisible();
  await page.getByRole("button", { name: "Diagnostics" }).click();
  const modal = page.getByRole("dialog", { name: "Media planner eligibility diagnostics" });
  await expect(modal).toBeVisible();
  await expect(modal.getByText("Planner tenant does not match published inventory.")).toBeVisible();
  await page.getByRole("button", { name: "Copy diagnostic report" }).click();
  await expect(page.getByText("Unable to copy diagnostic report. Select the JSON and copy it manually.")).toBeVisible();
  await expect(modal).toBeVisible();
});

test("platform superadmin runs safe media planner diagnostics", async ({ page }) => {
  await seedPlatformAdmin(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async () => undefined },
    });
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/", "");
    if (path === "observability/operational-mode/") {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ mode: "normal", label: "Normal", message: "", is_write_blocking: false }) });
    }
    if (path === "planner/links/") {
      return route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: 7, title: "Live Media Planner", client: null, client_name: "", allowed_cities: ["Jammu"], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 1 }]) });
    }
    if (path.startsWith("platform/diagnostics/media-planner/")) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          service: { git_sha: "abc123def456", build_timestamp: "2026-07-18T07:00:00Z", environment: "production" },
          database: { engine: "postgresql", database_fingerprint: "a1b2c3d4e5f6a7b8", migration_status: { "inventory.0009_mediaunit_is_publicly_listed_and_more": true, "planner.0001_initial": true } },
          planner_link: { id: 7, title: "Live Media Planner", tenant_id: 4, tenant_name: "ESPA FEE", is_active: true, is_revoked: false, is_expired: false, allowed_cities_raw_type: "list", allowed_cities_safe_summary: ["Jammu"], allowed_cities_normalized: ["jammu"], pricing_mode: "hidden", expires_at: null, eligible_count: 1 },
          pipeline: { all_units: 3, tenant_units: 2, publicly_listed: 1, active_units: 1, operationally_eligible: 1, parent_location_eligible: 1, allowed_city_eligible: 1, allowed_region_eligible: 1, inventory_type_eligible: 1, link_restriction_eligible: 1, available_for_requested_dates: 1, date_eligible: 1, public_serializer_eligible: 1, final_serialized: 1 },
          exclusions: { unpublished: 1, inactive: 0, wrong_tenant: 1, wrong_city: 0, retired: 0, maintenance: 0, missing_public_id: 0, unavailable_for_dates: 0, other: 0 },
          units: [{ code: "ESPA-001", tenant_id: 4, published: true, public_id_present: true, status: "available", availability_status: "available", city_raw: "Jammu", city_normalized: "jammu", parent_active: true, eligible: true, exclusion_reason: null }],
        }),
      });
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });
  await page.goto("/platform/diagnostics/media-planner");
  await expect(page.getByRole("link", { name: "Media Planner Diagnostics" })).toHaveCount(0);
  await expect(page.getByText("Platform diagnostics.")).toBeVisible();
  await page.getByLabel("Planner link").selectOption("7");
  await page.getByLabel("Unit codes").fill("ESPA-001");
  await page.getByRole("button", { name: "Run diagnostics" }).click();
  await expect(page.getByText("Eligible units")).toBeVisible();
  await expect(page.getByText("a1b2c3d4e5f6a7b8")).toBeVisible();
  await expect(page.getByText("final serialized")).toBeVisible();
  await expect(page.getByText("ESPA-001")).toBeVisible();
  await expect(page.getByText("DATABASE_URL")).toHaveCount(0);
  await page.getByRole("button", { name: "Copy diagnostics JSON" }).click();
  await expect(page.getByText("Diagnostics JSON copied")).toBeVisible();
});
