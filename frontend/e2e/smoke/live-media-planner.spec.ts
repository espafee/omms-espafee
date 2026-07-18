import { expect, test, type Page } from "@playwright/test";

const pixel = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
const admin = { id: 1, email: "admin@example.com", username: "admin", role: "admin", is_company_admin: true };
const platformAdmin = { id: 2, email: "platform@example.com", username: "platform", role: "admin", is_platform_admin: true, is_superuser: true };

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

function publicPayload(showRates = false) {
  return {
    count: 1, next: null, previous: null,
    planner: { title: "Acme Live Media Planner", tenant_name: "Alpha Outdoor", client_name: "Acme India", contact_email: "sales@alpha.test", expires_at: "2027-01-01T00:00:00Z", show_rates: showRates, pricing_mode: showRates ? "standard_selling_rate" : "hidden", allow_proposal_submission: true, allow_image_download: false, client_rate_card_available: false },
    filters: { cities: ["Jammu"], locations: ["Central Junction"], formats: ["single_side"], facing_directions: ["North"], illumination: [{ value: "true", label: "Illuminated" }], availability_statuses: ["available"], rate_bounds: { min: showRates ? "50000.00" : null, max: showRates ? "50000.00" : null } },
    meta: { eligible_unit_count: 1, has_campaign_dates: false },
    results: [{ public_id: "62807432-5e10-441f-a0e1-089cf5f42bb8", unit_code: "JMU-001-A", location_name: "Central Junction", public_address: "Central Road", city: "Jammu", region: "Jammu and Kashmir", dimensions: { width: "20.00", height: "10.00" }, display_format: "single_side", facing_direction: "North", is_illuminated: true, availability: { status: "available", label: "Available", reason: "Available for selected dates", conflict_count: 0 }, description: "Premium arterial road visibility.", features: ["High visibility"], primary_photo: { url: pixel, caption: "Main face", is_primary: true }, photos: [{ url: pixel, caption: "Main face", is_primary: true }, { url: pixel, caption: "Street view", is_primary: false }], image_download_allowed: false, monthly_rate: showRates ? "50000.00" : null }],
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
  await page.route("**/api/v1/public/media-planner/demo-token/**", async (route) => {
    requests.push(route.request().url());
    if (route.request().method() === "POST") {
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
  await page.getByLabel("Start date").fill("2026-08-01");
  await page.getByLabel("End date").fill("2026-08-31");
  await expect.poll(() => requests.some((url) => url.includes("start_date=2026-08-01") && url.includes("end_date=2026-08-31"))).toBeTruthy();
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
  const dialog = page.getByRole("dialog", { name: "Create campaign proposal" });
  await dialog.getByLabel("Campaign name").fill("Summer Launch");
  await dialog.getByLabel("Contact name").fill("Asha Client");
  await dialog.getByLabel("Email").fill("asha@acme.test");
  await dialog.getByRole("button", { name: "Submit proposal" }).click();
  await expect(page.getByText("Reference PRP-DEMO123")).toBeVisible();
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
  await page.getByLabel("Start date").fill("2026-08-01");
  await page.getByLabel("End date").fill("2026-08-31");
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
    if (path === "planner/links/" && request.method() === "POST") return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: 2, title: "Client Planner", client: null, client_name: "", allowed_cities: [], allowed_regions: [], allowed_inventory_types: [], show_rates: false, pricing_mode: "hidden", effective_show_rates: false, allow_proposal_submission: true, allow_image_download: false, allow_map_data: false, expires_at: null, revoked_at: null, is_available: true, eligible_unit_count: 1, public_path: "/media-planner/one-time-secret", token: "one-time-secret" }) });
    if (path === "planner/links/2/eligible-inventory/") return route.fulfill({ contentType: "application/json", body: JSON.stringify({ counts: { base_media_units: 2, tenant_scoped: 2, publicly_listed: 1, operational: 1, allowed_city: 1, date_available: 1, eligible: 1 }, excluded: { not_published: 1, city_not_allowed: 0, inactive: 0, unavailable_for_dates: 0, missing_public_information: 0 }, allowed_cities: [] }) });
    if (path === "planner/links/") return route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
    if (path.startsWith("planner/proposals/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: 4, reference: "PRP-001", client_name: "Acme India", campaign_name: "Summer Launch", brand_company: "Acme", requested_start_date: "2026-08-01", requested_end_date: "2026-08-31", contact_name: "Asha", contact_email: "asha@acme.test", contact_phone: "", billing_gstin: "", notes: "", status: "submitted", submitted_at: "2026-07-18T10:00:00Z", preliminary_subtotal: "0.00", selected_unit_count: 2, availability_conflict_count: 0, assigned_to_name: "Unassigned", estimate_number: null, converted_campaign_code: null, lines: [] }]) });
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not mocked" }) });
  });
  await page.goto("/sales/proposals");
  await expect(page.getByText("PRP-001")).toBeVisible();
  await page.getByLabel("Link title").fill("Client Planner");
  const generateButton = page.getByRole("button", { name: "Generate secure link" });
  await generateButton.click();
  await expect(page.getByRole("button", { name: "Link generated" })).toBeVisible();
  await expect(page.locator(".planner-action-feedback")).toHaveText("Link generated");
  await expect(page.locator(".planner-generated-link input")).toHaveValue(/one-time-secret/);
  await expect(page.getByText("1 published eligible unit", { exact: true })).toHaveCount(2);
  await expect(page.getByText("not published")).toBeVisible();
  await expect(page.getByText("The full token is shown once")).toBeVisible();
  await page.getByRole("button", { name: "Copy link" }).click();
  await expect(page.getByText("Link copied")).toBeVisible();
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
