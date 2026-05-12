"use client";

import Link from "next/link";
import { ReactNode } from "react";

type AppShellProps = {
  active: "dashboard" | "inventory" | "campaigns" | "bookings" | "billing" | "poe" | "notifications" | "operations" | "setup";
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
          <Link className={`nav-item ${active === "dashboard" ? "nav-item-active" : ""}`} href="/dashboard">
            Dashboard
          </Link>
          <Link className={`nav-item ${active === "inventory" ? "nav-item-active" : ""}`} href="/inventory">
            Inventory
          </Link>
          <Link className={`nav-item ${active === "campaigns" ? "nav-item-active" : ""}`} href="/campaigns">
            Campaigns
          </Link>
          <Link className={`nav-item ${active === "bookings" ? "nav-item-active" : ""}`} href="/bookings">
            Bookings
          </Link>
          <Link className={`nav-item ${active === "poe" ? "nav-item-active" : ""}`} href="/poe">
            POE
          </Link>
          <Link className={`nav-item ${active === "billing" ? "nav-item-active" : ""}`} href="/billing">
            Billing
          </Link>
          <Link className={`nav-item ${active === "notifications" ? "nav-item-active" : ""}`} href="/notifications">
            Notifications
          </Link>
          <Link className={`nav-item ${active === "operations" ? "nav-item-active" : ""}`} href="/operations">
            Operations
          </Link>
          <Link className={`nav-item ${active === "setup" ? "nav-item-active" : ""}`} href="/setup">
            Setup
          </Link>
        </nav>

        <div className="sidebar-foot">
          <p className="sidebar-kicker">Signed in</p>
          <p className="sidebar-user">{userEmail}</p>
          <button className="ghost sidebar-button" type="button" onClick={onLogout}>
            Log out
          </button>
        </div>
      </aside>

      <section className="workspace">
        {hideWorkspaceHeader ? null : (
          <header className="workspace-topbar">
            <div>
              <span className="eyebrow dashboard-eyebrow">{eyebrow}</span>
              <h1 className="workspace-title">{title}</h1>
              <p className="workspace-copy">{description}</p>
            </div>
            <div className="topbar-chip">
              <span className="topbar-chip-label">Role</span>
              <strong>{roleLabel}</strong>
            </div>
          </header>
        )}

        {children}
      </section>
    </main>
  );
}
