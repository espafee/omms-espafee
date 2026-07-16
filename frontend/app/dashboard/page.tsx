"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
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
  type DashboardWidget,
  updateDashboardProfile,
} from "@/lib/dashboard";
import { fetchOperationalMode, type OperationalMode } from "@/lib/environment";

type StoredUser = {
  email?: string;
  role?: string;
};

type WidgetContext = {
  dashboard: DashboardPayload | null;
  isLoading: boolean;
  profile: DashboardProfile;
  operationalMode: OperationalMode | null;
};

type WidgetDefinition = {
  render: (context: WidgetContext) => ReactNode;
  requiresFinance?: boolean;
  requiresOperations?: boolean;
};

const FINANCE_WIDGET_KEYS = [
  "billing_risk",
  "overdue_invoices",
  "collection_efficiency",
  "invoice_payment_trend",
  "billing_alerts",
  "client_invoices",
];

function profileHasVisibleFinanceWidgets(dashboardProfile: DashboardProfile) {
  return FINANCE_WIDGET_KEYS.some((key) => dashboardProfile.active_widgets.includes(key));
}

function applyWidgetVisibility(profile: DashboardProfile, widgets: Array<{ widget_key: string; is_visible: boolean; sort_order: number }>) {
  const widgetState = new Map(widgets.map((widget) => [widget.widget_key, widget]));
  const availableWidgets = profile.available_widgets.map((widget) => {
    const nextWidget = widgetState.get(widget.key);
    const isVisible = widget.is_required || (nextWidget ? nextWidget.is_visible : widget.is_visible);
    return {
      ...widget,
      is_visible: isVisible,
      sort_order: nextWidget?.sort_order ?? widget.sort_order,
    };
  });
  return {
    ...profile,
    available_widgets: availableWidgets,
    active_widgets: availableWidgets.filter((widget) => widget.is_visible).map((widget) => widget.key),
    hidden_widgets: availableWidgets.filter((widget) => !widget.is_visible).map((widget) => widget.key),
  };
}

function metricValue(value: string | number | null | undefined) {
  return value === undefined || value === null ? "..." : String(value);
}

