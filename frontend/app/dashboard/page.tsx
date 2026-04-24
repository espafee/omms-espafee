"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { fetchDashboardData, formatCurrency, type DashboardPayload } from "@/lib/dashboard";

type StoredUser = {
  email?: string;
  role?: string;
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
    }

    async function loadDashboard() {
      setIsLoading(true);
      setError("");

      try {
        const [profile, summaries] = await Promise.all([
          fetchCurrentUser(),
          fetchDashboardData(),
        ]);
        if (profile) {
          setUser(profile);
        }
        setDashboard(summaries);
      } catch (loadError) {
        const message = loadError instanceof Error ? loadError.message : "Unable to load the dashboard.";
        setError(message);
        if (message.includes("sign in again")) {
          router.replace("/login");
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadDashboard();
  }, [router]);

  const headline = useMemo(() => {
    if (!user?.role) {
      return "Your account is connected and ready.";
    }
    return `Signed in as ${user.role}. Your summaries are filtered according to your access level.`;
  }, [user]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  const quickStats = useMemo(() => {
    if (!dashboard) {
      return [];
    }

    return [
      { label: "Active campaigns", value: String(dashboard.campaigns.active_campaigns) },
      { label: "Live bookings", value: String(dashboard.bookings.live_bookings) },
      { label: "Outstanding revenue", value: formatCurrency(dashboard.billing.outstanding_amount) },
      { label: "Approved assets", value: String(dashboard.campaigns.approved_assets) },
    ];
  }, [dashboard]);

  return (
    <AppShell
      active="dashboard"
      roleLabel={user?.role ?? "Authenticated"}
      userEmail={user?.email ?? "Loading user..."}
      title="Dashboard overview"
      description={headline}
      onLogout={handleLogout}
    >
        {error ? <p className="error dashboard-error">{error}</p> : null}

        <section className="summary-row" aria-label="Quick stats">
          {quickStats.map((item) => (
            <article className="summary-card" key={item.label}>
              <p className="stat-label">{item.label}</p>
              <p className="summary-value">{isLoading ? "..." : item.value}</p>
            </article>
          ))}
        </section>

        <section className="module-grid">
          <article className="module-card">
            <div className="module-head">
              <h2>Campaign performance</h2>
              <span>Campaigns</span>
            </div>
            <div className="module-stats">
              <div className="module-stat">
                <p className="stat-label">Total campaigns</p>
                <p className="stat-value">{isLoading ? "..." : dashboard?.campaigns.total_campaigns ?? 0}</p>
              </div>
              <div className="module-stat">
                <p className="stat-label">Active budget</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.campaigns.active_budget ?? "0.00")}
                </p>
              </div>
              <div className="module-stat">
                <p className="stat-label">Approved assets</p>
                <p className="stat-value">{isLoading ? "..." : dashboard?.campaigns.approved_assets ?? 0}</p>
              </div>
            </div>
          </article>

          <article className="module-card">
            <div className="module-head">
              <h2>Booking pipeline</h2>
              <span>Bookings</span>
            </div>
            <div className="module-stats">
              <div className="module-stat">
                <p className="stat-label">Confirmed</p>
                <p className="stat-value">{isLoading ? "..." : dashboard?.bookings.confirmed_bookings ?? 0}</p>
              </div>
              <div className="module-stat">
                <p className="stat-label">Live value</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.bookings.live_booked_value ?? "0.00")}
                </p>
              </div>
              <div className="module-stat">
                <p className="stat-label">Media units</p>
                <p className="stat-value">{isLoading ? "..." : dashboard?.bookings.unique_media_units ?? 0}</p>
              </div>
            </div>
          </article>

          <article className="module-card module-card-highlight">
            <div className="module-head">
              <h2>Revenue watch</h2>
              <span>Billing</span>
            </div>
            <div className="module-stats">
              <div className="module-stat">
                <p className="stat-label">Total invoiced</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.billing.total_invoiced ?? "0.00")}
                </p>
              </div>
              <div className="module-stat">
                <p className="stat-label">Collected</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.billing.total_paid ?? "0.00")}
                </p>
              </div>
              <div className="module-stat">
                <p className="stat-label">Overdue amount</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.billing.overdue_amount ?? "0.00")}
                </p>
              </div>
            </div>
          </article>
        </section>

        <section className="activity-strip">
          <article className="activity-card">
            <p className="stat-label">Session</p>
            <p className="activity-value">JWT authenticated</p>
            <p className="activity-copy">Stored in localStorage and used for summary requests.</p>
          </article>
          <article className="activity-card">
            <p className="stat-label">Dashboard source</p>
            <p className="activity-value">Live API summaries</p>
            <p className="activity-copy">Campaign, booking, and billing cards are loaded from the backend.</p>
          </article>
          <article className="activity-card">
            <p className="stat-label">Next frontend slice</p>
            <p className="activity-value">Module detail pages</p>
            <p className="activity-copy">Campaign tables, booking workflows, and invoice detail screens fit next.</p>
          </article>
        </section>
    </AppShell>
  );
}
