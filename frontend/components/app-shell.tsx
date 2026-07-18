"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";

import { GlobalOperationalSearch } from "@/components/global-operational-search";
import { getAccessToken, getStoredUser } from "@/lib/auth";
import { fetchOperationalMode, type OperationalMode } from "@/lib/environment";

type AppShellProps = {
  active:
    | "dashboard"
    | "inventory"
    | "campaigns"
    | "bookings"
    | "billing"
    | "poe"
    | "notifications"
    | "operations"
    | "proposals"
    | "team"
    | "training"
    | "setup";
  roleLabel: string;
  userEmail: string;
  title: string;
  eyebrow?: string;
  description: string;
  hideWorkspaceHeader?: boolean;
  onLogout: () => void;
  children: ReactNode;
};

export function AppShell({
  active,
  roleLabel,
  userEmail,
  title,
  eyebrow = "Live summary",
  description,
  hideWorkspaceHeader = false,
  onLogout,
  children,
}: AppShellProps) {
  const [operationalMode, setOperationalMode] = useState<OperationalMode | null>(null);
  const [canManageTeam, setCanManageTeam] = useState(roleLabel === "admin");
  const [currentRole, setCurrentRole] = useState(roleLabel);

  useEffect(() => {
    if (!getAccessToken()) {
      return;
    }
    const storedUser = getStoredUser();
    setCurrentRole(storedUser?.role ?? roleLabel);
    setCanManageTeam(Boolean(storedUser?.is_platform_admin || storedUser?.is_company_admin || storedUser?.role === "admin"));
    let isMounted = true;
    fetchOperationalMode()
      .then((mode) => {
        if (isMounted) {
          setOperationalMode(mode);
        }
      })
      .catch(() => {
        if (isMounted) {
          setOperationalMode(null);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [roleLabel]);

  const specialistNavigation: Record<string, Set<AppShellProps["active"]>> = {
    poe_reviewer: new Set(["dashboard", "inventory", "campaigns", "bookings", "poe", "notifications", "training"]),
    inventory_manager: new Set(["dashboard", "inventory", "campaigns", "bookings", "notifications", "training"]),
  };
  const canShowNavigation = (key: AppShellProps["active"]) => specialistNavigation[currentRole]?.has(key) ?? true;
  const canUsePlanner = ["admin", "sales", "operations", "finance"].includes(currentRole);

  const showModeBanner = operationalMode && operationalMode.mode !== "normal";
  const modeBannerClass = operationalMode?.mode === "degraded" ? "mode-banner mode-banner-warning" : "mode-banner";

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div>
          <span className="eyebrow sidebar-eyebrow">OMMS Control</span>
          <h2 className="sidebar-title">Operations cockpit</h2>
          <p className="sidebar-copy">
            One shared surface for sales, operations, finance, and client reporting.
          </p>
        </div>

        <nav className="sidebar-nav" aria-label="Primary">
          <Link data-testid="sidebar-dashboard" className={`nav-item ${active === "dashboard" ? "nav-item-active" : ""}`} href="/dashboard">
            Dashboard
          </Link>
          {canShowNavigation("inventory") ? <Link data-testid="sidebar-inventory" className={`nav-item ${active === "inventory" ? "nav-item-active" : ""}`} href="/inventory">
            Inventory
          </Link> : null}
          {canShowNavigation("campaigns") ? <Link data-testid="sidebar-campaigns" className={`nav-item ${active === "campaigns" ? "nav-item-active" : ""}`} href="/campaigns">
            Campaigns
          </Link> : null}
          {canUsePlanner ? <Link data-testid="sidebar-proposals" className={`nav-item ${active === "proposals" ? "nav-item-active" : ""}`} href="/sales/proposals">
            Media proposals
          </Link> : null}
          {canShowNavigation("bookings") ? <Link data-testid="sidebar-bookings" className={`nav-item ${active === "bookings" ? "nav-item-active" : ""}`} href="/bookings">
            Bookings
          </Link> : null}
          {canShowNavigation("poe") ? <Link data-testid="sidebar-poe" className={`nav-item ${active === "poe" ? "nav-item-active" : ""}`} href="/poe">
            POE
          </Link> : null}
          {canShowNavigation("billing") ? <Link data-testid="sidebar-billing" className={`nav-item ${active === "billing" ? "nav-item-active" : ""}`} href="/billing">
            Billing
          </Link> : null}
          {canShowNavigation("notifications") ? <Link data-testid="sidebar-notifications" className={`nav-item ${active === "notifications" ? "nav-item-active" : ""}`} href="/notifications">
            Notifications
          </Link> : null}
          {canShowNavigation("operations") ? <Link data-testid="sidebar-operations" className={`nav-item ${active === "operations" ? "nav-item-active" : ""}`} href="/operations">
            Operations
          </Link> : null}
          {canManageTeam ? (
            <Link data-testid="sidebar-team" className={`nav-item ${active === "team" ? "nav-item-active" : ""}`} href="/settings/team">
              Team &amp; access
            </Link>
          ) : null}
          {canShowNavigation("training") ? <Link data-testid="sidebar-training" className={`nav-item ${active === "training" ? "nav-item-active" : ""}`} href="/training">
            Training
          </Link> : null}
          {canShowNavigation("setup") ? <Link data-testid="sidebar-setup" className={`nav-item ${active === "setup" ? "nav-item-active" : ""}`} href="/setup">
            Setup
          </Link> : null}
        </nav>

        <div className="sidebar-foot">
          <p className="sidebar-kicker">Signed in</p>
          <p className="sidebar-user">{userEmail}</p>
          {canManageTeam ? <Link className="sidebar-profile-link" href="/settings/team">Manage team access</Link> : null}
          <button className="ghost sidebar-button" type="button" onClick={onLogout}>
            Log out
          </button>
        </div>
      </aside>

      <section className="workspace">
        {showModeBanner ? (
          <div className={modeBannerClass} role="status">
            <strong>{operationalMode.label}</strong>
            <span>{operationalMode.message || (operationalMode.is_write_blocking ? "Changes are temporarily disabled." : "OMMS is operating with elevated caution.")}</span>
          </div>
        ) : null}

        {hideWorkspaceHeader ? null : (
          <header className="workspace-topbar">
            <div>
              <span className="eyebrow dashboard-eyebrow">{eyebrow}</span>
              <h1 className="workspace-title">{title}</h1>
              <p className="workspace-copy">{description}</p>
            </div>
            <div className="workspace-actions">
              <GlobalOperationalSearch />
              <div className="topbar-chip">
                <span className="topbar-chip-label">Role</span>
                <strong>{roleLabel}</strong>
              </div>
            </div>
          </header>
        )}

        {children}
      </section>
    </main>
  );
}
