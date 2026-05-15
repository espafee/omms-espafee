"use client";

import Link from "next/link";
import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  confirmImportJob,
  createExportJob,
  fetchAuditEvents,
  fetchDiagnostics,
  fetchExportJobs,
  fetchImportJob,
  fetchOperationsSummary,
  uploadInventorySiteImport,
  type AuditEvent,
  type DiagnosticsPayload,
  type ImportExportJob,
  type OperationsSummary,
} from "@/lib/observability";

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
  status: "",
  severity: "",
  event_type: "",
};

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
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

export default function OperationsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsPayload | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [importJob, setImportJob] = useState<ImportExportJob | null>(null);
  const [exportJob, setExportJob] = useState<ImportExportJob | null>(null);
  const [exportJobs, setExportJobs] = useState<ImportExportJob[]>([]);
  const [exportType, setExportType] = useState<ExportType>("inventory-sites");
  const [exportStatusFilter, setExportStatusFilter] = useState("");
  const [isStartingExport, setIsStartingExport] = useState(false);
  const [isImportConfirmOpen, setIsImportConfirmOpen] = useState(false);
  const [isStartingImport, setIsStartingImport] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  async function load(nextFilters = filters) {
    setIsLoading(true);
    setError("");
    try {
      const profile = await fetchCurrentUser();
      setUser(profile);
      const [summaryPayload, auditPayload, exportPayload] = await Promise.all([
        fetchOperationsSummary(nextFilters),
        fetchAuditEvents({ severity: nextFilters.severity, event_type: nextFilters.event_type }),
        fetchExportJobs(),
      ]);
      setSummary(summaryPayload);
      setAuditEvents(auditPayload);
      setExportJobs(exportPayload);
      if (profile.role === "admin") {
        setDiagnostics(await fetchDiagnostics());
      }
    } catch (loadError) {
      const nextMessage = loadError instanceof Error ? loadError.message : "Unable to load operations intelligence.";
      setError(nextMessage);
      if (nextMessage.includes("sign in again")) {
        router.replace("/login");
      }
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
    }
    async function loadInitial() {
      setIsLoading(true);
      setError("");
      try {
        const profile = await fetchCurrentUser();
        setUser(profile);
        const [summaryPayload, auditPayload, exportPayload] = await Promise.all([
          fetchOperationsSummary(INITIAL_FILTERS),
          fetchAuditEvents({ severity: "", event_type: "" }),
          fetchExportJobs(),
        ]);
        setSummary(summaryPayload);
        setAuditEvents(auditPayload);
        setExportJobs(exportPayload);
        if (profile.role === "admin") {
          setDiagnostics(await fetchDiagnostics());
        }
      } catch (loadError) {
        const nextMessage = loadError instanceof Error ? loadError.message : "Unable to load operations intelligence.";
        setError(nextMessage);
        if (nextMessage.includes("sign in again")) {
          router.replace("/login");
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadInitial();
  }, [router]);

  const maxTrend = useMemo(() => Math.max(1, ...(summary?.poe.trends_by_date ?? []).map((item) => item.total)), [summary]);
  const maxSeverity = useMemo(() => Math.max(1, ...(summary?.audit_by_severity ?? []).map((item) => item.total)), [summary]);
  const importSummary = importJob?.filters.summary ?? {};
  const importWarnings = importJob?.filters.warnings ?? [];
  const importRowsReady = (importSummary.rows_to_import ?? importJob?.rows_success ?? 0) > 0;
  const importCanStart = importJob?.status === "previewed" && importRowsReady;
  const importIsActive = importJob?.status === "confirmed" || importJob?.status === "processing";
  const exportIsActive = exportJobs.some((job) => job.status === "confirmed" || job.status === "processing");

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
    }, 3000);
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
    }, 3000);
    return () => window.clearInterval(timer);
  }, [exportIsActive]);

  function updateFilter(field: keyof typeof filters, value: string) {
    setFilters((current) => ({ ...current, [field]: value }));
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

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

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

      <section className="module-card">
        <div className="module-head">
          <h2>Filters</h2>
          <button className="ghost" type="button" onClick={() => void load(filters)}>Apply filters</button>
        </div>
        <div className="site-form-grid">
          {(["date_from", "date_to", "campaign", "site", "field_agent", "status", "severity", "event_type"] as const).map((field) => (
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
      </section>

      <section className="summary-row" aria-label="Operations intelligence">
        <article className="summary-card">
          <p className="stat-label">Suspicious POEs</p>
          <p className="summary-value">{isLoading ? "..." : summary?.poe.suspicious_count ?? 0}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Slow requests</p>
          <p className="summary-value">{isLoading ? "..." : summary?.slow_requests_count ?? 0}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Failed notifications</p>
          <p className="summary-value">{isLoading ? "..." : summary?.notification_failures_count ?? 0}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Overdue reviews</p>
          <p className="summary-value">{isLoading ? "..." : summary?.poe.overdue_review_count ?? 0}</p>
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Suspicious POE trend</h2>
            <Link href="/poe">Open POE review</Link>
          </div>
          <div className="module-stats">
            {(summary?.poe.trends_by_date ?? []).slice(-7).map((item) => (
              <SimpleBar key={item.day} label={item.day || "Unknown"} value={item.suspicious || item.total} max={maxTrend} />
            ))}
            {summary && summary.poe.trends_by_date.length === 0 ? <p className="empty-state">No POE trend data yet.</p> : null}
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Audit severity</h2>
            <span>Timeline</span>
          </div>
          <div className="module-stats">
            {(summary?.audit_by_severity ?? []).map((item) => (
              <SimpleBar key={item.severity} label={item.severity} value={item.total} max={maxSeverity} />
            ))}
            {summary && summary.audit_by_severity.length === 0 ? <p className="empty-state">Audit events will appear as workflows run.</p> : null}
          </div>
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Recent critical alerts</h2>
            <span>{summary?.recent_critical_alerts.length ?? 0}</span>
          </div>
          <div className="asset-list">
            {(summary?.recent_critical_alerts ?? []).map((alert) => (
              <article className="asset-card" key={alert.id}>
                <div className="asset-head">
                  <div>
                    <p className="site-code">{alert.metric}</p>
                    <h3>{alert.summary}</h3>
                    <p className="site-copy">{formatDateTime(alert.created_at)}</p>
                  </div>
                  <span className={`status-pill status-${alert.severity}`}>{alert.severity}</span>
                </div>
              </article>
            ))}
            {summary && summary.recent_critical_alerts.length === 0 ? <p className="empty-state">No critical alerts right now.</p> : null}
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Diagnostics</h2>
            <span>{diagnostics ? "Admin" : "Admin only"}</span>
          </div>
          <div className="module-stats">
            <div className="module-stat"><p className="stat-label">Database</p><p className="stat-value">{diagnostics?.database.ok ? "OK" : diagnostics ? "Check" : "Hidden"}</p></div>
            <div className="module-stat"><p className="stat-label">Cache</p><p className="stat-value">{diagnostics?.cache.ok ? "OK" : diagnostics ? "Check" : "Hidden"}</p></div>
            <div className="module-stat"><p className="stat-label">Background jobs</p><p className="stat-value">{diagnostics?.background_jobs.background_jobs_enabled ? "Enabled" : diagnostics ? "Off" : "Hidden"}</p></div>
          </div>
        </article>
      </section>

      <section className="module-card">
        <div className="module-head">
          <h2>Import / export workbench</h2>
          <span>Staged CSV / Excel</span>
        </div>
        <div className="import-workbench">
          <div className="import-upload-panel">
            <div className="field">
              <label htmlFor="site-import">Inventory import file</label>
              <input id="site-import" type="file" accept=".csv,.xlsx,.xlsm" onChange={(event) => void handleImportUpload(event)} />
              <p className="field-help">Upload CSV or Excel with site fields and optional media-unit columns. This phase validates and previews only.</p>
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
                </div>
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
