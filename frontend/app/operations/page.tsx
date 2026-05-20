"use client";

import Link from "next/link";
import { type ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { formatCurrency } from "@/lib/dashboard";
import { updateOperationalMode } from "@/lib/environment";
import {
  acknowledgeAlertEvent,
  confirmImportJob,
  createExportJob,
  downloadInventoryImportTemplate,
  fetchAlertRules,
  fetchAuditEvents,
  fetchDiagnostics,
  fetchExportJobs,
  fetchImportJob,
  fetchOperationsSummary,
  retryImportExportJob,
  updateAlertRule,
  type AlertRule,
  uploadInventorySiteImport,
  type AuditEvent,
  type DiagnosticsPayload,
  type ImportExportJob,
  type OperationsSummary,
} from "@/lib/observability";
import {
  createSavedOperationalView,
  deleteSavedOperationalView,
  fetchSavedOperationalViews,
  type SavedOperationalView,
} from "@/lib/operational-search";

type StoredUser = {
  email?: string;
  role?: string;
};

type ExportType = "inventory-sites" | "campaigns" | "poe-reports" | "invoices";

const INITIAL_FILTERS = {
  date_from: "",
  date_to: "",
  campaign: "",
  site: "",
  field_agent: "",
  client: "",
  company: "",
  module: "",
  role: "",
  notification_type: "",
  status: "",
  severity: "",
  event_type: "",
};

type OperationsFilters = typeof INITIAL_FILTERS;

const DASHBOARD_REFRESH_MS = 45_000;
const ACTIVE_JOB_REFRESH_MS = 5_000;
const LIVE_TICK_MS = 10_000;

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatRelativeRefresh(value: Date | null, now: number) {
  if (!value) {
    return "Waiting for first update";
  }
  const seconds = Math.max(0, Math.floor((now - value.getTime()) / 1000));
  if (seconds < 5) {
    return "Updated just now";
  }
  if (seconds < 60) {
    return `Updated ${seconds}s ago`;
  }
  return `Updated ${Math.floor(seconds / 60)}m ago`;
}

function formatHours(value: number) {
  if (value < 24) {
    return `${value}h`;
  }
  const days = Math.floor(value / 24);
  const hours = value % 24;
  return hours ? `${days}d ${hours}h` : `${days}d`;
}

function SimpleBar({ label, value, max }: { label: string; value: number; max: number }) {
  const width = max > 0 ? Math.max(4, Math.round((value / max) * 100)) : 4;
  return (
    <div className="module-stat">
      <p className="stat-label">{label}</p>
      <div className="progress-track">
        <span className="progress-fill" style={{ width: `${width}%` }} />
      </div>
      <p className="site-copy">{value}</p>
    </div>
  );
}

function KpiCard({ label, value, hint, href }: { label: string; value: string | number; hint?: string; href?: string }) {
  const content = (
    <article className="ops-kpi-card">
      <p className="stat-label">{label}</p>
      <strong>{value}</strong>
      {hint ? <span>{hint}</span> : null}
    </article>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}

function CompactBars({ rows, labelKey, valueKey }: { rows: Array<Record<string, unknown>>; labelKey: string; valueKey: string }) {
  const max = Math.max(1, ...rows.map((row) => Number(row[valueKey] ?? 0)));
  return (
    <div className="ops-bars">
      {rows.slice(-8).map((row, index) => {
        const value = Number(row[valueKey] ?? 0);
        const label = String(row[labelKey] ?? "-");
        return <SimpleBar key={`${label}-${index}`} label={label} value={value} max={max} />;
      })}
      {rows.length === 0 ? <p className="empty-state">No data for this filter.</p> : null}
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  return <span className={`ops-status-dot status-${status}`} aria-hidden="true" />;
}

function formatMetricLabel(value: string) {
  return value.replaceAll("_", " ");
}

function statusLabel(value?: string) {
  if (!value) {
    return "Unknown";
  }
  return value.replaceAll("_", " ");
}

export default function OperationsPage() {
  const router = useRouter();
  const loadInFlightRef = useRef(false);
  const [user, setUser] = useState<StoredUser | null>(null);
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsPayload | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [savedViews, setSavedViews] = useState<SavedOperationalView[]>([]);
  const [savedViewName, setSavedViewName] = useState("");
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [importJob, setImportJob] = useState<ImportExportJob | null>(null);
  const [exportJob, setExportJob] = useState<ImportExportJob | null>(null);
  const [exportJobs, setExportJobs] = useState<ImportExportJob[]>([]);
  const [exportType, setExportType] = useState<ExportType>("inventory-sites");
  const [exportStatusFilter, setExportStatusFilter] = useState("");
  const [isStartingExport, setIsStartingExport] = useState(false);
  const [isDownloadingTemplate, setIsDownloadingTemplate] = useState(false);
  const [savingAlertRule, setSavingAlertRule] = useState<number | null>(null);
  const [acknowledgingAlertId, setAcknowledgingAlertId] = useState<number | null>(null);
  const [isImportConfirmOpen, setIsImportConfirmOpen] = useState(false);
  const [isStartingImport, setIsStartingImport] = useState(false);
  const [retryingJobId, setRetryingJobId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loadWarnings, setLoadWarnings] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isLiveRefreshing, setIsLiveRefreshing] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [liveTick, setLiveTick] = useState(() => Date.now());
  const [isTabVisible, setIsTabVisible] = useState(true);
  const [modeDraft, setModeDraft] = useState("normal");
  const [modeMessageDraft, setModeMessageDraft] = useState("");
  const [isSavingMode, setIsSavingMode] = useState(false);

  const load = useCallback(
    async (nextFilters: OperationsFilters, options: { silent?: boolean } = {}) => {
      if (loadInFlightRef.current) {
        return;
      }
      loadInFlightRef.current = true;
      if (options.silent) {
        setIsLiveRefreshing(true);
      } else {
        setIsLoading(true);
      }
      setError("");
      setLoadWarnings([]);
      try {
        const profile = await fetchCurrentUser();
        setUser(profile);
        const [summaryResult, auditResult, exportResult, alertRuleResult, diagnosticsResult, savedViewsResult] = await Promise.allSettled([
          fetchOperationsSummary(nextFilters),
          fetchAuditEvents({ severity: nextFilters.severity, event_type: nextFilters.event_type }),
          fetchExportJobs(),
          fetchAlertRules(),
          profile.role === "admin" ? fetchDiagnostics() : Promise.resolve(null),
          fetchSavedOperationalViews({ view_type: "operations" }),
        ]);

        const warnings: string[] = [];
        if (summaryResult.status === "fulfilled") {
          setSummary(summaryResult.value);
          const environmentMode = summaryResult.value.system_health.environment_mode;
          if (environmentMode) {
            setModeDraft(environmentMode.mode);
            setModeMessageDraft(environmentMode.message ?? "");
          }
          if (summaryResult.value.warnings?.length) {
            warnings.push(...summaryResult.value.warnings);
          }
        } else {
          warnings.push("Operations summary is temporarily unavailable.");
        }
        if (auditResult.status === "fulfilled") {
          setAuditEvents(auditResult.value);
        } else {
          warnings.push("Audit timeline could not be refreshed.");
        }
        if (exportResult.status === "fulfilled") {
          setExportJobs(exportResult.value);
        } else {
          warnings.push("Import/export history could not be refreshed.");
        }
        if (alertRuleResult.status === "fulfilled") {
          setAlertRules(alertRuleResult.value);
        } else {
          warnings.push("Alert thresholds could not be refreshed.");
        }
        if (diagnosticsResult.status === "fulfilled") {
          setDiagnostics(diagnosticsResult.value);
        } else {
          setDiagnostics(null);
          if (profile.role === "admin") {
            warnings.push("Admin diagnostics could not be refreshed.");
          }
        }
        if (savedViewsResult.status === "fulfilled") {
          setSavedViews(savedViewsResult.value);
        } else {
          warnings.push("Saved views are temporarily unavailable.");
        }
        setLoadWarnings(warnings);
        const now = new Date();
        setLastUpdatedAt(now);
        setLiveTick(now.getTime());
      } catch (loadError) {
        const nextMessage = loadError instanceof Error ? loadError.message : "Unable to load operations intelligence.";
        if (!options.silent) {
          setError(nextMessage);
        }
        if (nextMessage.includes("sign in again")) {
          router.replace("/login");
        }
      } finally {
        loadInFlightRef.current = false;
        setIsLoading(false);
        setIsLiveRefreshing(false);
      }
    },
    [router],
  );

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
    }
    void load(INITIAL_FILTERS);
  }, [load, router]);

  const importSummary = importJob?.filters.summary ?? {};
  const importWarnings = importJob?.filters.warnings ?? [];
  const importRowsReady = (importSummary.rows_to_import ?? importJob?.rows_success ?? 0) > 0;
  const importCanStart = importJob?.status === "previewed" && importRowsReady;
  const importIsActive = importJob?.status === "confirmed" || importJob?.status === "processing";
  const exportIsActive = exportJobs.some((job) => job.status === "confirmed" || job.status === "processing");
  const activeExportJobs = exportJobs.filter((job) => job.status === "confirmed" || job.status === "processing");
  const latestCompletedExport = exportJobs.find((job) => job.status === "completed");
  const liveStatusLabel = isTabVisible ? "Live" : "Paused";

  useEffect(() => {
    if (!importJob || !importIsActive) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        setImportJob(await fetchImportJob(importJob.id));
      } catch {
        window.clearInterval(timer);
      }
    }, ACTIVE_JOB_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [importIsActive, importJob]);

  useEffect(() => {
    if (!exportIsActive) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const nextJobs = await fetchExportJobs();
        setExportJobs(nextJobs);
        setExportJob(nextJobs[0] ?? null);
      } catch {
        window.clearInterval(timer);
      }
    }, ACTIVE_JOB_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [exportIsActive]);

  useEffect(() => {
    const tick = window.setInterval(() => setLiveTick(Date.now()), LIVE_TICK_MS);
    return () => window.clearInterval(tick);
  }, []);

  useEffect(() => {
    function handleVisibilityChange() {
      setIsTabVisible(document.visibilityState === "visible");
    }
    handleVisibilityChange();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);

  useEffect(() => {
    if (!getAccessToken() || !isTabVisible) {
      return;
    }
    const timer = window.setInterval(() => {
      void load(filters, { silent: true });
    }, DASHBOARD_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [filters, isTabVisible, load]);

  function updateFilter(field: keyof typeof filters, value: string) {
    setFilters((current) => ({ ...current, [field]: value }));
  }

  async function handleSaveCurrentView() {
    const trimmedName = savedViewName.trim();
    if (!trimmedName) {
      setError("Name this saved view before saving it.");
      return;
    }
    setError("");
    setMessage("");
    try {
      const savedView = await createSavedOperationalView({
        name: trimmedName,
        view_type: "operations",
        module: filters.module || "operations",
        filters,
      });
      setSavedViews((current) => [savedView, ...current.filter((item) => item.id !== savedView.id && item.name !== savedView.name)]);
      setSavedViewName("");
      setMessage("Operational view saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save this operational view.");
    }
  }

  async function handleDeleteSavedView(id: number) {
    setError("");
    setMessage("");
    try {
      await deleteSavedOperationalView(id);
      setSavedViews((current) => current.filter((item) => item.id !== id));
      setMessage("Saved view removed.");
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to remove saved view.");
    }
  }

  function applySavedView(view: SavedOperationalView) {
    const nextFilters = { ...INITIAL_FILTERS, ...view.filters };
    setFilters(nextFilters);
    void load(nextFilters);
  }

  async function handleImportUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setMessage("");
    setError("");
    try {
      setImportJob(await uploadInventorySiteImport(file));
      setIsImportConfirmOpen(false);
      setMessage("Import preview is ready. No records have been imported yet.");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Unable to preview import file.");
    }
  }

  async function handleTemplateDownload() {
    setError("");
    setMessage("");
    setIsDownloadingTemplate(true);
    try {
      const blob = await downloadInventoryImportTemplate();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "OMMS_Inventory_Import_Template.xlsx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setMessage("Inventory import template downloaded.");
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Unable to download inventory import template.");
    } finally {
      setIsDownloadingTemplate(false);
    }
  }

  async function handleConfirmImport() {
    if (!importJob || !importCanStart) {
      return;
    }
    setIsStartingImport(true);
    setError("");
    setMessage("");
    try {
      const nextJob = await confirmImportJob(importJob.id);
      setImportJob(nextJob);
      setIsImportConfirmOpen(false);
      setMessage(nextJob.status === "completed" ? "Inventory import completed." : "Inventory import started.");
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : "Unable to start inventory import.");
    } finally {
      setIsStartingImport(false);
    }
  }

  async function handleExport() {
    setIsStartingExport(true);
    setError("");
    setMessage("");
    const exportFilters: Record<string, string> = {};
    if (exportStatusFilter) {
      exportFilters.status = exportStatusFilter;
    }
    if (filters.campaign) {
      exportFilters.campaign = filters.campaign;
    }
    if (filters.client) {
      exportFilters.client = filters.client;
    }
    try {
      const job = await createExportJob(exportType, exportFilters);
      const nextJobs = [job, ...exportJobs.filter((item) => item.id !== job.id)].slice(0, 8);
      setExportJob(job);
      setExportJobs(nextJobs);
      setMessage(job.status === "completed" ? "Export completed." : "Export queued.");
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Unable to start export.");
    } finally {
      setIsStartingExport(false);
    }
  }

  async function handleRetryJob(job: ImportExportJob) {
    if (job.status !== "failed") {
      return;
    }
    setRetryingJobId(job.id);
    setError("");
    setMessage("");
    try {
      const retryJob = await retryImportExportJob(job.id);
      if (retryJob.job_type === "import") {
        setImportJob(retryJob);
      } else {
        const nextJobs = [retryJob, ...exportJobs.filter((item) => item.id !== retryJob.id)].slice(0, 8);
        setExportJob(retryJob);
        setExportJobs(nextJobs);
      }
      setMessage(`Retry started for job #${job.id}.`);
      void load(filters, { silent: true });
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Unable to retry job.");
    } finally {
      setRetryingJobId(null);
    }
  }

  async function handleAlertRuleUpdate(rule: AlertRule, input: Partial<Pick<AlertRule, "threshold" | "is_enabled">>) {
    if (user?.role !== "admin") {
      return;
    }
    setSavingAlertRule(rule.id);
    setError("");
    setMessage("");
    try {
      const updated = await updateAlertRule(rule.id, input);
      setAlertRules((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("Alert threshold updated.");
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Unable to update alert threshold.");
    } finally {
      setSavingAlertRule(null);
    }
  }

  async function handleAcknowledgeAlert(alertId: number) {
    setError("");
    setMessage("");
    setAcknowledgingAlertId(alertId);
    try {
      await acknowledgeAlertEvent(alertId);
      setMessage("Alert acknowledged.");
      await load(filters);
    } catch (ackError) {
      setError(ackError instanceof Error ? ackError.message : "Unable to acknowledge alert.");
    } finally {
      setAcknowledgingAlertId(null);
    }
  }

  async function handleModeSave() {
    setError("");
    setMessage("");
    setIsSavingMode(true);
    try {
      await updateOperationalMode({ mode: modeDraft, message: modeMessageDraft });
      await load(filters, { silent: true });
      setMessage("Environment mode updated.");
    } catch (modeError) {
      setError(modeError instanceof Error ? modeError.message : "Unable to update environment mode.");
    } finally {
      setIsSavingMode(false);
    }
  }

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  const systemHealth = summary?.system_health;
  const deployment = systemHealth?.deployment;
  const healthSignals = systemHealth?.signals ?? [];

  return (
    <AppShell
      active="operations"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title="Operations intelligence"
      description="Monitor suspicious POE activity, audit events, request health, imports, exports, alerts, and platform diagnostics."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}
      {message ? <p className="success">{message}</p> : null}
      {loadWarnings.length ? <p className="warning">{loadWarnings.join(" ")}</p> : null}

      <section className="ops-live-strip" aria-label="Live operations refresh status">
        <div className="ops-live-status">
          <span className={`ops-live-dot ${isLiveRefreshing ? "is-refreshing" : ""} ${isTabVisible ? "" : "is-paused"}`} aria-hidden="true" />
          <div>
            <strong>{liveStatusLabel}</strong>
            <span>{formatRelativeRefresh(lastUpdatedAt, liveTick)} · refreshes every {DASHBOARD_REFRESH_MS / 1000}s</span>
          </div>
        </div>
        <div className="ops-live-meta">
          <span>{systemHealth?.active_jobs ?? 0} active job(s)</span>
          <span>{activeExportJobs.length} export running/queued</span>
          {isLiveRefreshing ? <span>Refreshing...</span> : null}
        </div>
      </section>

      <section className="module-card">
        <div className="module-head">
          <h2>Filters</h2>
          <button className="ghost" type="button" onClick={() => void load(filters)}>Apply filters</button>
        </div>
        <div className="site-form-grid">
          {(["date_from", "date_to", "company", "module", "role", "campaign", "site", "client", "field_agent", "status", "severity", "event_type", "notification_type"] as const).map((field) => (
            <div className="field" key={field}>
              <label htmlFor={`ops-${field}`}>{field.replaceAll("_", " ")}</label>
              <input
                id={`ops-${field}`}
                type={field.startsWith("date") ? "date" : "text"}
                value={filters[field]}
                onChange={(event) => updateFilter(field, event.target.value)}
                placeholder={field === "status" ? "pending / suspicious / verified" : ""}
              />
            </div>
          ))}
        </div>
        <div className="saved-views-panel">
          <div className="saved-view-save">
            <input
              aria-label="Saved view name"
              value={savedViewName}
              onChange={(event) => setSavedViewName(event.target.value)}
              placeholder="Save this view as..."
            />
            <button className="submit compact-action" type="button" onClick={handleSaveCurrentView}>
              Save view
            </button>
          </div>
          <div className="saved-view-list" aria-label="Saved operational views">
            {savedViews.slice(0, 6).map((view) => (
              <span className="saved-view-chip" key={view.id}>
                <button type="button" onClick={() => applySavedView(view)}>
                  {view.name}
                </button>
                <button aria-label={`Delete ${view.name}`} type="button" onClick={() => handleDeleteSavedView(view.id)}>
                  ×
                </button>
              </span>
            ))}
            {savedViews.length === 0 ? <span className="site-copy">No saved views yet.</span> : null}
          </div>
        </div>
      </section>

      <section className="summary-row" aria-label="Operations intelligence">
        <KpiCard label="Active jobs" value={isLoading ? "..." : summary?.kpis.active_jobs ?? 0} hint="imports / exports" />
        <KpiCard label="Failed jobs" value={isLoading ? "..." : summary?.kpis.failed_jobs ?? 0} hint="needs review" />
        <KpiCard label="Suspicious POEs" value={isLoading ? "..." : summary?.kpis.suspicious_poes ?? 0} href="/poe" />
        <KpiCard label="Pending POE reviews" value={isLoading ? "..." : summary?.kpis.pending_poe_reviews ?? 0} />
        <KpiCard label="POE SLA warnings" value={isLoading ? "..." : summary?.kpis.poe_sla_warnings ?? 0} hint="24h / 12h risk" href="/poe" />
        <KpiCard label="POE SLA breaches" value={isLoading ? "..." : summary?.kpis.poe_sla_breaches ?? 0} hint="needs escalation" href="/poe" />
        <KpiCard label="Notifications today" value={isLoading ? "..." : summary?.kpis.notifications_today ?? 0} href="/notifications" />
        <KpiCard label="Failed requests" value={isLoading ? "..." : summary?.kpis.failed_requests ?? 0} />
        <KpiCard label="Active users today" value={isLoading ? "..." : summary?.kpis.active_users_today ?? 0} />
        <KpiCard label="Campaigns running" value={isLoading ? "..." : summary?.kpis.campaigns_running ?? 0} href="/campaigns" />
        <KpiCard label="Ending soon" value={isLoading ? "..." : summary?.kpis.campaigns_ending_soon ?? 0} hint="campaigns" href="/campaigns" />
        <KpiCard label="Campaign POE risk" value={isLoading ? "..." : summary?.kpis.campaigns_poe_risk ?? 0} href="/campaigns" />
        <KpiCard label="Campaign billing risk" value={isLoading ? "..." : summary?.kpis.campaigns_billing_risk ?? 0} href="/campaigns" />
        <KpiCard label="Critical campaigns" value={isLoading ? "..." : summary?.kpis.critical_campaigns ?? 0} hint="escalate" href="/campaigns" />
        <KpiCard label="Collection status" value={isLoading ? "..." : `${summary?.kpis.invoice_collection_rate ?? 0}%`} href="/billing" />
        <KpiCard label="Overdue invoices" value={isLoading ? "..." : summary?.kpis.overdue_invoices ?? 0} hint="billing risk" href="/billing" />
        <KpiCard label="Overdue value" value={isLoading ? "..." : formatCurrency(summary?.kpis.overdue_invoice_value ?? "0.00")} href="/billing" />
        <KpiCard label="Exports today" value={isLoading ? "..." : summary?.kpis.export_activity_today ?? 0} />
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Campaign performance</h2>
            <Link href="/campaigns">Open campaigns</Link>
          </div>
          <div className="asset-list compact-feed">
            {(summary?.campaign_performance.campaigns ?? []).slice(0, 6).map((campaign) => (
              <article className="asset-card" key={campaign.campaign_id}>
                <div className="asset-head">
                  <div>
                    <p className="site-code">{campaign.campaign_code}</p>
                    <h3>{campaign.campaign_name}</h3>
                  </div>
                  <span className={`status-pill status-${campaign.risk_status}`}>{campaign.risk_status.replaceAll("_", " ")}</span>
                </div>
                <p className="site-copy">
                  POE {campaign.poe_completion_percentage}% · {campaign.sites_with_approved_poe}/{campaign.booked_sites_count} approved · {campaign.pending_poe_count} pending · {campaign.suspicious_poe_count} suspicious
                </p>
                {summary?.campaign_performance.can_view_billing ? (
                  <p className="site-copy">
                    Billing {campaign.billing_status.replaceAll("_", " ")} · payment {campaign.payment_completion_percentage}% · overdue {formatCurrency(campaign.overdue_amount)}
                  </p>
                ) : null}
              </article>
            ))}
            {(summary?.campaign_performance.campaigns ?? []).length === 0 ? <p className="empty-state">No campaign performance risk for this view.</p> : null}
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Campaign risk mix</h2>
            <span>Classification</span>
          </div>
          <CompactBars rows={summary?.charts.campaign_risk_distribution ?? []} labelKey="risk" valueKey="total" />
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>POE completion trend</h2>
            <span>Campaigns</span>
          </div>
          <CompactBars rows={summary?.charts.campaign_poe_completion_trend ?? []} labelKey="campaign" valueKey="completion" />
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Operational health trend</h2>
            <span>Delay indicators</span>
          </div>
          <CompactBars rows={summary?.charts.campaign_operational_health_trend ?? []} labelKey="campaign" valueKey="indicators" />
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Import / export activity</h2>
            <span>Daily jobs</span>
          </div>
          <CompactBars rows={summary?.charts.job_activity ?? []} labelKey="day" valueKey="exports" />
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Request analytics</h2>
            <span>Volume / failures</span>
          </div>
          <CompactBars rows={summary?.charts.request_activity ?? []} labelKey="day" valueKey="failed" />
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>POE intelligence</h2>
            <Link href="/poe">Open POE review</Link>
          </div>
          <CompactBars rows={summary?.charts.poe_status ?? []} labelKey="verification_status" valueKey="total" />
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Reviewer workload</h2>
            <span>POE reviews</span>
          </div>
          <CompactBars rows={summary?.charts.poe_reviewer_workload ?? []} labelKey="reviewer" valueKey="pending" />
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>POE SLA risk</h2>
            <span>Review deadlines</span>
          </div>
          <div className="ops-health-grid">
            <div><p className="stat-label">Warnings</p><strong>{summary?.poe_sla.warning_count ?? 0}</strong></div>
            <div><p className="stat-label">Breaches</p><strong>{summary?.poe_sla.breach_count ?? 0}</strong></div>
            <div><p className="stat-label">Unassigned</p><strong>{summary?.poe_sla.unassigned_count ?? 0}</strong></div>
            <div><p className="stat-label">Suspicious unresolved</p><strong>{summary?.poe_sla.suspicious_unresolved_count ?? 0}</strong></div>
            <div>
              <p className="stat-label">Oldest pending</p>
              <strong>{summary?.poe_sla.oldest_pending ? formatHours(summary.poe_sla.oldest_pending.age_hours) : "-"}</strong>
              {summary?.poe_sla.oldest_pending ? <span className="site-copy">{summary.poe_sla.oldest_pending.campaign}</span> : null}
            </div>
            <div>
              <p className="stat-label">SLA rules</p>
              <strong>{summary?.poe_sla.thresholds.pending_warning_hours ?? 24}h / {summary?.poe_sla.thresholds.pending_breach_hours ?? 48}h</strong>
              <span className="site-copy">Pending warning / breach</span>
            </div>
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Reviewer balance</h2>
            <span>Pending / outcomes</span>
          </div>
          <div className="ops-bars">
            {(summary?.poe_sla.reviewer_workload ?? []).map((row) => (
              <div className="module-stat" key={row.reviewer}>
                <p className="stat-label">{row.reviewer}</p>
                <div className="progress-track">
                  <span
                    className="progress-fill"
                    style={{
                      width: `${Math.max(
                        4,
                        Math.min(100, Math.round((row.pending / Math.max(1, summary?.poe_sla.thresholds.reviewer_overload_threshold ?? 10)) * 100)),
                      )}%`,
                    }}
                  />
                </div>
                <p className="site-copy">
                  {row.pending} pending · {row.approved} approved · {row.rejected} rejected · {row.rework} rework
                  {row.is_overloaded ? " · overloaded" : ""}
                </p>
              </div>
            ))}
            {(summary?.poe_sla.reviewer_workload ?? []).length === 0 ? <p className="empty-state">No reviewer load for this filter.</p> : null}
          </div>
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Billing analytics</h2>
            <Link href="/billing">Open billing</Link>
          </div>
          <CompactBars rows={summary?.billing_intelligence.payment_trend ?? []} labelKey="day" valueKey="amount" />
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Billing risk</h2>
            <span>Receivables</span>
          </div>
          <div className="ops-health-grid">
            <div><p className="stat-label">Invoiced</p><strong>{formatCurrency(summary?.billing_intelligence.total_invoiced_amount ?? "0.00")}</strong></div>
            <div><p className="stat-label">Collected</p><strong>{formatCurrency(summary?.billing_intelligence.collected_amount ?? "0.00")}</strong></div>
            <div><p className="stat-label">Pending</p><strong>{formatCurrency(summary?.billing_intelligence.pending_amount ?? "0.00")}</strong></div>
            <div><p className="stat-label">Overdue</p><strong>{formatCurrency(summary?.billing_intelligence.overdue_amount ?? "0.00")}</strong></div>
            <div><p className="stat-label">Efficiency</p><strong>{summary?.billing_intelligence.collection_efficiency_percentage ?? 0}%</strong></div>
            <div><p className="stat-label">Avg payment delay</p><strong>{summary?.billing_intelligence.average_days_to_payment ?? "-"}d</strong></div>
          </div>
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Overdue age buckets</h2>
            <span>Invoice value</span>
          </div>
          <CompactBars rows={summary?.billing_intelligence.overdue_age_buckets ?? []} labelKey="label" valueKey="amount" />
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Top overdue clients</h2>
            <span>Largest exposure</span>
          </div>
          <div className="asset-list compact-feed">
            {(summary?.billing_intelligence.top_overdue_clients ?? []).map((client) => (
              <article className="asset-card" key={client.client}>
                <div className="asset-head">
                  <div>
                    <p className="site-code">{client.count} overdue invoice(s)</p>
                    <h3>{client.client}</h3>
                  </div>
                  <span className="status-pill status-overdue">{client.oldest_days_overdue}d</span>
                </div>
                <p className="site-copy">{formatCurrency(client.amount)} overdue</p>
              </article>
            ))}
            {(summary?.billing_intelligence.top_overdue_clients ?? []).length === 0 ? <p className="empty-state">No overdue client exposure for this view.</p> : null}
          </div>
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Operational load</h2>
            <span>Audit distribution</span>
          </div>
          <CompactBars rows={summary?.charts.load_distribution ?? []} labelKey="entity_type" valueKey="total" />
        </article>

        <article className="module-card">
          <div className="module-head">
            <div>
              <h2>System status</h2>
              <p className="site-copy">Environment {deployment?.environment_name || "unknown"}</p>
            </div>
            <span className={`status-pill status-${systemHealth?.status ?? "unknown"}`}>
              {statusLabel(systemHealth?.status)}
            </span>
          </div>
          <div className="ops-health-grid">
            <div><p className="stat-label">API</p><strong>{statusLabel(systemHealth?.api_status)}</strong></div>
            <div><p className="stat-label">Database</p><strong>{systemHealth?.database?.ok ? "Connected" : "Degraded"}</strong></div>
            <div><p className="stat-label">Mode</p><strong>{systemHealth?.environment_mode?.label ?? "Normal"}</strong><span className="site-copy">{systemHealth?.environment_mode?.is_write_blocking ? "Writes blocked" : "Writes enabled"}</span></div>
            <div><p className="stat-label">Redis</p><strong>{systemHealth?.redis?.configured ? "Configured" : "Not configured"}</strong></div>
            <div><p className="stat-label">Celery</p><strong>{systemHealth?.celery?.mode ?? "..."}</strong><span className="site-copy">{systemHealth?.celery?.worker_ready ?? "unknown"} worker</span></div>
            <div><p className="stat-label">Failed jobs</p><strong>{systemHealth?.recent_failed_background_jobs ?? 0}</strong></div>
            <div><p className="stat-label">Failed requests</p><strong>{systemHealth?.recent_failed_requests ?? 0}</strong></div>
            <div><p className="stat-label">Slow requests</p><strong>{systemHealth?.recent_slow_requests ?? 0}</strong></div>
            <div><p className="stat-label">API failures</p><strong>{systemHealth?.api_failure_percentage ?? 0}%</strong></div>
            <div><p className="stat-label">Retries due</p><strong>{systemHealth?.notification_retries_due ?? 0}</strong></div>
            <div><p className="stat-label">Last import</p><strong>{systemHealth?.last_successful_import ? formatDateTime(systemHealth.last_successful_import) : "-"}</strong></div>
            <div><p className="stat-label">Last export</p><strong>{systemHealth?.last_successful_export ? formatDateTime(systemHealth.last_successful_export) : "-"}</strong></div>
            <div><p className="stat-label">Build</p><strong>{deployment?.git_commit || deployment?.app_version || "-"}</strong></div>
          </div>
          {healthSignals.length ? (
            <p className="site-copy">Signals: {healthSignals.map(statusLabel).join(", ")}</p>
          ) : null}
          {user?.role === "admin" ? (
            <div className="ops-mode-controls">
              <label className="field">
                <span>Environment mode</span>
                <select value={modeDraft} onChange={(event) => setModeDraft(event.target.value)} disabled={isSavingMode}>
                  <option value="normal">Normal</option>
                  <option value="maintenance">Maintenance</option>
                  <option value="degraded">Degraded</option>
                  <option value="read_only">Read only</option>
                </select>
              </label>
              <label className="field">
                <span>Message</span>
                <input
                  value={modeMessageDraft}
                  onChange={(event) => setModeMessageDraft(event.target.value)}
                  placeholder="Optional user-facing status note"
                  disabled={isSavingMode}
                />
              </label>
              <button className="ghost" type="button" onClick={handleModeSave} disabled={isSavingMode}>
                {isSavingMode ? "Saving..." : "Update mode"}
              </button>
            </div>
          ) : null}
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Recent critical alerts</h2>
            <span>{summary?.recent_critical_alerts.length ?? 0}</span>
          </div>
          <div className="asset-list compact-feed">
            {(summary?.recent_critical_alerts ?? []).map((alert) => {
              const isAcknowledged = Boolean(alert.acknowledged_at);
              return (
              <article className={`asset-card alert-event-card ${isAcknowledged ? "is-acknowledged" : ""}`} key={alert.id}>
                <div className="asset-head">
                  <div>
                    <p className="site-code">{alert.metric}</p>
                    <h3>{alert.summary}</h3>
                    <p className="site-copy">{formatDateTime(alert.created_at)}</p>
                    {isAcknowledged ? (
                      <p className="site-copy">Acknowledged {formatDateTime(alert.acknowledged_at as string)} by {alert.acknowledged_by__email ?? "operations"}</p>
                    ) : null}
                  </div>
                  <div className="alert-event-actions">
                    <span className={`status-pill status-${alert.severity}`}>{alert.severity}</span>
                    <button
                      className="secondary-button compact"
                      type="button"
                      disabled={isAcknowledged || acknowledgingAlertId === alert.id}
                      onClick={() => void handleAcknowledgeAlert(alert.id)}
                    >
                      {isAcknowledged ? "Acknowledged" : acknowledgingAlertId === alert.id ? "Saving..." : "Acknowledge"}
                    </button>
                  </div>
                </div>
              </article>
              );
            })}
            {summary && summary.recent_critical_alerts.length === 0 ? <p className="empty-state">No critical alerts right now.</p> : null}
          </div>
        </article>
      </section>

      <section className="module-card">
        <div className="module-head">
          <h2>Alert thresholds</h2>
          <span>{alertRules.filter((rule) => rule.is_enabled).length} active</span>
        </div>
        <div className="alert-threshold-grid">
          {alertRules.map((rule) => {
            const breached = rule.current_value >= rule.threshold;
            const canEdit = user?.role === "admin";
            return (
              <article className="alert-threshold-card" key={rule.id}>
                <div>
                  <p className="site-code">{formatMetricLabel(rule.metric)}</p>
                  <h3>{rule.name}</h3>
                  <p className="site-copy">{rule.current_value} current / {rule.threshold} threshold | {rule.window_minutes} min window</p>
                  <p className="site-copy">Last triggered: {rule.last_triggered_at ? formatDateTime(rule.last_triggered_at) : "Never"}</p>
                  <p className="site-copy">Cooldown: {rule.cooldown_remaining_minutes > 0 ? `${rule.cooldown_remaining_minutes} min remaining` : `${rule.cooldown_minutes} min window`}</p>
                </div>
                <div className="alert-threshold-controls">
                  <span className={`status-pill status-${breached ? rule.severity : "completed"}`}>{breached ? "breached" : "normal"}</span>
                  <label className="filter-toggle">
                    <input
                      type="checkbox"
                      checked={rule.is_enabled}
                      disabled={!canEdit || savingAlertRule === rule.id}
                      onChange={(event) => void handleAlertRuleUpdate(rule, { is_enabled: event.target.checked })}
                    />
                    <span className="filter-toggle-control" />
                    <span className="filter-toggle-copy">
                      <strong>{rule.is_enabled ? "Enabled" : "Disabled"}</strong>
                      <small>{canEdit ? "Alerting" : "Admin only"}</small>
                    </span>
                  </label>
                  <div className="field">
                    <label htmlFor={`alert-threshold-${rule.id}`}>Threshold</label>
                    <input
                      id={`alert-threshold-${rule.id}`}
                      type="number"
                      min="1"
                      value={rule.threshold}
                      disabled={!canEdit || savingAlertRule === rule.id}
                      onChange={(event) => {
                        const nextValue = Number(event.target.value);
                        if (Number.isInteger(nextValue) && nextValue > 0) {
                          setAlertRules((current) => current.map((item) => (item.id === rule.id ? { ...item, threshold: nextValue } : item)));
                        }
                      }}
                      onBlur={(event) => {
                        const nextValue = Number(event.target.value);
                        if (Number.isInteger(nextValue) && nextValue > 0) {
                          void handleAlertRuleUpdate(rule, { threshold: nextValue });
                        }
                      }}
                    />
                  </div>
                </div>
              </article>
            );
          })}
          {!isLoading && alertRules.length === 0 ? <p className="empty-state">Alert thresholds will appear after alert rules are seeded.</p> : null}
        </div>
      </section>

      <section className="module-card">
        <div className="module-head">
          <h2>Import / export workbench</h2>
          <span>Staged CSV / Excel</span>
        </div>
        <div className="ops-active-job-grid" aria-label="Active background job monitoring">
          <article>
            <p className="stat-label">Import queue</p>
            <strong>{importIsActive ? importJob?.status.replaceAll("_", " ") : "No active import"}</strong>
            <span>{importJob ? `Job #${importJob.id} · ${importJob.progress_percent}%` : "Upload a file to stage an import"}</span>
          </article>
          <article>
            <p className="stat-label">Export queue</p>
            <strong>{activeExportJobs.length} active</strong>
            <span>{activeExportJobs[0] ? `Job #${activeExportJobs[0].id} · ${activeExportJobs[0].progress_percent}%` : "No queued export jobs"}</span>
          </article>
          <article>
            <p className="stat-label">Last completed export</p>
            <strong>{latestCompletedExport ? latestCompletedExport.resource_type.replaceAll("_", " ") : "-"}</strong>
            <span>{latestCompletedExport ? formatDateTime(latestCompletedExport.updated_at) : "No completed export in recent history"}</span>
          </article>
        </div>
        <div className="import-workbench">
          <div className="import-upload-panel">
            <div className="field">
              <label htmlFor="site-import">Inventory import file</label>
              <input id="site-import" type="file" accept=".csv,.xlsx,.xlsm" onChange={(event) => void handleImportUpload(event)} />
              <p className="field-help">Upload CSV or Excel with site fields and optional media-unit columns. This phase validates and previews only.</p>
            </div>
            <div className="import-upload-actions">
              <button className="ghost" type="button" onClick={() => void handleTemplateDownload()} disabled={isDownloadingTemplate}>
                {isDownloadingTemplate ? "Preparing..." : "Download Excel Template"}
              </button>
              <span>Use the official workbook before staging a new inventory import.</span>
            </div>
            <div className="import-schema">
              <span>Required site fields: site_code, site_name, site_type, address, city, state</span>
              <span>Optional unit fields: unit_code, width, height, monthly_rate, status</span>
            </div>
          </div>
          <div className="export-control-panel">
            <div className="field">
              <label htmlFor="export-type">Export type</label>
              <select id="export-type" value={exportType} onChange={(event) => setExportType(event.target.value as ExportType)}>
                <option value="inventory-sites">Inventory</option>
                <option value="campaigns">Campaigns</option>
                <option value="poe-reports">POE reports</option>
                <option value="invoices">Invoices / payments</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="export-status">Status filter</label>
              <input id="export-status" value={exportStatusFilter} onChange={(event) => setExportStatusFilter(event.target.value)} placeholder="optional" />
            </div>
            <button className="submit" type="button" disabled={isStartingExport} onClick={() => void handleExport()}>
              {isStartingExport ? "Starting..." : "Start Export"}
            </button>
          </div>
        </div>
        {importJob ? (
          <div className="import-review-panel">
            <div className="asset-head">
              <div>
                <p className="site-code">Import job #{importJob.id}</p>
                <h3>{importJob.status === "previewed" ? "Preview ready" : importJob.status.replaceAll("_", " ")}</h3>
                <p className="site-copy">{importJob.filters.duplicate_handling}</p>
              </div>
              <span className={`status-pill status-${importJob.status}`}>{importJob.status}</span>
            </div>
            <p className="import-preview-note">
              {importJob.status === "previewed"
                ? "No records have been imported yet. Review the preview before starting."
                : importJob.status === "completed"
                  ? "Import completed. Final result counts are shown below."
                  : "Import has been confirmed. Progress and results will update here."}
            </p>
            {importIsActive || importJob.status === "completed" || importJob.status === "failed" ? (
              <div className="progress-track import-progress">
                <span className="progress-fill" style={{ width: `${importJob.progress_percent}%` }} />
              </div>
            ) : null}
            <div className="import-summary-grid">
              <div className="module-stat"><p className="stat-label">Total rows</p><p className="stat-value">{importJob.rows_total}</p></div>
              <div className="module-stat"><p className="stat-label">Valid</p><p className="stat-value">{importSummary.valid_rows ?? 0}</p></div>
              <div className="module-stat"><p className="stat-label">Warnings</p><p className="stat-value">{importSummary.warning_rows ?? importWarnings.length}</p></div>
              <div className="module-stat"><p className="stat-label">Failed</p><p className="stat-value">{importJob.status === "previewed" ? importSummary.failed_rows ?? importJob.rows_failed : importJob.rows_failed}</p></div>
              <div className="module-stat"><p className="stat-label">Duplicates</p><p className="stat-value">{importSummary.duplicate_rows ?? 0}</p></div>
              <div className="module-stat"><p className="stat-label">Rows ready</p><p className="stat-value">{importSummary.rows_to_import ?? importJob.rows_success}</p></div>
              <div className="module-stat"><p className="stat-label">Imported</p><p className="stat-value">{importSummary.imported_count ?? importJob.rows_success}</p></div>
              <div className="module-stat"><p className="stat-label">Updated</p><p className="stat-value">{importSummary.updated_count ?? importJob.rows_updated}</p></div>
              <div className="module-stat"><p className="stat-label">Skipped</p><p className="stat-value">{importSummary.skipped_count ?? importJob.rows_skipped}</p></div>
              <div className="module-stat"><p className="stat-label">Duration</p><p className="stat-value">{importJob.duration_seconds === null ? "-" : `${importJob.duration_seconds}s`}</p></div>
            </div>
            {importJob.status === "previewed" ? (
              <div className="import-confirm-strip">
                <div>
                  <strong>{importSummary.rows_to_import ?? importJob.rows_success} row(s) ready to import</strong>
                  <p className="site-copy">{importSummary.rows_skipped ?? importJob.rows_failed} row(s) will be skipped until corrected.</p>
                </div>
                <button className="submit" type="button" disabled={!importCanStart} onClick={() => setIsImportConfirmOpen(true)}>
                  Start Import
                </button>
              </div>
            ) : null}
            {importJob.status === "confirmed" ? <p className="field-help">Import is queued for background processing.</p> : null}
            {importJob.status === "processing" ? <p className="field-help">Import is running. This panel refreshes automatically.</p> : null}
            {importJob.status === "completed" ? <p className="field-help">Import completed. Review final counts and download the report if available.</p> : null}
            {importJob.status === "failed" ? <p className="field-help">Import failed before any successful rows were committed. Review the errors below.</p> : null}
            {importJob.status === "failed" ? (
              <div className="import-confirm-strip">
                <div>
                  <strong>Retry available</strong>
                  <p className="site-copy">
                    {importJob.retry_count > 0 ? `${importJob.retry_count} retry attempt(s). Last retry ${importJob.last_retry_at ? formatDateTime(importJob.last_retry_at) : "not recorded"}.` : "This creates a linked retry job and preserves the failed history."}
                  </p>
                </div>
                <button className="submit" type="button" disabled={retryingJobId === importJob.id} onClick={() => void handleRetryJob(importJob)}>
                  {retryingJobId === importJob.id ? "Retrying..." : "Retry Import"}
                </button>
              </div>
            ) : null}
            {importWarnings.length > 0 ? (
              <div className="import-issue-list">
                <p className="stat-label">Warnings</p>
                {importWarnings.slice(0, 5).map((warning, index) => (
                  <span key={`${warning.row ?? "row"}-${index}`}>Row {warning.row ?? "-"}: {warning.warning}</span>
                ))}
              </div>
            ) : null}
            {importJob.errors.length > 0 ? (
              <div className="import-issue-list import-issue-list-error">
                <p className="stat-label">Errors</p>
                {importJob.errors.slice(0, 5).map((errorItem, index) => (
                  <span key={`${errorItem.row ?? "row"}-${index}`}>Row {errorItem.row ?? "-"}: {errorItem.error}</span>
                ))}
              </div>
            ) : null}
            {importJob.preview_rows.length > 0 ? (
              <div className="inventory-table-wrap">
                <table className="inventory-table import-preview-table">
                  <thead><tr><th>Row</th><th>Status</th><th>Site</th><th>Unit</th><th>Action</th></tr></thead>
                  <tbody>
                    {importJob.preview_rows.slice(0, 8).map((row, index) => (
                      <tr key={`${row.row ?? index}-${row.site_code ?? ""}-${row.unit_code ?? ""}`}>
                        <td>{row.row ?? "-"}</td>
                        <td><span className={`status-pill status-${row.status ?? "pending"}`}>{row.status ?? "pending"}</span></td>
                        <td>{row.site_code || row.site_name || "-"}</td>
                        <td>{row.unit_code || "-"}</td>
                        <td>{row.action?.replaceAll("_", " ") ?? row.message ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {importJob.output_file_url ? (
              <a className="asset-link" href={importJob.output_file_url} target="_blank" rel="noreferrer">Download import report</a>
            ) : null}
          </div>
        ) : null}
        {exportJobs.length > 0 ? (
          <div className="export-job-list">
            {exportJobs.map((job) => (
              <article className="export-job-row" key={job.id}>
                <div>
                  <p className="site-code">{job.resource_type.replaceAll("_", " ")}</p>
                  <p className="site-copy">Job #{job.id} | {job.rows_success}/{job.rows_total || "?"} row(s) | {formatDateTime(job.created_at)}</p>
                  {(job.status === "confirmed" || job.status === "processing") ? (
                    <div className="progress-track import-progress">
                      <span className="progress-fill" style={{ width: `${job.progress_percent}%` }} />
                    </div>
                  ) : null}
                </div>
                <div className="export-job-actions">
                  <span className={`status-pill status-${job.status}`}>{job.status === "confirmed" ? "queued" : job.status}</span>
                  {job.output_file_url ? <a className="asset-link" href={job.output_file_url} target="_blank" rel="noreferrer">Download CSV</a> : null}
                  {job.status === "failed" ? (
                    <button className="secondary-button compact" type="button" disabled={retryingJobId === job.id} onClick={() => void handleRetryJob(job)}>
                      {retryingJobId === job.id ? "Retrying..." : "Retry"}
                    </button>
                  ) : null}
                </div>
                {job.retry_count > 0 || job.retry_of_id ? (
                  <p className="site-copy">Retry {job.retry_of_id ? `of #${job.retry_of_id}` : `attempts: ${job.retry_count}`} {job.last_retry_at ? `· last ${formatDateTime(job.last_retry_at)}` : ""}</p>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
        {exportJob ? <p className="section-copy">Latest export: {exportJob.resource_type} | {exportJob.rows_total} row(s) | status {exportJob.status}</p> : null}
      </section>

      {isImportConfirmOpen && importJob ? (
        <div className="modal-backdrop" role="presentation">
          <div className="modal-card import-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="import-confirm-title">
            <div className="module-head">
              <div>
                <p className="site-code">Import job #{importJob.id}</p>
                <h2 id="import-confirm-title">Start inventory import?</h2>
              </div>
              <button className="ghost" type="button" onClick={() => setIsImportConfirmOpen(false)}>Close</button>
            </div>
            <p className="section-copy">This will import valid and warning rows in the background. Failed rows will be skipped.</p>
            <div className="import-summary-grid">
              <div className="module-stat"><p className="stat-label">Rows ready</p><p className="stat-value">{importSummary.rows_to_import ?? importJob.rows_success}</p></div>
              <div className="module-stat"><p className="stat-label">Warnings</p><p className="stat-value">{importSummary.warning_rows ?? 0}</p></div>
              <div className="module-stat"><p className="stat-label">Failed skipped</p><p className="stat-value">{importSummary.rows_skipped ?? importJob.rows_failed}</p></div>
            </div>
            <div className="form-actions">
              <button className="ghost" type="button" onClick={() => setIsImportConfirmOpen(false)}>Cancel</button>
              <button className="submit" type="button" disabled={isStartingImport} onClick={() => void handleConfirmImport()}>
                {isStartingImport ? "Starting..." : "Confirm and start"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <section className="module-card">
        <div className="module-head">
          <h2>Unified operational timeline</h2>
          <span>{summary?.timeline.length ?? 0} signals</span>
        </div>
        <div className="ops-timeline">
          {(summary?.timeline ?? []).map((item) => (
            <article className="ops-timeline-row" key={item.id}>
              <StatusDot status={item.status} />
              <div>
                <p className="site-code">{item.kind} / {item.module}</p>
                <h3>{item.summary}</h3>
                <p className="site-copy">{item.actor} | {formatDateTime(item.created_at)}</p>
              </div>
              <span className={`status-pill status-${item.status}`}>{item.status}</span>
            </article>
          ))}
          {summary && summary.timeline.length === 0 ? <p className="empty-state">No operational activity for this filter.</p> : null}
        </div>
      </section>

      <section className="module-card">
        <div className="module-head">
          <h2>Recent audit timeline</h2>
          <span>{auditEvents.length} events</span>
        </div>
        <div className="inventory-table-wrap">
          <table className="inventory-table">
            <thead>
              <tr><th>Event</th><th>Entity</th><th>Severity</th><th>Actor</th><th>Time</th></tr>
            </thead>
            <tbody>
              {auditEvents.map((event) => (
                <tr key={event.id}>
                  <td><div className="table-primary"><strong>{event.event_type}</strong><span>{event.summary}</span></div></td>
                  <td>{event.entity_type} #{event.entity_id}</td>
                  <td><span className={`status-pill status-${event.severity}`}>{event.severity}</span></td>
                  <td>{event.actor_email || "System"}</td>
                  <td>{formatDateTime(event.created_at)}</td>
                </tr>
              ))}
              {!isLoading && auditEvents.length === 0 ? <tr><td colSpan={5}>Audit timeline will populate as operations happen.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
