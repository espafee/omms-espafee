import { mkdirSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import { createRequire } from "node:module";

const root = path.resolve("/Users/macbook/Projects/OMMS");
const frontend = path.join(root, "frontend");
const outputDir = path.join(root, "docs", "training", "screenshots");
const baseURL = "http://127.0.0.1:3110";
const require = createRequire(path.join(frontend, "package.json"));
const { chromium } = require("playwright");

mkdirSync(outputDir, { recursive: true });

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function startServer() {
  const child = spawn("npm", ["run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3110"], {
    cwd: frontend,
    stdio: "ignore",
  });
  return child;
}

async function waitForServer() {
  for (let i = 0; i < 80; i += 1) {
    try {
      const response = await fetch(baseURL);
      if (response.status < 500) {
        return;
      }
    } catch {
      await wait(1000);
    }
  }
  throw new Error("Timed out waiting for frontend dev server.");
}

const systemHealth = {
  status: "healthy",
  api_status: "healthy",
  database: { ok: true, diagnostic_queries_ok: true },
  redis: { configured: true },
  celery: { enabled: true, broker_configured: true, eager: false, mode: "enabled", worker_ready: "unknown", beat_configured: true },
  recent_failed_requests: 1,
  recent_slow_requests: 2,
  recent_failed_background_jobs: 0,
  active_jobs: 1,
  last_successful_import: new Date().toISOString(),
  last_successful_export: new Date().toISOString(),
  signals: [],
  deployment: { environment_name: "production", git_commit: "training", app_version: "2026.05" },
  environment_mode: { mode: "normal", label: "Normal", message: "", is_write_blocking: false, updated_at: null, updated_by_email: null },
};

const operationsSummary = {
  poe: { total_poes: 42, suspicious_count: 3, outside_geofence_count: 2, missing_gps_count: 1, duplicate_replacement_count: 0, pending_review_count: 8, overdue_review_count: 2, trends_by_date: [], recent_suspicious: [] },
  poe_sla: {
    warning_count: 4,
    breach_count: 2,
    oldest_pending: { id: 101, captured_at: new Date().toISOString(), campaign: "SP Smart School Admission", age_hours: 53 },
    unassigned_count: 3,
    reviewer_workload: [{ reviewer: "ops@omms.local", pending: 7, approved: 12, rejected: 2, rework: 1, is_overloaded: false }],
    suspicious_unresolved_count: 3,
    thresholds: { pending_warning_hours: 24, pending_breach_hours: 48, suspicious_warning_hours: 12, suspicious_breach_hours: 24, reviewer_overload_threshold: 10 },
  },
  operational_heatmap: {
    summary: { total_activity: 31, busy_regions: 3, suspicious_regions: 1, delayed_regions: 1, hotspot_flag: true, plain_language: "Review suspicious activity areas first." },
    top_busy_region: { region: "Jammu, Jammu and Kashmir", city: "Jammu", state: "Jammu and Kashmir", total_uploads: 12, suspicious_count: 2, delayed_count: 1, pending_count: 4, intensity: 82 },
    top_suspicious_region: { region: "Jammu, Jammu and Kashmir", city: "Jammu", state: "Jammu and Kashmir", total_uploads: 12, suspicious_count: 2, delayed_count: 1, pending_count: 4, intensity: 82 },
    top_delayed_region: { region: "Delhi, Delhi", city: "Delhi", state: "Delhi", total_uploads: 8, suspicious_count: 1, delayed_count: 2, pending_count: 3, intensity: 74 },
    region_activity: [
      { region: "Jammu, Jammu and Kashmir", city: "Jammu", state: "Jammu and Kashmir", total_uploads: 12, suspicious_count: 2, delayed_count: 1, pending_count: 4, intensity: 82 },
      { region: "Delhi, Delhi", city: "Delhi", state: "Delhi", total_uploads: 8, suspicious_count: 1, delayed_count: 2, pending_count: 3, intensity: 74 },
    ],
    site_activity: [],
    campaign_regions: [{ region: "Jammu, Jammu and Kashmir", campaigns: 3, booked_sites: 9 }],
    reviewer_load: [{ reviewer: "ops@omms.local", reviewed: 12, pending: 7, suspicious: 2 }],
    upload_trend: [{ day: "2026-05-20", uploads: 12, suspicious: 2, delayed: 1 }],
    operational_activity: { poe_uploads: 20, suspicious_poes: 3, delayed_reviews: 3, campaign_bookings: 4, alerts: 1, jobs: 0 },
    alert_density: [],
    job_density: [],
    filters_applied: {},
  },
  kpis: {
    active_jobs: 1,
    failed_jobs: 1,
    suspicious_poes: 3,
    pending_poe_reviews: 8,
    poe_sla_warnings: 4,
    poe_sla_breaches: 2,
    notifications_today: 6,
    failed_requests: 1,
    active_users_today: 9,
    campaigns_running: 12,
    campaigns_ending_soon: 3,
    campaigns_poe_risk: 2,
    campaigns_billing_risk: 1,
    critical_campaigns: 1,
    invoice_collection_rate: 78,
    overdue_invoices: 4,
    overdue_invoice_value: "165000",
    export_activity_today: 5,
  },
  billing_intelligence: {
    overdue_invoice_count: 4,
    overdue_amount: "165000",
    collection_efficiency_percentage: 78,
    overdue_age_buckets: [{ bucket: "8-15", label: "8-15 days", count: 2, amount: "85000" }],
    payment_trend: [{ day: "2026-05-20", amount: "120000", payments: 3 }],
    top_overdue_clients: [{ client: "Northline Media", count: 2, amount: "85000", oldest_days_overdue: 14 }],
  },
  campaign_performance: {
    summary: { active_campaigns: 12, ending_soon_count: 3, poe_risk_count: 2, billing_risk_count: 1, critical_count: 1 },
    campaigns: [{
      campaign_id: 1,
      campaign_code: "SPADM-001",
      campaign_name: "SP Smart School Admission",
      client_name: "SP Smart",
      risk_status: "poe_risk",
      poe_completion_percentage: 72,
      booked_sites_count: 18,
      sites_with_approved_poe: 13,
      pending_poe_count: 3,
      suspicious_poe_count: 2,
      billing_status: "invoice_issued",
      payment_completion_percentage: 65,
      overdue_amount: "85000",
    }],
    risk_distribution: [{ risk: "on_track", total: 9 }, { risk: "poe_risk", total: 2 }, { risk: "critical", total: 1 }],
    poe_completion_trend: [{ day: "2026-05-20", completion: 72 }],
    operational_health_trend: [{ day: "2026-05-20", healthy: 9, risk: 3 }],
  },
  charts: {
    import_export_trend: [{ day: "2026-05-20", imports: 2, exports: 5, failed: 1 }],
    request_trend: [{ day: "2026-05-20", total: 420, failed: 1, slow: 2 }],
    poe_status_distribution: [{ status: "approved", total: 34 }, { status: "suspicious", total: 3 }],
    poe_rejection_trend: [],
    billing_trend: [{ day: "2026-05-20", invoices: 4, paid: 3, overdue: 1 }],
    operations_activity: [{ day: "2026-05-20", total: 28 }],
    notification_volume: [{ notification_type: "system", total: 6 }],
    load_distribution: [{ entity_type: "poe", total: 18 }, { entity_type: "billing", total: 5 }],
    poe_reviewer_workload: [{ reviewer: "ops@omms.local", pending: 7 }],
    overdue_age_buckets: [{ bucket: "8-15", count: 2 }],
    payment_trend: [{ day: "2026-05-20", amount: "120000" }],
    campaign_risk_distribution: [{ risk: "on_track", total: 9 }, { risk: "poe_risk", total: 2 }],
    campaign_poe_completion_trend: [{ day: "2026-05-20", completion: 72 }],
    campaign_operational_health_trend: [{ day: "2026-05-20", healthy: 9, risk: 3 }],
  },
  timeline: [{ id: "evt-1", module: "POE", title: "Suspicious POE flagged", status: "warning", created_at: new Date().toISOString(), actor: "system" }],
  recent_critical_alerts: [],
  active_jobs: [{ id: 12, job_type: "export", resource_type: "inventory_sites", status: "processing", progress_percent: 45 }],
  system_health: systemHealth,
  warnings: [],
};

const dashboardProfile = {
  role: "admin",
  role_label: "Admin",
  active_widgets: ["operational_health", "critical_campaigns", "billing_risk", "alerts", "campaign_performance", "poe_sla", "collection_efficiency", "import_export_jobs", "assigned_work"],
  available_widgets: [],
  hidden_widgets: [],
  can_customize: true,
  can_view_finance: true,
  can_view_operations: true,
};

async function routeApi(page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const key = url.pathname.replace("/api/v1/", "");
    if (key === "users/auth/me/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ id: 1, email: "admin@vistaai.local", username: "admin", role: "admin" }) });
      return;
    }
    if (key === "observability/operations-summary/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(operationsSummary) });
      return;
    }
    if (key === "observability/dashboard-profile/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(dashboardProfile) });
      return;
    }
    if (key === "observability/audit-events/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ count: 1, results: [{ id: 1, event_type: "alert.triggered", entity_type: "alert_rule", entity_id: "1", severity: "warning", actor_email: null, summary: "POE SLA breach threshold crossed.", created_at: new Date().toISOString() }] }) });
      return;
    }
    if (key === "observability/diagnostics/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ system_health: systemHealth }) });
      return;
    }
    if (key === "campaigns/summary/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ total_campaigns: 18, active_campaigns: 12, draft_campaigns: 2, completed_campaigns: 4, total_budget: "1250000", active_budget: "860000", total_bookings: 42, live_bookings: 28, approved_assets: 34, ending_soon_count: 3, campaigns_at_risk: 3, campaigns_poe_risk: 2, campaigns_billing_risk: 1, critical_campaigns: 1 }) });
      return;
    }
    if (key === "bookings/summary/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ total_bookings: 42, pending_bookings: 5, confirmed_bookings: 28, live_bookings: 24, completed_bookings: 9, cancelled_bookings: 0, unique_media_units: 38, total_booked_value: "980000", live_booked_value: "720000" }) });
      return;
    }
    if (key === "billing/invoices/summary/") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ total_estimated: "1250000", total_approved_estimates: "980000", total_invoices: 14, draft_invoices: 2, issued_invoices: 8, due_soon_invoices: 2, overdue_invoices: 4, paid_invoices: 6, partially_paid_invoices: 3, payment_count: 11, total_invoiced: "980000", overdue_amount: "165000", total_paid: "765000", payments_received_this_month: "220000", total_collected: "765000", outstanding_amount: "215000", outstanding_balance: "215000", collection_efficiency_percentage: 78, average_days_to_payment: 9, overdue_age_buckets: [], top_overdue_clients: [], payment_trend: [] }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }) });
  });
}