function clampPercentage(value: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function ratioPercentage(value: number, total: number) {
  return Number.isFinite(value) && Number.isFinite(total) && total > 0
    ? clampPercentage((value / total) * 100)
    : 0;
}

function DashboardMetric({
  label,
  value,
  href,
  hint,
}: {
  label: string;
  value: ReactNode;
  href?: string;
  hint?: string;
}) {
  const content = (
    <>
      <span className="dashboard-metric-copy">
        <span className="stat-label">{label}</span>
        {hint ? <span className="dashboard-metric-hint">{hint}</span> : null}
      </span>
      <span className="stat-value">{value}</span>
      {href ? <span className="dashboard-metric-arrow" aria-hidden="true">→</span> : null}
    </>
  );
  if (href) {
    return <Link className="module-stat" href={href}>{content}</Link>;
  }
  return <div className="module-stat">{content}</div>;
}

function WidgetCard({
  title,
  category,
  description,
  children,
  testId,
  highlight = false,
}: {
  title: string;
  category: string;
  description?: string;
  children: ReactNode;
  testId: string;
  highlight?: boolean;
}) {
  return (
    <article className={`module-card${highlight ? " module-card-highlight" : ""}`} data-testid={testId}>
      <div className="module-head">
        <div>
          <span className="dashboard-widget-category">{category}</span>
          <h2>{title}</h2>
          {description ? <p className="dashboard-widget-description">{description}</p> : null}
        </div>
        <span className="dashboard-widget-status" aria-hidden="true" />
      </div>
      <div className="module-stats">{children}</div>
    </article>
  );
}

function ExecutiveMetric({
  label,
  value,
  context,
  percentage,
  tone = "green",
  href,
}: {
  label: string;
  value: ReactNode;
  context: string;
  percentage: number;
  tone?: "green" | "blue" | "amber" | "red";
  href: string;
}) {
  return (
    <Link className={`executive-metric executive-metric-${tone}`} href={href}>
      <span className="executive-metric-topline">
        <span className="executive-metric-label">{label}</span>
        <span className="executive-metric-link" aria-hidden="true">↗</span>
      </span>
      <strong>{value}</strong>
      <span className="executive-metric-context">{context}</span>
      <span className="executive-progress" aria-hidden="true">
        <span style={{ width: `${clampPercentage(percentage)}%` }} />
      </span>
    </Link>
  );
}

function ExecutiveDashboard({
  dashboard,
  isLoading,
  operationalMode,
  canViewFinance,
}: {
  dashboard: DashboardPayload | null;
  isLoading: boolean;
  operationalMode: OperationalMode | null;
  canViewFinance: boolean;
}) {
  const campaigns = dashboard?.campaigns;
  const bookings = dashboard?.bookings;
  const billing = dashboard?.billing;
  const campaignHealth = campaigns
    ? clampPercentage(100 - ratioPercentage(campaigns.campaigns_at_risk, campaigns.active_campaigns))
    : 0;
  const deliveryCoverage = bookings
    ? ratioPercentage(campaigns?.approved_assets ?? 0, bookings.total_bookings)
    : 0;
  const bookingMomentum = bookings ? ratioPercentage(bookings.live_bookings, bookings.total_bookings) : 0;
  const collectionEfficiency = clampPercentage(billing?.collection_efficiency_percentage ?? 0);
  const attentionItems = [
    {
      label: "Critical campaigns",
      value: campaigns?.critical_campaigns ?? 0,
      detail: "Require leadership attention",
      href: "/campaigns",
      tone: "critical",
    },
    {
      label: "Campaigns at risk",
      value: campaigns?.campaigns_at_risk ?? 0,
      detail: "POE or billing pressure",
      href: "/campaigns",
      tone: "warning",
    },
    {
      label: "Pending bookings",
      value: bookings?.pending_bookings ?? 0,
      detail: "Awaiting confirmation",
      href: "/bookings",
      tone: "neutral",
    },
    ...(canViewFinance
      ? [{
          label: "Overdue invoices",
          value: billing?.overdue_invoices ?? 0,
          detail: formatCurrency(billing?.overdue_amount ?? "0.00"),
          href: "/billing?invoiceStatus=overdue",
          tone: "critical",
        }]
      : []),
  ];

  return (
    <section className="executive-dashboard" data-testid="admin-executive-dashboard">
      <div className="executive-hero">
        <div className="executive-hero-copy">
          <span className="executive-kicker">Executive command center</span>
          <h2>Your business, in one decisive view.</h2>
          <p>Portfolio health, delivery momentum, financial control, and immediate priorities across OMMS.</p>
        </div>
        <div className="executive-hero-status">
          <span className="live-indicator"><span aria-hidden="true" /> Live portfolio</span>
          <strong>{operationalMode?.label ?? "Normal operations"}</strong>
          <small>Current environment mode</small>
        </div>
      </div>

      <div className="executive-metric-grid" aria-label="Executive performance indicators">
        <ExecutiveMetric
          label="Campaign health"
          value={isLoading ? "..." : `${campaignHealth}%`}
          context={`${campaigns?.active_campaigns ?? 0} active · ${campaigns?.campaigns_at_risk ?? 0} at risk`}
          percentage={campaignHealth}
          href="/campaigns"
        />
        <ExecutiveMetric
          label="Live execution"
          value={isLoading ? "..." : bookings?.live_bookings ?? 0}
          context={`${bookings?.total_bookings ?? 0} total bookings`}
          percentage={bookingMomentum}
          tone="blue"
          href="/bookings"
        />
        <ExecutiveMetric
          label="POE coverage"
          value={isLoading ? "..." : `${deliveryCoverage}%`}
          context={`${campaigns?.approved_assets ?? 0} approved proof assets`}
          percentage={deliveryCoverage}
          tone="amber"
          href="/poe"
        />
        {canViewFinance ? (
          <ExecutiveMetric
            label="Collection efficiency"
            value={isLoading ? "..." : `${collectionEfficiency}%`}
            context={`${formatCurrency(billing?.outstanding_balance ?? "0.00")} outstanding`}
            percentage={collectionEfficiency}
            tone={collectionEfficiency < 60 ? "red" : "green"}
            href="/billing"
          />
        ) : (
          <ExecutiveMetric
            label="Active portfolio"
            value={isLoading ? "..." : formatCurrency(campaigns?.active_budget ?? "0.00")}
            context={`${campaigns?.active_campaigns ?? 0} campaigns in market`}
            percentage={ratioPercentage(campaigns?.active_campaigns ?? 0, campaigns?.total_campaigns ?? 0)}
            href="/campaigns"
          />
        )}
      </div>

      <div className="executive-insight-grid">
        <article className="executive-insight-panel">
          <div className="executive-panel-heading">
            <div>
              <span>Portfolio momentum</span>
              <h3>Performance at a glance</h3>
            </div>
            <Link href="/operations">View intelligence</Link>
          </div>
          <div className="executive-performance-list">
            <div>
              <span><strong>Campaign health</strong><em>{campaignHealth}%</em></span>
              <span className="executive-bar"><span style={{ width: `${campaignHealth}%` }} /></span>
            </div>
            <div>
              <span><strong>Live booking share</strong><em>{bookingMomentum}%</em></span>
              <span className="executive-bar executive-bar-blue"><span style={{ width: `${bookingMomentum}%` }} /></span>
            </div>
            <div>
              <span><strong>Proof coverage</strong><em>{deliveryCoverage}%</em></span>
              <span className="executive-bar executive-bar-amber"><span style={{ width: `${deliveryCoverage}%` }} /></span>
            </div>
            {canViewFinance ? (
              <div>
                <span><strong>Collections</strong><em>{collectionEfficiency}%</em></span>
                <span className="executive-bar"><span style={{ width: `${collectionEfficiency}%` }} /></span>
              </div>
            ) : null}
          </div>
        </article>

        <article className="executive-insight-panel executive-attention-panel">
          <div className="executive-panel-heading">
            <div>
              <span>Command priorities</span>
              <h3>What needs attention</h3>
            </div>
            <span className="executive-priority-count">{attentionItems.reduce((total, item) => total + item.value, 0)}</span>
          </div>
          <div className="executive-priority-list">
            {attentionItems.map((item) => (
              <Link href={item.href} key={item.label}>
                <span className={`priority-dot priority-dot-${item.tone}`} aria-hidden="true" />
                <span><strong>{item.label}</strong><small>{item.detail}</small></span>
                <b>{isLoading ? "..." : item.value}</b>
              </Link>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

const dashboardWidgetRegistry: Record<string, WidgetDefinition> = {
  operational_health: {
    requiresOperations: true,
    render: ({ operationalMode }) => (
      <WidgetCard title="Operational health" category="Operations" testId="dashboard-widget-operational_health">
        <DashboardMetric label="Environment mode" value={operationalMode?.label ?? "Normal"} href="/operations" />
        <DashboardMetric label="Live jobs" value="Monitor" href="/operations" />
        <DashboardMetric label="Request health" value="Open" href="/operations" />
      </WidgetCard>
    ),
  },
  critical_campaigns: {
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Critical campaigns" category="Campaigns" testId="dashboard-widget-critical_campaigns">
        <DashboardMetric label="Critical" value={isLoading ? "..." : metricValue(dashboard?.campaigns.critical_campaigns ?? 0)} href="/campaigns" />
        <DashboardMetric label="At risk" value={isLoading ? "..." : metricValue(dashboard?.campaigns.campaigns_at_risk ?? 0)} href="/campaigns" />
        <DashboardMetric label="Ending soon" value={isLoading ? "..." : metricValue(dashboard?.campaigns.ending_soon_count ?? 0)} href="/campaigns" />
      </WidgetCard>
    ),
  },
  billing_risk: {
    requiresFinance: true,
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Billing risk" category="Finance" testId="dashboard-widget-billing_risk" highlight>
        <DashboardMetric label="Outstanding" value={isLoading ? "..." : formatCurrency(dashboard?.billing?.outstanding_amount ?? "0.00")} href="/billing" />
        <DashboardMetric label="Overdue amount" value={isLoading ? "..." : formatCurrency(dashboard?.billing?.overdue_amount ?? "0.00")} href="/billing?invoiceStatus=overdue" />
        <DashboardMetric label="Overdue invoices" value={isLoading ? "..." : metricValue(dashboard?.billing?.overdue_invoices ?? 0)} href="/billing?invoiceStatus=overdue" />
      </WidgetCard>
    ),
  },
  alerts: {
    requiresOperations: true,
    render: () => (
      <WidgetCard title="Alerts" category="Operations" testId="dashboard-widget-alerts">
        <DashboardMetric label="Active alerts" value="Review" href="/operations" />
        <DashboardMetric label="Thresholds" value="Open" href="/operations" />
        <DashboardMetric label="Notifications" value="Inbox" href="/notifications" />
      </WidgetCard>
    ),
  },
  campaign_performance: {
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Campaign performance" category="Campaigns" testId="dashboard-widget-campaign_performance">
        <DashboardMetric label="Active campaigns" value={isLoading ? "..." : metricValue(dashboard?.campaigns.active_campaigns ?? 0)} href="/campaigns" />
        <DashboardMetric label="Active budget" value={isLoading ? "..." : formatCurrency(dashboard?.campaigns.active_budget ?? "0.00")} href="/campaigns" />
        <DashboardMetric label="Approved assets" value={isLoading ? "..." : metricValue(dashboard?.campaigns.approved_assets ?? 0)} href="/campaigns" />
      </WidgetCard>
    ),
  },
  poe_sla: {
    render: () => (
      <WidgetCard title="POE SLA" category="POE" testId="dashboard-widget-poe_sla">
        <DashboardMetric label="Review queue" value="Open" href="/poe" />
        <DashboardMetric label="SLA risk" value="Monitor" href="/operations" />
        <DashboardMetric label="Suspicious proofs" value="Review" href="/poe" />
      </WidgetCard>
    ),
  },
  reviewer_workload: {
    requiresOperations: true,
    render: () => (
      <WidgetCard title="Reviewer workload" category="POE" testId="dashboard-widget-reviewer_workload">
        <DashboardMetric label="Workload" value="Open" href="/operations" />
        <DashboardMetric label="Unassigned" value="Review" href="/operations" />
        <DashboardMetric label="Breaches" value="Monitor" href="/operations" />
      </WidgetCard>
    ),
  },
  import_export_jobs: {
    requiresOperations: true,
    render: () => (
      <WidgetCard title="Import/export jobs" category="Operations" testId="dashboard-widget-import_export_jobs">
        <DashboardMetric label="Job history" value="Open" href="/operations" />
        <DashboardMetric label="Failed jobs" value="Retry" href="/operations" />
        <DashboardMetric label="Exports" value="Download" href="/operations" />
      </WidgetCard>
    ),
  },
  overdue_invoices: {
    requiresFinance: true,
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Overdue invoices" category="Finance" testId="dashboard-widget-overdue_invoices" highlight>
        <DashboardMetric label="Count" value={isLoading ? "..." : metricValue(dashboard?.billing?.overdue_invoices ?? 0)} href="/billing?invoiceStatus=overdue" />
        <DashboardMetric label="Value" value={isLoading ? "..." : formatCurrency(dashboard?.billing?.overdue_amount ?? "0.00")} href="/billing?invoiceStatus=overdue" />
        <DashboardMetric label="Due soon" value={isLoading ? "..." : metricValue(dashboard?.billing?.due_soon_invoices ?? 0)} href="/billing?invoiceStatus=due_soon" />
      </WidgetCard>
    ),
  },
  collection_efficiency: {
    requiresFinance: true,
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Collection efficiency" category="Finance" testId="dashboard-widget-collection_efficiency" highlight>
        <DashboardMetric label="Efficiency" value={isLoading ? "..." : `${dashboard?.billing?.collection_efficiency_percentage ?? 0}%`} href="/billing" />
        <DashboardMetric label="Collected" value={isLoading ? "..." : formatCurrency(dashboard?.billing?.total_collected ?? "0.00")} href="/billing" />
        <DashboardMetric label="Pending" value={isLoading ? "..." : formatCurrency(dashboard?.billing?.outstanding_balance ?? "0.00")} href="/billing" />
      </WidgetCard>
    ),
  },
  invoice_payment_trend: {
    requiresFinance: true,
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Invoice/payment trend" category="Finance" testId="dashboard-widget-invoice_payment_trend" highlight>
        <DashboardMetric label="Invoices" value={isLoading ? "..." : metricValue(dashboard?.billing?.total_invoices ?? 0)} href="/billing" />
        <DashboardMetric label="Payments" value={isLoading ? "..." : metricValue(dashboard?.billing?.payment_count ?? 0)} href="/billing?payments=this_month" />
        <DashboardMetric label="This month" value={isLoading ? "..." : formatCurrency(dashboard?.billing?.payments_received_this_month ?? "0.00")} href="/billing?payments=this_month" />
      </WidgetCard>
    ),
  },
  billing_alerts: {
    requiresFinance: true,
    render: () => (
      <WidgetCard title="Billing alerts" category="Finance" testId="dashboard-widget-billing_alerts" highlight>
        <DashboardMetric label="Finance alerts" value="Open" href="/notifications" />
        <DashboardMetric label="Overdue rules" value="Review" href="/operations" />
        <DashboardMetric label="Payment risk" value="Monitor" href="/billing" />
      </WidgetCard>
    ),
  },
  assigned_work: {
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Assigned work" category="Field" testId="dashboard-widget-assigned_work">
        <DashboardMetric label="Live bookings" value={isLoading ? "..." : metricValue(dashboard?.bookings.live_bookings ?? 0)} href="/poe/capture" />
        <DashboardMetric label="Confirmed" value={isLoading ? "..." : metricValue(dashboard?.bookings.confirmed_bookings ?? 0)} href="/bookings" />
        <DashboardMetric label="Media units" value={isLoading ? "..." : metricValue(dashboard?.bookings.unique_media_units ?? 0)} href="/inventory" />
      </WidgetCard>
    ),
  },
  pending_poe_uploads: {
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Pending POE uploads" category="Field" testId="dashboard-widget-pending_poe_uploads">
        <DashboardMetric label="Pending bookings" value={isLoading ? "..." : metricValue(dashboard?.bookings.pending_bookings ?? 0)} href="/poe/capture" />
        <DashboardMetric label="Capture" value="Open" href="/poe/capture" />
        <DashboardMetric label="POE queue" value="Review" href="/poe" />
      </WidgetCard>
    ),
  },
  upload_status: {
    render: () => (
      <WidgetCard title="Upload status" category="Field" testId="dashboard-widget-upload_status">
        <DashboardMetric label="Capture status" value="Open" href="/poe/capture" />
        <DashboardMetric label="Recent uploads" value="Review" href="/poe" />
        <DashboardMetric label="Rework" value="Check" href="/poe" />
      </WidgetCard>
    ),
  },
  site_task_alerts: {
    render: () => (
      <WidgetCard title="Site/task alerts" category="Field" testId="dashboard-widget-site_task_alerts">
        <DashboardMetric label="Task alerts" value="Inbox" href="/notifications" />
        <DashboardMetric label="Bookings" value="Open" href="/bookings" />
        <DashboardMetric label="Issues" value="Review" href="/operations" />
      </WidgetCard>
    ),
  },
  client_campaign_status: {
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Campaign status" category="Client" testId="dashboard-widget-client_campaign_status">
        <DashboardMetric label="Total campaigns" value={isLoading ? "..." : metricValue(dashboard?.campaigns.total_campaigns ?? 0)} href="/campaigns" />
        <DashboardMetric label="Active campaigns" value={isLoading ? "..." : metricValue(dashboard?.campaigns.active_campaigns ?? 0)} href="/campaigns" />
        <DashboardMetric label="Approved assets" value={isLoading ? "..." : metricValue(dashboard?.campaigns.approved_assets ?? 0)} href="/campaigns" />
      </WidgetCard>
    ),
  },
  approved_poes: {
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Approved POEs" category="Client" testId="dashboard-widget-approved_poes">
        <DashboardMetric label="Approved assets" value={isLoading ? "..." : metricValue(dashboard?.campaigns.approved_assets ?? 0)} href="/poe" />
        <DashboardMetric label="Proof gallery" value="Open" href="/poe" />
        <DashboardMetric label="Campaign evidence" value="Review" href="/campaigns" />
      </WidgetCard>
    ),
  },
  client_invoices: {
    requiresFinance: true,
    render: ({ dashboard, isLoading }) => (
      <WidgetCard title="Invoices/statements" category="Client" testId="dashboard-widget-client_invoices" highlight>
        <DashboardMetric label="Invoices" value={isLoading ? "..." : metricValue(dashboard?.billing?.total_invoices ?? 0)} href="/billing" />
        <DashboardMetric label="Outstanding" value={isLoading ? "..." : formatCurrency(dashboard?.billing?.outstanding_amount ?? "0.00")} href="/billing" />
        <DashboardMetric label="Statements" value="Open" href="/billing" />
      </WidgetCard>
    ),
  },
};

