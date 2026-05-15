"use client";

import Link from "next/link";
import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  createExportJob,
  fetchAuditEvents,
  fetchDiagnostics,
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

const INITIAL_FILTERS = {
  date_from: "",
  date_to: "",
  campaign: "",
  site: "",
  field_agent: "",
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
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  async function load(nextFilters = filters) {
    setIsLoading(true);
    setError("");
    try {
      const profile = await fetchCurrentUser();
      setUser(profile);
      const [summaryPayload, auditPayload] = await Promise.all([
        fetchOperationsSummary(nextFilters),
        fetchAuditEvents({ severity: nextFilters.severity, event_type: nextFilters.event_type }),
      ]);
      setSummary(summaryPayload);
      setAuditEvents(auditPayload);
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
        const [summaryPayload, auditPayload] = await Promise.all([
          fetchOperationsSummary(INITIAL_FILTERS),
          fetchAuditEvents({ severity: "", event_type: "" }),
        ]);
        setSummary(summaryPayload);
        setAuditEvents(auditPayload);
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
      setMessage("Import preview is ready. No records have been imported yet.");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Unable to preview import file.");
    }
  }

  async function handleExport(path: "campaigns" | "invoices" | "poe-reports" | "client-statements") {
    setExportJob(await createExportJob(path, filters));
    setMessage("Export job completed. Use the generated file link from the job once storage exposes it.");
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
          <div className="form-actions">
            <button className="ghost" type="button" onClick={() => void handleExport("campaigns")}>Export campaigns</button>
            <button className="ghost" type="button" onClick={() => void handleExport("invoices")}>Export invoices</button>
            <button className="ghost" type="button" onClick={() => void handleExport("poe-reports")}>Export POE</button>
            <button className="ghost" type="button" onClick={() => void handleExport("client-statements")}>Export statements</button>
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
            <p className="import-preview-note">No records have been imported yet. Review the preview before enabling the confirmation workflow.</p>
            <div className="import-summary-grid">
              <div className="module-stat"><p className="stat-label">Total rows</p><p className="stat-value">{importJob.rows_total}</p></div>
              <div className="module-stat"><p className="stat-label">Valid</p><p className="stat-value">{importSummary.valid_rows ?? 0}</p></div>
              <div className="module-stat"><p className="stat-label">Warnings</p><p className="stat-value">{importSummary.warning_rows ?? importWarnings.length}</p></div>
              <div className="module-stat"><p className="stat-label">Failed</p><p className="stat-value">{importJob.rows_failed}</p></div>
              <div className="module-stat"><p className="stat-label">Duplicates</p><p className="stat-value">{importSummary.duplicate_rows ?? 0}</p></div>
              <div className="module-stat"><p className="stat-label">Rows ready</p><p className="stat-value">{importSummary.rows_to_import ?? importJob.rows_success}</p></div>
            </div>
            {importJob.status === "previewed" ? (
              <div className="import-confirm-strip">
                <div>
                  <strong>{importSummary.rows_to_import ?? importJob.rows_success} row(s) ready to import</strong>
                  <p className="site-copy">{importSummary.rows_skipped ?? importJob.rows_failed} row(s) will be skipped until corrected.</p>
                </div>
                <button className="submit" type="button" disabled>
                  Start Import
                </button>
              </div>
            ) : null}
            <p className="field-help">Start Import is intentionally disabled until the confirmation and background-processing phase is implemented.</p>
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
        {exportJob ? <p className="section-copy">Latest export: {exportJob.resource_type} | {exportJob.rows_total} row(s) | status {exportJob.status}</p> : null}
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
