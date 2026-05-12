"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { fetchAuditEvents, fetchDiagnostics, fetchPoeAnalytics, type AuditEvent, type DiagnosticsPayload, type PoeAnalytics } from "@/lib/observability";

type StoredUser = {
  email?: string;
  role?: string;
};

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function OperationsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [poe, setPoe] = useState<PoeAnalytics | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsPayload | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
    }

    async function load() {
      setIsLoading(true);
      setError("");
      try {
        const profile = await fetchCurrentUser();
        setUser(profile);
        const [poePayload, auditPayload] = await Promise.all([fetchPoeAnalytics(), fetchAuditEvents()]);
        setPoe(poePayload);
        setAuditEvents(auditPayload);
        if (profile.role === "admin") {
          setDiagnostics(await fetchDiagnostics());
        }
      } catch (loadError) {
        const message = loadError instanceof Error ? loadError.message : "Unable to load operations intelligence.";
        setError(message);
        if (message.includes("sign in again")) {
          router.replace("/login");
        }
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [router]);

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
      description="Monitor suspicious POE activity, audit events, request health, and platform diagnostics."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}
      <section className="summary-row" aria-label="POE intelligence">
        <article className="summary-card">
          <p className="stat-label">Suspicious POEs</p>
          <p className="summary-value">{isLoading ? "..." : poe?.suspicious_count ?? 0}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Outside geofence</p>
          <p className="summary-value">{isLoading ? "..." : poe?.outside_geofence_count ?? 0}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Missing GPS</p>
          <p className="summary-value">{isLoading ? "..." : poe?.missing_gps_count ?? 0}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Overdue reviews</p>
          <p className="summary-value">{isLoading ? "..." : poe?.overdue_review_count ?? 0}</p>
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Suspicious POE queue</h2>
            <Link href="/poe">Open POE review</Link>
          </div>
          <div className="asset-list">
            {(poe?.recent_suspicious ?? []).map((record) => (
              <article className="asset-card" key={record.id}>
                <div className="asset-head">
                  <div>
                    <p className="site-code">POE #{record.id}</p>
                    <h3>{record.campaign}</h3>
                    <p className="site-copy">{record.site} | {formatDateTime(record.captured_at)}</p>
                  </div>
                  <span className={`status-pill status-${record.status}`}>{record.status}</span>
                </div>
              </article>
            ))}
            {poe && poe.recent_suspicious.length === 0 ? <p className="empty-state">No suspicious POE records right now.</p> : null}
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Diagnostics</h2>
            <span>{diagnostics ? "Admin" : "Admin only"}</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Database</p>
              <p className="stat-value">{diagnostics?.database.ok ? "OK" : diagnostics ? "Check" : "Hidden"}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Cache</p>
              <p className="stat-value">{diagnostics?.cache.ok ? "OK" : diagnostics ? "Check" : "Hidden"}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Slow threshold</p>
              <p className="stat-value">{diagnostics ? `${diagnostics.request_logging.slow_threshold_ms}ms` : "Hidden"}</p>
            </div>
          </div>
        </article>
      </section>

      <section className="module-card">
        <div className="module-head">
          <h2>Recent audit timeline</h2>
          <span>{auditEvents.length} events</span>
        </div>
        <div className="inventory-table-wrap">
          <table className="inventory-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Entity</th>
                <th>Severity</th>
                <th>Actor</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {auditEvents.map((event) => (
                <tr key={event.id}>
                  <td>
                    <div className="table-primary">
                      <strong>{event.event_type}</strong>
                      <span>{event.summary}</span>
                    </div>
                  </td>
                  <td>{event.entity_type} #{event.entity_id}</td>
                  <td><span className={`status-pill status-${event.severity}`}>{event.severity}</span></td>
                  <td>{event.actor_email || "System"}</td>
                  <td>{formatDateTime(event.created_at)}</td>
                </tr>
              ))}
              {!isLoading && auditEvents.length === 0 ? (
                <tr>
                  <td colSpan={5}>Audit timeline will populate as operations happen.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