function canRenderWidget(widget: DashboardWidget, profile: DashboardProfile) {
  const definition = dashboardWidgetRegistry[widget.key];
  if (!definition || !widget.is_visible || !profile.active_widgets.includes(widget.key)) {
    return false;
  }
  if (definition.requiresFinance && !profile.can_view_finance) {
    return false;
  }
  if (definition.requiresOperations && !profile.can_view_operations) {
    return false;
  }
  return true;
}

function getRenderableWidgets(profile: DashboardProfile | null) {
  if (!profile) {
    return [];
  }
  return profile.available_widgets
    .filter((widget) => canRenderWidget(widget, profile))
    .sort((a, b) => a.sort_order - b.sort_order || a.label.localeCompare(b.label));
}

function renderDashboardWidget(widget: DashboardWidget, context: WidgetContext) {
  return dashboardWidgetRegistry[widget.key]?.render(context) ?? null;
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [profile, setProfile] = useState<DashboardProfile | null>(null);
  const [operationalMode, setOperationalMode] = useState<OperationalMode | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  async function refreshDashboardForProfile(nextProfile: DashboardProfile) {
    setProfile(nextProfile);
    const summaries = await fetchDashboardData({
      includeBilling: nextProfile.can_view_finance && profileHasVisibleFinanceWidgets(nextProfile),
    });
    setDashboard(summaries);
  }

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
        const mode = await fetchOperationalMode().catch(() => null);
        setProfile(dashboardProfile);
        setOperationalMode(mode);
        const summaries = await fetchDashboardData({
          includeBilling: dashboardProfile.can_view_finance && profileHasVisibleFinanceWidgets(dashboardProfile),
        });
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

  const renderableWidgets = useMemo(() => getRenderableWidgets(profile), [profile]);
  const isExecutiveAdmin = useMemo(() => {
    const role = (profile?.role ?? user?.role ?? "").toLowerCase();
    return ["admin", "owner", "super_admin", "platform_admin", "company_admin"].includes(role);
  }, [profile?.role, user?.role]);

  async function handleWidgetToggle(widgetKey: string, isVisible: boolean) {
    if (!profile?.can_customize) {
      return;
    }
    const previousProfile = profile;
    setIsSavingProfile(true);
    setError("");
    setMessage("");
    try {
      const nextWidgets = profile.available_widgets.map((widget) => ({
        widget_key: widget.key,
        is_visible: widget.key === widgetKey ? isVisible : widget.is_visible,
        sort_order: widget.sort_order,
      }));
      setProfile(applyWidgetVisibility(profile, nextWidgets));
      const nextProfile = await updateDashboardProfile(nextWidgets);
      await refreshDashboardForProfile(nextProfile);
      setMessage("Dashboard preference saved.");
    } catch (saveError) {
      setProfile(previousProfile);
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
      const nextProfile = await restoreDashboardProfileDefaults();
      await refreshDashboardForProfile(nextProfile);
      setMessage("Dashboard defaults restored.");
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Unable to restore dashboard defaults.");
    } finally {
      setIsSavingProfile(false);
    }
  }

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  return (
    <AppShell
      active="dashboard"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      eyebrow="OMMS intelligence"
      title={isExecutiveAdmin ? "Executive overview" : "Dashboard overview"}
      description={headline}
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}
      {message ? <p className="success">{message}</p> : null}

      {isExecutiveAdmin && profile ? (
        <ExecutiveDashboard
          dashboard={dashboard}
          isLoading={isLoading}
          operationalMode={operationalMode}
          canViewFinance={profile.can_view_finance && profileHasVisibleFinanceWidgets(profile)}
        />
      ) : null}

      <div className="dashboard-section-heading">
        <div>
          <span>Role workspace</span>
          <h2>Your operational modules</h2>
          <p>Focused views arranged around your responsibilities and saved dashboard preferences.</p>
        </div>
        <span className="dashboard-section-count">{renderableWidgets.length} active</span>
      </div>

      <section className="module-grid" data-testid="dashboard-widget-grid">
        {renderableWidgets.map((widget) => (
          <div className="dashboard-widget-slot" key={widget.key} data-testid={`dashboard-widget-slot-${widget.key}`}>
            {profile ? renderDashboardWidget(widget, { dashboard, isLoading, profile, operationalMode }) : null}
          </div>
        ))}
      </section>

      {!isLoading && profile && !renderableWidgets.length ? (
        <p className="empty-state">No dashboard widgets are currently visible. Restore defaults or enable a widget to rebuild this view.</p>
      ) : null}

      {profile?.can_customize ? (
        <details className="module-card dashboard-customize">
          <summary>
            <span>
              <strong>Customize dashboard</strong>
              <small>Choose the operational modules that matter to you</small>
            </span>
            <span className="dashboard-customize-action">Manage widgets</span>
          </summary>
          <div className="dashboard-customize-content">
            <div className="module-head">
              <div>
                <h2>Dashboard modules</h2>
                <p className="site-copy">Role defaults protect required views. Optional modules can be hidden at any time.</p>
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
                    <small>{widget.category} · {widget.description}{widget.is_required ? " · Required" : ""}</small>
                  </span>
                </label>
              ))}
            </div>
          </div>
        </details>
      ) : null}
    </AppShell>
  );
}