async function captureWeb(page, route, name) {
  await routeApi(page);
  await page.addInitScript(() => {
    localStorage.setItem("omms_access_token", "training-token");
    localStorage.setItem("omms_user", JSON.stringify({ id: 1, email: "admin@vistaai.local", role: "admin", username: "admin" }));
  });
  await page.goto(`${baseURL}${route}`);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: false });
}

async function captureMobileMock(page, name, title, body) {
  await page.setViewportSize({ width: 420, height: 860 });
  await page.setContent(`
    <html><head><style>
      body{margin:0;background:#eef6f2;font-family:Inter,Arial,sans-serif;color:#0f172a;display:flex;align-items:center;justify-content:center;height:100vh}
      .phone{width:360px;height:780px;border-radius:38px;background:#f8fbf9;border:10px solid #0b2f24;box-shadow:0 24px 80px #0004;overflow:hidden;padding:24px;box-sizing:border-box}
      .logo{display:flex;gap:10px;align-items:center;color:#064e3b;font-weight:900}.mark{width:42px;height:42px;border-radius:14px;background:#dcfce7;display:grid;place-items:center}
      .eyebrow{margin-top:22px;color:#064e3b;font-size:12px;text-transform:uppercase;font-weight:900;letter-spacing:.08em}.title{font-size:28px;font-weight:900;margin:8px 0}
      .card{background:#fff;border:1px solid #d8e7df;border-radius:18px;padding:16px;margin-top:14px;box-shadow:0 14px 30px #0b3b2b17}
      .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kpi{background:#f6faf8;border:1px solid #dceae3;border-radius:14px;padding:12px}.kpi b{display:block;font-size:22px;color:#064e3b}.kpi span{font-size:11px;color:#4b635a;font-weight:800}
      .button{background:#064e3b;color:white;border-radius:14px;padding:14px;text-align:center;font-weight:900;margin-top:14px}.muted{color:#4b635a;line-height:1.45}.status{display:inline-block;border:1px solid #bbf7d0;background:#ecfdf5;color:#064e3b;border-radius:999px;padding:6px 10px;font-size:11px;font-weight:900;margin-top:8px}
    </style></head><body><div class="phone"><div class="logo"><div class="mark">V</div><span>VistaAi OMMS</span></div><p class="eyebrow">${title.eyebrow}</p><h1 class="title">${title.heading}</h1><p class="muted">${title.subheading}</p>${body}</div></body></html>`);
  await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: false });
}

