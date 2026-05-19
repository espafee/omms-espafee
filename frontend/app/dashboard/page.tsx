"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  fetchDashboardData,
  fetchDashboardProfile,
  formatCurrency,
  restoreDashboardProfileDefaults,
  type DashboardPayload,
  type DashboardProfile,
  updateDashboardProfile,
} from "@/lib/dashboard";

type StoredUser = {
  email?: string;
  role?: string;
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [profile, setProfile] = useState<DashboardProfile | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

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
        const currentUser = await fetchCurrentUser();
        if (currentUser) {
          setUser(currentUser);
        }
        const dashboardProfile = await fetchDashboardProfile();
        setProfile(dashboardProfile);
        const summaries = await fetchDashboardData({ includeBilling: dashboardProfile.can_view_finance });
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
      return "Monitor campaigns, bookings, inventory, and billing performance from one operations view.";
    }
    return `Welcome back. Your dashboard is tailored for ${profile?.role_label ?? user.role.replace("_", " ")} workflows.`;
  }, [profile, user]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  const activeWidgetSet = useMemo(() => new Set(profile?.active_widgets ?? []), [profile]);

  function hasWidget(key: string) {
    return activeWidgetSet.has(key);
  }

  const quickStats = useMemo(() => {
    if (!dashboard) {
      return [];
    }

    return [
      { key: "campaign_performance", label: "Active campaigns", value: String(dashboard.campaigns.active_campaigns) },
      { key: "assigned_work", label: "Live bookings", value: String(dashboard.bookings.live_bookings) },
      { key: "billing_risk", label: "Outstanding revenue", value: formatCurrency(dashboard.billing?.outstanding_amount ?? "0.00") },
      { key: "client_campaign_status", label: "Approved assets", value: String(dashboard.campaigns.approved_assets) },
    ].filter((item) => activeWidgetSet.has(item.key) || (item.key === "billing_risk" && profile?.can_view_finance));
  }, [activeWidgetSet, dashboard, profile]);

  async function handleWidgetToggle(widgetKey: string, isVisible: boolean) {
    if (!profile?.can_customize) {
      return;
    }
    setIsSavingProfile(true);
    setError("");
    setMessage("");
    try {
      const nextWidgets = profile.available_widgets.map((widget) => ({
        widget_key: widget.key,
        is_visible: widget.key === widgetKey ? isVisible : widget.is_visible,
        sort_order: widget.sort_order,
      }));
      setProfile(await updateDashboardProfile(nextWidgets));
      setMessage("Dashboard preference saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save dashboard preference.");
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handleRestoreDefaults() {
    setIsSavingProfile(true);
    setError("");
    setMessage("");
    try {
      setProfile(await restoreDashboardProfileDefaults());
      setMessage("Dashboard defaults restored.");
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Unable to restore dashboard defaults.");
    } finally {
      setIsSavingProfile(false);
    }
  }

  return (
    <AppShell
      active="dashboard"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title="Dashboard overview"
      description={headline}
      onLogout={handleLogout}
    >
        {error ? <p className="error dashboard-error">{error}</p> : null}
        {message ? <p className="success">{message}</p> : null}

        {profile?.can_customize ? (
          <section className="module-card dashboard-customize">
            <div className="module-head">
              <div>
                <h2>Customize dashboard</h2>
                <p className="site-copy">Role defaults are applied first. Hide safe optional widgets you do not need.</p>
              </div>
              <button className="ghost" type="button" onClick={handleRestoreDefaults} disabled={isSavingProfile}>
                Restore defaults
              </button>
            </div>
            <div className="dashboard-widget-toggles">
              {profile.available_widgets.map((widget) => (
                <label className="dashboard-widget-toggle" key={widget.key}>
                  <input
                    type="checkbox"
                    checked={widget.is_visible}
                    disabled={widget.is_required || isSavingProfile}
                    onChange={(event) => handleWidgetToggle(widget.key, event.target.checked)}
                  />
                  <span>
                    <strong>{widget.label}</strong>
                    <small>{widget.category} · {widget.description}</small>
                  </span>
                </label>
              ))}
            </div>
          </section>
        ) : null}

        <section className="summary-row" aria-label="Quick stats">
          {quickStats.map((item) => (
            <article className="summary-card" key={item.label}>
              <p className="stat-label">{item.label}</p>
              <p className="summary-value">{isLoading ? "..." : item.value}</p>
            </article>
          ))}
        </section>

        <section className="module-grid">
          {hasWidget("campaign_performance") || hasWidget("critical_campaigns") || hasWidget("client_campaign_status") ? (
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
          ) : null}

          {hasWidget("assigned_work") || hasWidget("pending_poe_uploads") || hasWidget("campaign_performance") ? (
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
          ) : null}

          {profile?.can_view_finance && (hasWidget("billing_risk") || hasWidget("overdue_invoices") || hasWidget("collection_efficiency") || hasWidget("client_invoices")) ? (
          <article className="module-card module-card-highlight">
            <div className="module-head">
              <h2>Revenue watch</h2>
              <span>Billing</span>
            </div>
            <div className="module-stats">
              <Link className="module-stat" href="/billing?invoiceStatus=unpaid">
                <p className="stat-label">Total invoiced</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.billing?.total_invoiced ?? "0.00")}
                </p>
              </Link>
              <Link className="module-stat" href="/billing?payments=this_month">
                <p className="stat-label">Collected</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.billing?.total_paid ?? "0.00")}
                </p>
              </Link>
              <Link className="module-stat" href="/billing?invoiceStatus=overdue">
                <p className="stat-label">Overdue amount</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.billing?.overdue_amount ?? "0.00")}
                </p>
              </Link>
              <Link className="module-stat" href="/billing?invoiceStatus=due_soon">
                <p className="stat-label">Due soon</p>
                <p className="stat-value">{isLoading ? "..." : dashboard?.billing?.due_soon_invoices ?? 0}</p>
              </Link>
              <Link className="module-stat" href="/billing?payments=this_month">
                <p className="stat-label">This month</p>
                <p className="stat-value">
                  {isLoading ? "..." : formatCurrency(dashboard?.billing?.payments_received_this_month ?? "0.00")}
                </p>
              </Link>
              <Link className="module-stat" href="/billing?invoiceStatus=draft">
                <p className="stat-label">Draft invoices</p>
                <p className="stat-value">{isLoading ? "..." : dashboard?.billing?.draft_invoices ?? 0}</p>
              </Link>
            </div>
          </article>
          ) : null}
        </section>

        <section className="activity-strip">
          {hasWidget("import_export_jobs") || hasWidget("assigned_work") || hasWidget("pending_poe_uploads") ? (
          <article className="activity-card">
            <p className="stat-label">Bookings needing attention</p>
            <p className="activity-value">{isLoading ? "..." : dashboard?.bookings.pending_bookings ?? 0}</p>
            <p className="activity-copy">Pending booking windows awaiting confirmation or follow-up.</p>
          </article>
          ) : null}
          {hasWidget("campaign_performance") || hasWidget("client_campaign_status") ? (
          <article className="activity-card">
            <p className="stat-label">Inventory in use</p>
            <p className="activity-value">{isLoading ? "..." : dashboard?.bookings.unique_media_units ?? 0}</p>
            <p className="activity-copy">Media units currently represented across visible booking activity.</p>
          </article>
          ) : null}
          {profile?.can_view_finance && (hasWidget("billing_risk") || hasWidget("overdue_invoices") || hasWidget("client_invoices")) ? (
          <article className="activity-card">
            <p className="stat-label">Actions needed</p>
            <p className="activity-value">{isLoading ? "..." : dashboard?.billing?.overdue_invoices ?? 0}</p>
            <p className="activity-copy">Overdue invoices or campaign finance items that may need attention.</p>
          </article>
          ) : null}
        </section>
    </AppShell>
  );
}
