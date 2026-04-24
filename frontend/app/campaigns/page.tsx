"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { CampaignShareCard } from "@/components/campaign-share-card";
import { ClientCreatePanel } from "@/components/client-create-panel";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  createCampaignAccessLink,
  fetchCampaignAccessLinks,
  getCachedCampaignShareLink,
  getCampaignAccessLinkStatus,
  getCampaignShareLinkError,
  revokeCampaignAccessLink,
  type CampaignAccessLink,
} from "@/lib/campaign-share-links";
import { createCampaign, fetchCampaignData, type CampaignCreateInput, type CampaignPayload } from "@/lib/campaigns";
import { formatCurrency } from "@/lib/dashboard";
import { fetchClients, fetchUsers, type ClientOption, type UserOption } from "@/lib/users";

type StoredUser = {
  id?: number;
  email?: string;
  role?: string;
};

const WRITE_ROLES = new Set(["admin", "sales"]);
const ADMIN_ROLES = new Set(["admin"]);

const INITIAL_FORM: CampaignCreateInput = {
  name: "",
  code: "",
  client: 0,
  account_manager: null,
  start_date: "",
  end_date: "",
  budget: "",
  status: "draft",
  objective: "",
};

function formatDateRange(startDate: string, endDate: string) {
  const formatter = new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return `${formatter.format(new Date(startDate))} - ${formatter.format(new Date(endDate))}`;
}

