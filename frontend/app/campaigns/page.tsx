"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ClientCreatePanel } from "@/components/client-create-panel";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  createCampaignAccessLink,
  fetchCampaignAccessLinks,
  getCampaignAccessLinkUrl,
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

type CampaignRosterFilter = "all" | "ongoing" | "upcoming" | "ended";

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

  return `${formatter.format(new Date(`${startDate}T12:00:00`))} - ${formatter.format(new Date(`${endDate}T12:00:00`))}`;
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
  const [copyFeedback, setCopyFeedback] = useState<{ linkId: number; message: string; isError: boolean } | null>(null);
  const [form, setForm] = useState<CampaignCreateInput>(INITIAL_FORM);
  const [rosterFilter, setRosterFilter] = useState<CampaignRosterFilter>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isShareLoading, setIsShareLoading] = useState(false);
  const [activeShareKey, setActiveShareKey] = useState<string | null>(null);
  const shareActionInFlight = useRef(false);
  const copyFeedbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const canManageCampaigns = WRITE_ROLES.has(user?.role ?? "");
  const canManageShareLinks = ADMIN_ROLES.has(user?.role ?? "");

  function mergeAccessLink(nextLink: CampaignAccessLink) {
    setAccessLinks((current) => {
      const remaining = current.filter((item) => item.id !== nextLink.id && item.campaign !== nextLink.campaign);
      return [nextLink, ...remaining];
    });
  }

  const loadCampaigns = useCallback(async (profileHint?: StoredUser | null) => {
    setIsLoading(true);
    setError("");
    setIsShareLoading(true);
    setShareError("");

    try {
      const profile = profileHint ?? (await fetchCurrentUser());
      if (profile) {
        setUser(profile);
      }

      const [payload, directory] = await Promise.all([
        fetchCampaignData(),
        WRITE_ROLES.has(profile?.role ?? "") ? fetchClients() : Promise.resolve([]),
      ]);

      let links: CampaignAccessLink[] = [];
      if (ADMIN_ROLES.has(profile?.role ?? "")) {
        try {
          links = await fetchCampaignAccessLinks();
        } catch {
          setShareError("Share links are temporarily unavailable right now. Campaign data is still available.");
        }
      }

      let managerDirectory: UserOption[] =
        profile
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

      if (ADMIN_ROLES.has(profile?.role ?? "")) {
        try {
          managerDirectory = await fetchUsers();
        } catch {
          setFormError("Campaign managers are temporarily unavailable. You can still review campaign data.");
        }
      }

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
  }, [router]);

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
    return () => {
      if (copyFeedbackTimer.current) {
        clearTimeout(copyFeedbackTimer.current);
      }
    };
  }, [loadCampaigns, router]);

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
      { label: "Ongoing campaigns", value: String(campaignData.summary.active_campaigns) },
      { label: "Ending soon", value: String(campaignData.summary.ending_soon_count) },
      { label: "Campaigns at risk", value: String(campaignData.summary.campaigns_at_risk) },
      { label: "Critical campaigns", value: String(campaignData.summary.critical_campaigns) },
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
  const campaigns = useMemo(() => campaignData?.campaigns ?? [], [campaignData?.campaigns]);
  const filteredCampaigns = useMemo(() => {
    const visible = rosterFilter === "all"
      ? campaigns
      : campaigns.filter((campaign) => campaign.effective_status === rosterFilter);
    return [...visible].sort((left, right) => {
      const createdDifference = new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
      if (createdDifference !== 0) {
        return createdDifference;
      }
      const startDifference = right.start_date.localeCompare(left.start_date);
      return startDifference || right.id - left.id;
    });
  }, [campaigns, rosterFilter]);

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
    try {
      const refreshedClients = await fetchClients();
      setClients(refreshedClients);
      setForm((current) => ({
        ...current,
        client: client.id,
      }));
    } catch (refreshError) {
      const message =
        refreshError instanceof Error
          ? refreshError.message
          : "The client was created, but the dropdown could not be refreshed automatically.";
      setFormError(message);
    }
  }

  function getPreferredAccessLink(campaignId: number): CampaignAccessLink | null {
    const links = [...(accessLinkMap.get(campaignId) ?? [])];
    if (links.length === 0) {
      return null;
    }

    const activeLink =
      links.find((link) => getCampaignAccessLinkStatus(link) === "active") ?? null;
    if (activeLink) {
      return activeLink;
    }

    return links[0] ?? null;
  }

  async function handleGenerateLink(campaignId: number) {
    if (shareActionInFlight.current) {
      return;
    }

    setShareError("");
    setShareSuccess("");
    shareActionInFlight.current = true;
    setActiveShareKey(`generate-${campaignId}`);

    try {
      const link = await createCampaignAccessLink(campaignId);
      mergeAccessLink(link);
      setShareSuccess("Client share link generated successfully.");
    } catch (shareActionError) {
      setShareError(getCampaignShareLinkError(shareActionError));
    } finally {
      shareActionInFlight.current = false;
      setActiveShareKey(null);
    }
  }

  async function handleCopyLink(url: string, linkId: number) {
    if (shareActionInFlight.current) {
      return;
    }

    const scrollPosition = window.scrollY;
    setCopyFeedback(null);
    shareActionInFlight.current = true;
    setActiveShareKey(`copy-${linkId}`);

    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API is not available.");
      }
      await navigator.clipboard.writeText(url);
      setCopyFeedback({ linkId, message: "Link copied", isError: false });
    } catch {
      setCopyFeedback({ linkId, message: "Copy failed. Please try again.", isError: true });
    } finally {
      shareActionInFlight.current = false;
      setActiveShareKey(null);
      window.requestAnimationFrame(() => window.scrollTo({ top: scrollPosition, behavior: "auto" }));
      if (copyFeedbackTimer.current) {
        clearTimeout(copyFeedbackTimer.current);
      }
      copyFeedbackTimer.current = setTimeout(() => setCopyFeedback(null), 2000);
    }
  }

  async function handleRevokeLink(link: CampaignAccessLink) {
    if (shareActionInFlight.current) {
      return;
    }

    const confirmed = window.confirm("Revoke this client share link? The public campaign page will stop working immediately.");
    if (!confirmed) {
      return;
    }

    setShareError("");
    setShareSuccess("");
    shareActionInFlight.current = true;
    setActiveShareKey(`revoke-${link.id}`);

    try {
      const revoked = await revokeCampaignAccessLink(link.id);
      setAccessLinks((current) => current.map((item) => (item.id === revoked.id ? revoked : item)));
      setShareSuccess("Client share link revoked.");
    } catch (shareActionError) {
      setShareError(getCampaignShareLinkError(shareActionError));
    } finally {
      shareActionInFlight.current = false;
      setActiveShareKey(null);
    }
  }

  return (
    <AppShell
      active="campaigns"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title="Campaign control"
      eyebrow="Campaigns"
      description="Track campaign timelines, budgets, assets, and booking readiness from one shared operations workspace."
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
              Launch a new campaign, assign ownership, and keep booking readiness visible for the operations team.
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
              <p className="stat-label">Ongoing</p>
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

      <section className="module-card campaign-roster-section">
        <div className="campaign-roster-header">
          <div>
            <span className="site-code">Operational portfolio</span>
            <h2>Campaign roster</h2>
            <p className="site-copy">One view for lifecycle, delivery, billing, sharing, and internal campaign access.</p>
          </div>
          <span className="campaign-roster-count">{filteredCampaigns.length} of {campaigns.length}</span>
        </div>

        <div className="campaign-roster-toolbar">
          <div className="campaign-filter-tabs" aria-label="Filter campaigns by lifecycle">
            {(["all", "ongoing", "upcoming", "ended"] as CampaignRosterFilter[]).map((filter) => (
              <button
                className={rosterFilter === filter ? "campaign-filter-active" : ""}
                key={filter}
                type="button"
                aria-pressed={rosterFilter === filter}
                onClick={() => setRosterFilter(filter)}
              >
                {filter === "all" ? "All" : filter[0].toUpperCase() + filter.slice(1)}
              </button>
            ))}
          </div>
          <div className="campaign-share-notice" aria-live="polite">
            {shareError ? <span className="campaign-inline-error">{shareError}</span> : null}
            {!shareError && shareSuccess ? <span>{shareSuccess}</span> : null}
          </div>
        </div>

        <div className="inventory-table-wrap campaign-roster-table-wrap">
          <table className="inventory-table campaign-roster-table">
            <thead>
              <tr>
                <th>Campaign</th>
                <th>Timeline</th>
                <th>Status</th>
                <th>Performance</th>
                <th>Budget</th>
                <th>Assets</th>
                <th>Billing</th>
                <th>Objective</th>
                <th>Share link</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredCampaigns.map((campaign) => {
                const accessLink = canManageShareLinks ? getPreferredAccessLink(campaign.id) : null;
                const accessLinkUrl = getCampaignAccessLinkUrl(accessLink);
                const linkStatus = accessLink ? getCampaignAccessLinkStatus(accessLink) : null;
                const isGenerating = activeShareKey === `generate-${campaign.id}`;
                const isCopying = Boolean(accessLink && activeShareKey === `copy-${accessLink.id}`);
                const isRevoking = Boolean(accessLink && activeShareKey === `revoke-${accessLink.id}`);
                const feedback = accessLink && copyFeedback?.linkId === accessLink.id ? copyFeedback : null;
                const approvedAssets = campaign.assets.filter((asset) => asset.is_approved).length;
                const billingVisible = campaign.performance?.billing_status !== "hidden";

                return (
                  <tr className={campaign.is_ended ? "campaign-row-ended" : ""} key={campaign.id}>
                    <td>
                      <div className="table-primary campaign-name-cell">
                        <strong>{campaign.name}</strong>
                        <span>{campaign.code}</span>
                      </div>
                    </td>
                    <td className="campaign-timeline-cell">{formatDateRange(campaign.start_date, campaign.end_date)}</td>
                    <td>
                      <span className={`status-pill status-${campaign.effective_status}`}>
                        {campaign.effective_status.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td>
                      <div className="campaign-performance-cell">
                        <strong>{campaign.performance?.poe_completion_percentage ?? 0}% POE</strong>
                        <span>{campaign.performance?.pending_poe_count ?? 0} pending</span>
                        <span className={`campaign-risk-label status-${campaign.performance?.risk_status ?? "on_track"}`}>
                          {(campaign.performance?.risk_status ?? "on_track").replaceAll("_", " ")}
                        </span>
                      </div>
                    </td>
                    <td className="campaign-value-cell">{formatCurrency(campaign.budget)}</td>
                    <td>
                      <div className="campaign-assets-cell">
                        <strong>{campaign.assets.length}</strong>
                        <span>{approvedAssets} approved</span>
                      </div>
                    </td>
                    <td>
                      {billingVisible ? (
                        <div className="campaign-billing-cell">
                          <strong>{(campaign.performance?.billing_status ?? "no_invoice").replaceAll("_", " ")}</strong>
                          <span>
                            {(campaign.performance?.overdue_amount ?? "0.00") !== "0.00"
                              ? `${formatCurrency(campaign.performance?.overdue_amount)} overdue`
                              : `${campaign.performance?.payment_completion_percentage ?? 0}% collected`}
                          </span>
                        </div>
                      ) : <span className="campaign-restricted-value">Restricted</span>}
                    </td>
                    <td>
                      <p className="campaign-objective-cell" title={campaign.objective || "No objective added yet."}>
                        {campaign.objective || "No objective added yet."}
                      </p>
                    </td>
                    <td>
                      {canManageShareLinks ? (
                        <div className="campaign-share-cell">
                          {campaign.is_ended || linkStatus === "ended" ? (
                            <span className="campaign-link-state">Campaign ended · public access closed</span>
                          ) : linkStatus === "active" && accessLink && accessLinkUrl ? (
                            <>
                              <span className="campaign-link-state">Active · {accessLink.token_prefix}...</span>
                              <div className="campaign-row-actions">
                                <button
                                  className="ghost table-action"
                                  type="button"
                                  disabled={isShareLoading || isCopying || isRevoking}
                                  onClick={() => void handleCopyLink(accessLinkUrl, accessLink.id)}
                                >
                                  {isCopying ? "Copying..." : "Copy"}
                                </button>
                                <button
                                  className="ghost ghost-danger table-action"
                                  type="button"
                                  disabled={isShareLoading || isCopying || isRevoking}
                                  onClick={() => void handleRevokeLink(accessLink)}
                                >
                                  {isRevoking ? "Revoking..." : "Revoke"}
                                </button>
                              </div>
                            </>
                          ) : linkStatus === "active" && accessLink ? (
                            <>
                              <span className="campaign-link-state">Link unavailable · regenerate securely</span>
                              <div className="campaign-row-actions">
                                <button
                                  className="ghost ghost-danger table-action"
                                  type="button"
                                  disabled={isShareLoading || isRevoking}
                                  onClick={() => void handleRevokeLink(accessLink)}
                                >
                                  {isRevoking ? "Revoking..." : "Revoke"}
                                </button>
                              </div>
                            </>
                          ) : (
                            <>
                              <span className="campaign-link-state">
                                {linkStatus === "revoked" ? "Revoked" : linkStatus === "expired" ? "Expired" : "Not generated"}
                              </span>
                              <button
                                className="ghost table-action"
                                type="button"
                                disabled={isShareLoading || isGenerating}
                                onClick={() => void handleGenerateLink(campaign.id)}
                              >
                                {isGenerating ? "Generating..." : linkStatus ? "Generate new" : "Generate link"}
                              </button>
                            </>
                          )}
                          <span className={`campaign-copy-feedback${feedback?.isError ? " campaign-copy-feedback-error" : ""}`} aria-live="polite">
                            {feedback?.message ?? "\u00a0"}
                          </span>
                        </div>
                      ) : <span className="campaign-restricted-value">Admin only</span>}
                    </td>
                    <td>
                      <Link
                        className="ghost table-action campaign-view-action"
                        href={`/campaigns/${campaign.id}`}
                        aria-label={`View ${campaign.name}`}
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!isLoading && filteredCampaigns.length === 0 ? (
          <p className="empty-state">
            {rosterFilter === "all" ? "No campaigns are visible for the current account." : `No ${rosterFilter} campaigns in this tenant.`}
          </p>
        ) : null}
      </section>
    </AppShell>
  );
}