let server;
try {
  server = startServer();
  await waitForServer();
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  await captureWeb(page, "/dashboard", "web-dashboard");
  await captureWeb(page, "/operations", "web-operations");
  await captureWeb(page, "/campaigns", "web-campaigns");
  await captureWeb(page, "/billing", "web-billing");
  await captureWeb(page, "/poe", "web-poe-review");
  await captureWeb(page, "/training", "web-training-center");

  await captureMobileMock(page, "mobile-login", { eyebrow: "Field operations console", heading: "OMMS Mobile", subheading: "Capture assigned work, GPS proof, and execution status from the field." }, `<div class="card"><b>Secure access</b><p class="muted">Use your OMMS account credentials.</p><div class="kpi"><span>Email</span><b style="font-size:16px">you@company.com</b></div><div class="kpi" style="margin-top:10px"><span>Password</span><b style="font-size:16px">••••••••</b></div><div class="button">Sign in</div></div>`);
  await captureMobileMock(page, "mobile-poe-upload", { eyebrow: "Field proof", heading: "Upload POE", subheading: "Assigned site details, photo proof, GPS readiness, and upload status in one flow." }, `<div class="card"><span class="status">GPS ready</span><span class="status">Photo ready</span><p class="muted">SP Smart School Admission · ESPA-001_1</p><div class="grid"><div class="kpi"><b>28.61</b><span>Latitude</span></div><div class="kpi"><b>77.20</b><span>Longitude</span></div></div><div class="button">Submit proof</div></div>`);
  await captureMobileMock(page, "mobile-admin-dashboard", { eyebrow: "Admin operations", heading: "Operations Dashboard", subheading: "High-level campaign, POE SLA, billing risk, and system status for owners." }, `<div class="card"><div class="grid"><div class="kpi"><b>12</b><span>Active campaigns</span></div><div class="kpi"><b>3</b><span>At risk</span></div><div class="kpi"><b>2</b><span>POE SLA breaches</span></div><div class="kpi"><b>78%</b><span>Collection</span></div></div><div class="button">Live · Refresh</div></div>`);

  await browser.close();
  writeFileSync(path.join(outputDir, "manifest.json"), JSON.stringify({ generated_at: new Date().toISOString() }, null, 2));
} finally {
  if (server) {
    server.kill("SIGTERM");
  }
}