export default function CampaignsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [campaignData, setCampaignData] = useState<CampaignPayload | null>(null);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [managers, setManagers] = useState<UserOption[]>([]);
  const [accessLinks, setAccessLinks] = useState<CampaignAccessLink[]>([]);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [shareError, setShareError] = useState("");
  const [shareSuccess, setShareSuccess] = useState("");
  const [form, setForm] = useState<CampaignCreateInput>(INITIAL_FORM);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isShareLoading, setIsShareLoading] = useState(false);
  const [activeShareKey, setActiveShareKey] = useState<string | null>(null);

  const canManageCampaigns = WRITE_ROLES.has(user?.role ?? "");
  const canManageShareLinks = ADMIN_ROLES.has(user?.role ?? "");

  async function loadCampaigns(profileHint?: StoredUser | null) {
    setIsLoading(true);
    setError("");
    setIsShareLoading(true);

    try {
      const profile = profileHint ?? (await fetchCurrentUser());
      if (profile) {
        setUser(profile);
      }

      const [payload, directory, links] = await Promise.all([
        fetchCampaignData(),
        WRITE_ROLES.has(profile?.role ?? "") ? fetchClients() : Promise.resolve([]),
        ADMIN_ROLES.has(profile?.role ?? "") ? fetchCampaignAccessLinks() : Promise.resolve([]),
      ]);

      const managerDirectory = ADMIN_ROLES.has(profile?.role ?? "")
        ? await fetchUsers()
        : profile
          ? [
              {
                id: profile.id ?? 0,
                email: profile.email ?? "",
                username: profile.email ?? "",
                first_name: "",
                last_name: "",
                role: profile.role ?? "",
                organization_name: "",
              },
            ]
          : [];

      setCampaignData(payload);
      setClients(directory);
      setManagers(managerDirectory);
      setAccessLinks(links);

      if (directory.length > 0) {
        const firstClient = directory[0];
        const preferredManager =
          managerDirectory.find((entry) => entry.id === profile?.id) ??
          managerDirectory.find((entry) => entry.role === "admin" || entry.role === "sales") ??
          null;

        setForm((current) => ({
          ...current,
          client: current.client || firstClient?.id || 0,
          account_manager: current.account_manager ?? preferredManager?.id ?? null,
        }));
      }
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load campaigns.";
      setError(message);
      if (message.includes("sign in again")) {
        router.replace("/login");
      }
    } finally {
      setIsLoading(false);
      setIsShareLoading(false);
    }
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
    void loadCampaigns(storedUser);
  }, [router]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  const quickStats = useMemo(() => {
    if (!campaignData) {
      return [];
    }

    return [
      { label: "Total campaigns", value: String(campaignData.summary.total_campaigns) },
      { label: "Active campaigns", value: String(campaignData.summary.active_campaigns) },
      { label: "Live bookings", value: String(campaignData.summary.live_bookings) },
      { label: "Approved assets", value: String(campaignData.summary.approved_assets) },
    ];
  }, [campaignData]);

  const recentAssets = useMemo(() => {
    return (campaignData?.campaigns ?? [])
      .flatMap((campaign) =>
        campaign.assets.map((asset) => ({
          ...asset,
          campaignCode: campaign.code,
          campaignName: campaign.name,
        })),
      )
      .slice(0, 6);
  }, [campaignData]);

  const clientOptions = clients;
  const managerOptions = managers.filter((entry) => entry.role === "admin" || entry.role === "sales");
  const accessLinkMap = useMemo(() => {
    const grouped = new Map<number, CampaignAccessLink[]>();
    for (const link of accessLinks) {
      const items = grouped.get(link.campaign) ?? [];
      items.push(link);
      grouped.set(link.campaign, items);
    }
    return grouped;
  }, [accessLinks]);

  function updateForm<K extends keyof CampaignCreateInput>(field: K, value: CampaignCreateInput[K]) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleCreateCampaign(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");
    setFormSuccess("");
    setIsSubmitting(true);

    try {
      await createCampaign({
        ...form,
        budget: Number(form.budget).toFixed(2),
      });
      setFormSuccess("Campaign created successfully.");
      setForm({
        ...INITIAL_FORM,
        client: form.client,
        account_manager: form.account_manager,
        status: "draft",
      });
      await loadCampaigns(user);
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : "Unable to create campaign.";
      setFormError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleClientCreated(client: ClientOption) {
    const refreshedClients = await fetchClients();
    setClients(refreshedClients);
    setForm((current) => ({
      ...current,
      client: client.id,
    }));
  }

  function getPreferredAccessLink(campaignId: number, campaignEndDate: string): CampaignAccessLink | null {
    const links = [...(accessLinkMap.get(campaignId) ?? [])];
    if (links.length === 0) {
      return null;
    }

    const activeLink =
      links.find((link) => getCampaignAccessLinkStatus(link, campaignEndDate) === "active") ?? null;
    if (activeLink) {
      return activeLink;
    }

    return links[0] ?? null;
  }

  async function handleGenerateLink(campaignId: number) {
    if (activeShareKey) {
      return;
    }

    setShareError("");
    setShareSuccess("");
    setActiveShareKey(`generate-${campaignId}`);

    try {
      const link = await createCampaignAccessLink(campaignId);
      setAccessLinks((current) => [link, ...current]);
      setShareSuccess("Client share link generated successfully.");
    } catch (shareActionError) {
      setShareError(getCampaignShareLinkError(shareActionError));
    } finally {
      setActiveShareKey(null);
    }
  }

  async function handleCopyLink(url: string) {
    if (activeShareKey) {
      return;
    }

    setShareError("");
    setShareSuccess("");

    try {
      await navigator.clipboard.writeText(url);
      setShareSuccess("Client share link copied.");
    } catch {
      setShareError("Unable to copy the link automatically. You can still copy it from the field.");
    }
  }

  async function handleRevokeLink(link: CampaignAccessLink) {
    if (activeShareKey) {
      return;
    }

    const confirmed = window.confirm("Revoke this client share link? The public campaign page will stop working immediately.");
    if (!confirmed) {
      return;
    }

    setShareError("");
    setShareSuccess("");
    setActiveShareKey(`revoke-${link.id}`);

    try {
      const revoked = await revokeCampaignAccessLink(link.id);
      setAccessLinks((current) => current.map((item) => (item.id === revoked.id ? revoked : item)));
      setShareSuccess("Client share link revoked.");
    } catch (shareActionError) {
      setShareError(getCampaignShareLinkError(shareActionError));
    } finally {
      setActiveShareKey(null);
    }
  }

  return (
    <AppShell
      active="campaigns"
      roleLabel={user?.role ?? "Authenticated"}
      userEmail={user?.email ?? "Loading user..."}
      title="Campaign control"
      eyebrow="Campaigns"
      description="Track campaign timelines, budgets, assets, and booking readiness from one live workspace connected to the backend API."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}

      {canManageCampaigns ? (
        <section className="campaign-creation-stack">
          {canManageShareLinks ? <ClientCreatePanel onCreated={handleClientCreated} /> : null}
          <section className="module-card creation-panel">
            <div className="module-head">
              <h2>Create campaign</h2>
              <span>Write access</span>
            </div>
            <p className="section-copy creation-copy">
              Launch a new campaign directly from the browser. The record is saved to the backend and then refreshed into this roster.
            </p>
            {formError ? <p className="error">{formError}</p> : null}
            {formSuccess ? <p className="success">{formSuccess}</p> : null}
            <form className="campaign-form-grid" onSubmit={handleCreateCampaign}>
              <div className="field field-span-2">
                <label htmlFor="campaign-name">Campaign name</label>
                <input
                  id="campaign-name"
                  value={form.name}
                  onChange={(event) => updateForm("name", event.target.value)}
                  placeholder="Monsoon Reach Push"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="campaign-code">Campaign code</label>
                <input
                  id="campaign-code"
                  value={form.code}
                  onChange={(event) => updateForm("code", event.target.value.toUpperCase())}
                  placeholder="MONSOON-001"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="campaign-client">Client</label>
                <select
                  id="campaign-client"
                  value={form.client || ""}
                  onChange={(event) => updateForm("client", Number(event.target.value))}
                  required
                >
                  <option value="" disabled>
                    Select client
                  </option>
                  {clientOptions.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.organization_name || entry.email}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="campaign-manager">Account manager</label>
                <select
                  id="campaign-manager"
                  value={form.account_manager ?? ""}
                  onChange={(event) =>
                    updateForm("account_manager", event.target.value ? Number(event.target.value) : null)
                  }
                >
                  <option value="">Unassigned</option>
                  {managerOptions.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.first_name || entry.username || entry.email}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="campaign-start-date">Start date</label>
                <input
                  id="campaign-start-date"
                  type="date"
                  value={form.start_date}
                  onChange={(event) => updateForm("start_date", event.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="campaign-end-date">End date</label>
                <input
                  id="campaign-end-date"
                  type="date"
                  value={form.end_date}
                  onChange={(event) => updateForm("end_date", event.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="campaign-budget">Budget</label>
                <input
                  id="campaign-budget"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.budget}
                  onChange={(event) => updateForm("budget", event.target.value)}
                  placeholder="250000"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="campaign-status">Status</label>
                <select
                  id="campaign-status"
                  value={form.status}
                  onChange={(event) => updateForm("status", event.target.value)}
                >
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="paused">Paused</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
              <div className="field field-full">
                <label htmlFor="campaign-objective">Objective</label>
                <textarea
                  id="campaign-objective"
                  value={form.objective}
                  onChange={(event) => updateForm("objective", event.target.value)}
                  placeholder="Drive awareness in key commuter corridors."
                  rows={4}
                />
              </div>
              <div className="form-actions field-full">
                <button className="submit" type="submit" disabled={isSubmitting || isLoading}>
                  {isSubmitting ? "Creating campaign..." : "Create campaign"}
                </button>
              </div>
            </form>
          </section>
        </section>
      ) : null}

      {canManageShareLinks ? (
        <section className="campaign-share-section">
          <div className="module-head">
            <h2>Client share links</h2>
            <span>{campaignData?.campaigns.length ?? 0} campaigns</span>
          </div>
          {shareError ? <p className="error">{shareError}</p> : null}
          {shareSuccess ? <p className="success">{shareSuccess}</p> : null}
          <div className="campaign-share-grid">
            {(campaignData?.campaigns ?? []).map((campaign) => {
              const accessLink = getPreferredAccessLink(campaign.id, campaign.end_date);
              const accessLinkUrl = accessLink ? getCachedCampaignShareLink(accessLink.id) : null;
              const status = accessLink ? getCampaignAccessLinkStatus(accessLink, campaign.end_date) : null;
              const isActing =
                activeShareKey === `generate-${campaign.id}` ||
                (accessLink ? activeShareKey === `revoke-${accessLink.id}` : false);

              return (
                <CampaignShareCard
                  key={campaign.id}
                  campaign={campaign}
                  accessLink={accessLink}
                  accessLinkUrl={accessLinkUrl}
                  status={status}
                  isLoading={isShareLoading || isLoading}
                  isActing={isActing}
                  onGenerate={handleGenerateLink}
                  onCopy={handleCopyLink}
                  onRevoke={handleRevokeLink}
                />
              );
            })}
          </div>
          {!isLoading && (campaignData?.campaigns.length ?? 0) === 0 ? (
            <p className="empty-state">Create a campaign first to generate a secure client share link.</p>
          ) : null}
        </section>
      ) : null}

      <section className="summary-row" aria-label="Campaign stats">
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
            <h2>Budget overview</h2>
            <span>Finance</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Total budget</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(campaignData?.summary.total_budget ?? "0.00")}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Active budget</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(campaignData?.summary.active_budget ?? "0.00")}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Booked campaigns</p>
              <p className="stat-value">{isLoading ? "..." : campaignData?.summary.total_bookings ?? 0}</p>
            </div>
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Status mix</h2>
            <span>Delivery</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Draft</p>
              <p className="stat-value">{isLoading ? "..." : campaignData?.summary.draft_campaigns ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Active</p>
              <p className="stat-value">{isLoading ? "..." : campaignData?.summary.active_campaigns ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Completed</p>
              <p className="stat-value">
                {isLoading ? "..." : campaignData?.summary.completed_campaigns ?? 0}
              </p>
            </div>
          </div>
        </article>

        <article className="module-card module-card-highlight">
          <div className="module-head">
            <h2>Creative assets</h2>
            <span>Approval</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Recent assets</p>
              <p className="stat-value">{isLoading ? "..." : recentAssets.length}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Approved assets</p>
              <p className="stat-value">{isLoading ? "..." : campaignData?.summary.approved_assets ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Unapproved assets</p>
              <p className="stat-value">
                {isLoading
                  ? "..."
                  : Math.max(
                      (campaignData?.campaigns ?? []).reduce((count, campaign) => count + campaign.assets.length, 0) -
                        (campaignData?.summary.approved_assets ?? 0),
                      0,
                    )}
              </p>
            </div>
          </div>
        </article>
      </section>

      <section className="campaign-layout">
        <article className="module-card module-card-wide">
          <div className="module-head">
            <h2>Campaign roster</h2>
            <span>{campaignData?.campaigns.length ?? 0} items</span>
          </div>
          <div className="inventory-table-wrap">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Timeline</th>
                  <th>Status</th>
                  <th>Budget</th>
                  <th>Assets</th>
                  <th>Objective</th>
                </tr>
              </thead>
              <tbody>
                {(campaignData?.campaigns ?? []).map((campaign) => (
                  <tr key={campaign.id}>
                    <td>
                      <div className="table-primary">
                        <strong>{campaign.name}</strong>
                        <span>{campaign.code}</span>
                      </div>
                    </td>
                    <td>{formatDateRange(campaign.start_date, campaign.end_date)}</td>
                    <td>
                      <span className={`status-pill status-${campaign.status}`}>{campaign.status}</span>
                    </td>
                    <td>{formatCurrency(campaign.budget)}</td>
                    <td>{campaign.assets.length}</td>
                    <td className="table-wrap">{campaign.objective || "No objective added yet."}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!isLoading && (campaignData?.campaigns.length ?? 0) === 0 ? (
            <p className="empty-state">No campaigns are visible for the current account.</p>
          ) : null}
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Recent assets</h2>
            <span>Creative</span>
          </div>
          <div className="asset-list">
            {recentAssets.map((asset) => (
              <article className="asset-card" key={asset.id}>
                <div className="asset-head">
                  <div>
                    <p className="site-code">{asset.campaignCode}</p>
                    <h3>{asset.name}</h3>
                  </div>
                  <span className={`status-pill ${asset.is_approved ? "status-approved" : "status-draft"}`}>
                    {asset.is_approved ? "approved" : "pending"}
                  </span>
                </div>
                <p className="site-copy">{asset.campaignName}</p>
                <p className="site-copy">
                  {asset.asset_type} • {asset.version}
                </p>
                <a className="asset-link" href={asset.file_url} rel="noreferrer" target="_blank">
                  Open asset
                </a>
              </article>
            ))}
            {!isLoading && recentAssets.length === 0 ? (
              <p className="empty-state">No assets are available for the current campaign scope.</p>
            ) : null}
          </div>
        </article>
      </section>
    </AppShell>
  );
}
