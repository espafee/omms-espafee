"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, getAccessToken, getStoredUser, type AuthUser } from "@/lib/auth";
import { fetchPlannerLinks, type PlannerLink } from "@/lib/planner";
import {
  fetchMediaPlannerDiagnostics,
  type MediaPlannerDiagnosticsPayload,
} from "@/lib/platform-diagnostics";

export default function MediaPlannerDiagnosticsPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [links, setLinks] = useState<PlannerLink[]>([]);
  const [payload, setPayload] = useState<MediaPlannerDiagnosticsPayload | null>(null);
  const [error, setError] = useState("");
  const [copyFeedback, setCopyFeedback] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    const storedUser = getStoredUser();
    setUser(storedUser);
    if (!storedUser?.is_platform_admin) {
      setIsReady(true);
      return;
    }
    fetchPlannerLinks()
      .then(setLinks)
      .catch(() => setLinks([]))
      .finally(() => setIsReady(true));
  }, [router]);

  async function runDiagnostics(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPayload(null);
    setCopyFeedback("");
    setIsLoading(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await fetchMediaPlannerDiagnostics({
        planner_link_id: String(form.get("planner_link_id") || ""),
        planner_title: String(form.get("planner_title") || ""),
        unit_code: String(form.get("unit_code") || ""),
        requested_start_date: String(form.get("requested_start_date") || ""),
        requested_end_date: String(form.get("requested_end_date") || ""),
      });
      setPayload(result);
    } catch (diagnosticError) {
      setError(
        diagnosticError instanceof Error
          ? diagnosticError.message
          : "Unable to run media planner diagnostics.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function copyJson() {
    if (!payload) return;
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setCopyFeedback("Diagnostics JSON copied");
  }

  if (!isReady) {
    return <main className="public-shell"><p className="empty-state">Loading diagnostics...</p></main>;
  }

  if (!user?.is_platform_admin) {
    return (
      <main className="public-shell">
        <section className="auth-card">
          <span className="eyebrow">Platform diagnostics</span>
          <h1>Restricted</h1>
          <p>Only platform superadmins can access media planner diagnostics.</p>
        </section>
      </main>
    );
  }

  return (
    <AppShell
      active="operations"
      roleLabel={user.role ?? "platform_admin"}
      userEmail={user.email ?? ""}
      title="Media Planner Diagnostics"
      eyebrow="Platform diagnostics"
      description="Read-only production evidence for Live Media Planner inventory visibility."
      onLogout={() => {
        clearAuthSession();
        router.replace("/login");
      }}
    >
      <section className="diagnostics-warning" role="status">
        <strong>Platform diagnostics.</strong>
        <span>Contains operational metadata. Do not share publicly.</span>
      </section>

      <section className="dashboard-grid diagnostics-layout">
        <form className="module-panel diagnostics-form" onSubmit={runDiagnostics}>
          <div>
            <span className="eyebrow">Planner lookup</span>
            <h2>Run safe visibility trace</h2>
            <p className="site-copy">Use a planner link id or exact title. Raw planner tokens are not accepted.</p>
          </div>
          <label>
            Planner link
            <select name="planner_link_id" defaultValue="">
              <option value="">Select a planner link</option>
              {links.map((link) => (
                <option key={link.id} value={link.id}>
                  #{link.id} - {link.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Planner title fallback
            <input name="planner_title" placeholder="Live Media Planner" />
          </label>
          <label>
            Unit codes
            <textarea name="unit_code" rows={3} placeholder="ESPA-001, ESPA-002_1, ESPA-002_2" />
          </label>
          <div className="form-grid">
            <label>
              Start date
              <input name="requested_start_date" type="date" />
            </label>
            <label>
              End date
              <input name="requested_end_date" type="date" />
            </label>
          </div>
          <button className="primary" type="submit" disabled={isLoading}>
            {isLoading ? "Running diagnostics..." : "Run diagnostics"}
          </button>
          {error ? <p className="form-error">{error}</p> : null}
        </form>

        <div className="module-panel diagnostics-output">
          <div className="panel-heading-row">
            <div>
              <span className="eyebrow">Safe evidence</span>
              <h2>Pipeline result</h2>
            </div>
            <button className="ghost" type="button" onClick={copyJson} disabled={!payload}>
              Copy diagnostics JSON
            </button>
          </div>
          {copyFeedback ? <p className="planner-action-feedback">{copyFeedback}</p> : null}
          {payload ? (
            <>
              <div className="diagnostics-cards">
                <DiagnosticCard label="Eligible units" value={payload.planner_link.eligible_count} />
                <DiagnosticCard label="Git SHA" value={payload.service.git_sha} />
                <DiagnosticCard label="DB fingerprint" value={payload.database.database_fingerprint} />
                <DiagnosticCard label="Environment" value={payload.service.environment} />
              </div>
              <DiagnosticsMap title="Pipeline counts" rows={payload.pipeline} />
              <DiagnosticsMap title="Grouped exclusions" rows={payload.exclusions} />
              <div>
                <h3>Migration checks</h3>
                <div className="diagnostics-migrations">
                  {Object.entries(payload.database.migration_status).map(([name, applied]) => (
                    <span key={name} className={applied ? "status-pill status-pill-success" : "status-pill status-pill-warning"}>
                      {name}: {applied ? "applied" : "missing"}
                    </span>
                  ))}
                </div>
              </div>
              <div className="diagnostics-table-wrap">
                <table className="data-table diagnostics-table">
                  <thead>
                    <tr>
                      <th>Unit</th>
                      <th>Tenant</th>
                      <th>Published</th>
                      <th>City</th>
                      <th>Status</th>
                      <th>Eligible</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payload.units.map((unit) => (
                      <tr key={unit.code}>
                        <td>{unit.code}</td>
                        <td>{unit.tenant_id ?? "-"}</td>
                        <td>{unit.published ? "Yes" : "No"}</td>
                        <td>{unit.city_raw || "-"}</td>
                        <td>{unit.status}</td>
                        <td>{unit.eligible ? "Yes" : "No"}</td>
                        <td>{unit.exclusion_reason ?? "Included"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="empty-state">Run diagnostics to see pipeline counts and safe sampled units.</p>
          )}
        </div>
      </section>
    </AppShell>
  );
}

function DiagnosticCard({ label, value }: { label: string; value: string | number }) {
  return (
    <article className="ops-kpi-card">
      <p className="stat-label">{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

function DiagnosticsMap({ title, rows }: { title: string; rows: Record<string, number> }) {
  return (
    <div>
      <h3>{title}</h3>
      <dl className="diagnostics-map">
        {Object.entries(rows).map(([key, value]) => (
          <div key={key}>
            <dt>{key.replaceAll("_", " ")}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

