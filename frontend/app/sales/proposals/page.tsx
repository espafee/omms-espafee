"use client";

import Link from "next/link";
import { Fragment, FormEvent, MouseEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import {
  clearAuthSession,
  getAccessToken,
  getStoredUser,
  type AuthUser,
} from "@/lib/auth";
import {
  createPlannerLink,
  fetchPlannerLinkEligibility,
  fetchPlannerLinkEligibilityDiagnostics,
  fetchPlannerLinks,
  fetchPlannerProposals,
  revokePlannerLink,
  type PlannerEligibilityPreview,
  type PlannerLinkEligibilityDiagnostics,
  type PlannerLink,
  type PlannerProposal,
} from "@/lib/planner";
import { fetchTeamRoles, type TeamTenant } from "@/lib/team";

const DEFAULT_DIAGNOSTIC_UNITS = "ESPA-001,ESPA-002_1,ESPA-002_2,ESPA-003";
const TENANT_MISMATCH_MESSAGE = "Planner tenant does not match published inventory.";

const configuredPlannerOrigin =
  process.env.NEXT_PUBLIC_FRONTEND_ORIGIN ||
  process.env.NEXT_PUBLIC_APP_ORIGIN ||
  process.env.NEXT_PUBLIC_APP_URL ||
  process.env.NEXT_PUBLIC_SITE_URL ||
  "";

function copyWithTextareaFallback(value: string) {
  const textarea = document.createElement("textarea");
  const activeElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-1000px";
  textarea.style.left = "-1000px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
    activeElement?.focus();
  }
  return copied;
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // Fall back for browsers that expose the API but reject clipboard writes.
    }
  }
  if (!copyWithTextareaFallback(value)) {
    throw new Error("Clipboard copy failed.");
  }
}

function buildPlannerPublicUrl(publicPath?: string | null) {
  const path = publicPath?.trim();
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const rawOrigin = configuredPlannerOrigin || (typeof window !== "undefined" ? window.location.origin : "");
  const trimmedOrigin = rawOrigin.trim().replace(/\/+$/, "");
  const origin = trimmedOrigin && /^https?:\/\//i.test(trimmedOrigin) ? trimmedOrigin : trimmedOrigin ? `https://${trimmedOrigin}` : "";
  if (!origin) return normalizedPath;
  try {
    return new URL(normalizedPath, origin).toString();
  } catch {
    return normalizedPath;
  }
}

function isCopyablePlannerLink(link: PlannerLink) {
  if (!link.id || !link.is_available || link.revoked_at) return false;
  return !link.expires_at || new Date(link.expires_at).getTime() > Date.now();
}

function formatPlannerPricing(value: string) {
  if (value === "hidden") return "Rates hidden";
  if (value === "standard_selling_rate") return "Standard rates visible";
  if (value === "client_rate_card") return "Client rate card";
  return value.replaceAll("_", " ");
}

function formatPlannerDate(value?: string | null) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function getPlannerLinkStatus(link: PlannerLink) {
  if (link.revoked_at) return "revoked";
  if (link.expires_at && new Date(link.expires_at).getTime() <= Date.now()) return "expired";
  if (link.is_available) return "active";
  return "closed";
}

function hasTenantMismatch(report?: PlannerLinkEligibilityDiagnostics | null) {
  if (!report) return false;
  return (
    (report.link.eligible_count ?? 0) === 0 &&
    (report.pipeline.tenant_units ?? 0) === 0 &&
    (report.exclusions.wrong_tenant ?? 0) > 0
  );
}

export default function ProposalsWorkspacePage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [proposals, setProposals] = useState<PlannerProposal[]>([]);
  const [links, setLinks] = useState<PlannerLink[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedUrl, setGeneratedUrl] = useState("");
  const [generatedLink, setGeneratedLink] = useState<PlannerLink | null>(null);
  const [eligibilityPreview, setEligibilityPreview] =
    useState<PlannerEligibilityPreview | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [diagnosticsByLink, setDiagnosticsByLink] = useState<Record<number, PlannerLinkEligibilityDiagnostics>>({});
  const [activeDiagnostics, setActiveDiagnostics] = useState<PlannerLinkEligibilityDiagnostics | null>(null);
  const [diagnosticsFeedback, setDiagnosticsFeedback] = useState("");
  const [isDiagnosticsLoading, setIsDiagnosticsLoading] = useState(false);
  const [linkFeedback, setLinkFeedback] = useState("");
  const [copyFeedback, setCopyFeedback] = useState("");
  const [historyCopyFeedback, setHistoryCopyFeedback] = useState("");
  const [historyCopyError, setHistoryCopyError] = useState("");
  const [copiedPlannerLinkId, setCopiedPlannerLinkId] = useState<number | null>(null);
  const [copyingPlannerLinkId, setCopyingPlannerLinkId] = useState<number | null>(null);
  const [tenantOptions, setTenantOptions] = useState<TeamTenant[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState("");
  const [tenantFeedback, setTenantFeedback] = useState("");
  const historyCopyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const copyingPlannerLinkRef = useRef<number | null>(null);
  const isPlatformAdmin = Boolean(user?.is_platform_admin);
  const userCompanyName = user?.tenant_name || user?.organization_name || "Your company";
  const recentPlannerLinks = links.slice(0, 8);
  const showPlannerDateColumn = recentPlannerLinks.some((link) => Boolean(link.created_at));
  const plannerHistoryColumnCount = showPlannerDateColumn ? 6 : 5;

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [proposalRows, linkRows] = await Promise.all([
        fetchPlannerProposals(status ? { status } : {}),
        fetchPlannerLinks(),
      ]);
      setProposals(proposalRows);
      setLinks(linkRows);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load client proposals.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [status]);
  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    setUser(getStoredUser());
    void load();
  }, [load, router]);

  useEffect(() => {
    return () => {
      if (historyCopyTimer.current) {
        clearTimeout(historyCopyTimer.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!isPlatformAdmin || !links.length) {
      return;
    }
    let isMounted = true;
    void Promise.allSettled(
      links.slice(0, 8).map((link) =>
        fetchPlannerLinkEligibilityDiagnostics(link.id, { unit_code: DEFAULT_DIAGNOSTIC_UNITS }),
      ),
    ).then((results) => {
      if (!isMounted) return;
      const next: Record<number, PlannerLinkEligibilityDiagnostics> = {};
      results.forEach((result) => {
        if (result.status === "fulfilled") {
          next[result.value.link.id] = result.value;
        }
      });
      setDiagnosticsByLink(next);
    });
    return () => {
      isMounted = false;
    };
  }, [isPlatformAdmin, links]);

  useEffect(() => {
    if (!isPlatformAdmin) {
      setTenantOptions([]);
      setSelectedTenantId("");
      setTenantFeedback("");
      return;
    }
    let isMounted = true;
    setTenantFeedback("");
    void fetchTeamRoles()
      .then((directory) => {
        if (!isMounted) return;
        setTenantOptions(directory.tenants);
      })
      .catch((tenantError) => {
        if (!isMounted) return;
        setTenantFeedback(
          tenantError instanceof Error
            ? tenantError.message
            : "Unable to load company list.",
        );
      });
    return () => {
      isMounted = false;
    };
  }, [isPlatformAdmin]);

  async function generateLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isGenerating) return;
    if (isPlatformAdmin && !selectedTenantId) {
      setTenantFeedback("Select a company before generating a planner link.");
      return;
    }
    setIsGenerating(true);
    setError("");
    setLinkFeedback("");
    setCopyFeedback("");
    setTenantFeedback("");
    const form = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = {
      title: form.get("title"),
      pricing_mode: form.get("pricing_mode"),
      show_rates: form.get("pricing_mode") === "standard_selling_rate",
      allow_proposal_submission: true,
      allow_image_download: form.get("allow_image_download") === "on",
      allow_map_data: false,
      expires_at: form.get("expires_at") || null,
      allowed_cities: String(form.get("allowed_cities") || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
    };
    if (isPlatformAdmin) {
      payload.tenant = Number(selectedTenantId);
    }
    try {
      const link = await createPlannerLink(payload);
      const url = buildPlannerPublicUrl(link.public_path);
      setGeneratedUrl(url);
      setGeneratedLink(link);
      setLinkFeedback("Link generated");
      void loadEligibilityPreview(link.id);
      await load();
      setLinks((current) => [link, ...current.filter((item) => item.id !== link.id)]);
    } catch (createError) {
      setLinkFeedback("");
      setError(
        createError instanceof Error
          ? createError.message
          : "Unable to create media planner link.",
      );
    } finally {
      setIsGenerating(false);
    }
  }

  async function loadEligibilityPreview(linkId = generatedLink?.id) {
    if (!linkId) return;
    setIsPreviewLoading(true);
    try {
      setEligibilityPreview(await fetchPlannerLinkEligibility(linkId));
    } catch {
      setEligibilityPreview(null);
    } finally {
      setIsPreviewLoading(false);
    }
  }

  async function copyGeneratedLink() {
    if (!generatedUrl) return;
    setCopyFeedback("");
    try {
      await copyText(generatedUrl);
      setCopyFeedback("Link copied");
    } catch {
      setCopyFeedback("Unable to copy link. Select the URL and copy it manually.");
    }
  }

  async function copyPlannerHistoryLink(event: MouseEvent<HTMLButtonElement>, link: PlannerLink) {
    event.preventDefault();
    event.stopPropagation();
    if (!isCopyablePlannerLink(link) || copyingPlannerLinkRef.current === link.id) return;
    const url = buildPlannerPublicUrl(link.public_path);
    if (!url) {
      setHistoryCopyFeedback("");
      setHistoryCopyError("Unable to copy link. This planner link does not have a copyable public URL. Create a new planner link and try again.");
      return;
    }
    copyingPlannerLinkRef.current = link.id;
    setCopyingPlannerLinkId(link.id);
    setHistoryCopyFeedback("");
    setHistoryCopyError("");
    if (historyCopyTimer.current) {
      clearTimeout(historyCopyTimer.current);
    }
    try {
      await copyText(url);
      setCopiedPlannerLinkId(link.id);
      setHistoryCopyFeedback("Link copied");
      historyCopyTimer.current = setTimeout(() => {
        setCopiedPlannerLinkId((current) => (current === link.id ? null : current));
        setHistoryCopyFeedback("");
      }, 2000);
    } catch (copyError) {
      setCopiedPlannerLinkId(null);
      setHistoryCopyError("Unable to copy link. Please try again.");
      console.warn(
        "Planner link copy failed",
        copyError instanceof Error ? copyError.message : "Unknown clipboard failure",
      );
    } finally {
      if (copyingPlannerLinkRef.current === link.id) {
        copyingPlannerLinkRef.current = null;
        setCopyingPlannerLinkId((current) => (current === link.id ? null : current));
      }
    }
  }

  async function openDiagnostics(link: PlannerLink) {
    setDiagnosticsFeedback("");
    setIsDiagnosticsLoading(true);
    try {
      const report =
        diagnosticsByLink[link.id] ??
        (await fetchPlannerLinkEligibilityDiagnostics(link.id, { unit_code: DEFAULT_DIAGNOSTIC_UNITS }));
      setDiagnosticsByLink((current) => ({ ...current, [link.id]: report }));
      setActiveDiagnostics(report);
    } catch (diagnosticsError) {
      setDiagnosticsFeedback(
        diagnosticsError instanceof Error
          ? diagnosticsError.message
          : "Unable to load media planner diagnostics.",
      );
    } finally {
      setIsDiagnosticsLoading(false);
    }
  }

  async function copyDiagnosticsReport() {
    if (!activeDiagnostics) return;
    setDiagnosticsFeedback("");
    try {
      await copyText(JSON.stringify(activeDiagnostics, null, 2));
      setDiagnosticsFeedback("Diagnostic report copied");
    } catch {
      setDiagnosticsFeedback("Unable to copy diagnostic report. Select the JSON and copy it manually.");
    }
  }

  function logout() {
    clearAuthSession();
    router.replace("/login");
  }
  return (
    <AppShell
      active="proposals"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? ""}
      onLogout={logout}
      title="Client media proposals"
      description="Share controlled inventory, review client selections, and prepare formal estimates without reserving media prematurely."
    >
      <section className="planner-internal-grid">
        <article className="module-card planner-link-card">
          <div className="module-head">
            <div>
              <p className="site-code">LIVE MEDIA PLANNER</p>
              <h2>Create a secure client link</h2>
            </div>
          </div>
          <form className="planner-link-form" onSubmit={generateLink}>
            {isPlatformAdmin ? (
              <label className="field-full">
                <span>Select company</span>
                <select
                  name="tenant"
                  value={selectedTenantId}
                  required
                  onChange={(event) => setSelectedTenantId(event.target.value)}
                >
                  <option value="">Choose a client company</option>
                  {tenantOptions.map((tenant) => (
                    <option key={tenant.id} value={tenant.id}>
                      {tenant.name}
                    </option>
                  ))}
                </select>
                <small>Planner inventory will be scoped to this company.</small>
              </label>
            ) : (
              <div className="planner-company-context field-full">
                <span>Company</span>
                <strong>{userCompanyName}</strong>
              </div>
            )}
            <label>
              <span>Link title</span>
              <input name="title" defaultValue="Live Media Planner" required />
            </label>
            <label>
              <span>Pricing visibility</span>
              <select name="pricing_mode" defaultValue="hidden">
                <option value="hidden">Rates hidden</option>
                <option value="standard_selling_rate">
                  Standard selling rates
                </option>
                <option value="client_rate_card">
                  Client rate card (foundation only)
                </option>
              </select>
            </label>
            <label>
              <span>Allowed cities</span>
              <input name="allowed_cities" placeholder="Delhi, Mumbai" />
              <small>Optional, comma-separated.</small>
            </label>
            <label>
              <span>Expires</span>
              <input name="expires_at" type="datetime-local" />
            </label>
            <label className="checkbox-field">
              <input name="allow_image_download" type="checkbox" />
              <span>Allow photo downloads</span>
            </label>
            <button className="submit" type="submit" disabled={isGenerating || (isPlatformAdmin && !selectedTenantId)}>
              {isGenerating
                ? "Generating..."
                : linkFeedback === "Link generated"
                  ? "Link generated"
                  : "Generate secure link"}
            </button>
          </form>
          <div className="planner-action-feedback" aria-live="polite">
            {copyFeedback || linkFeedback || tenantFeedback}
          </div>
          {generatedUrl ? (
            <div className="planner-generated-link" role="status">
              <strong>Copy this link now</strong>
              <div className="planner-generated-summary">
                <span>
                  Company: {generatedLink?.tenant_name || userCompanyName}
                </span>
                <span>
                  {generatedLink?.allowed_cities?.length
                    ? `Cities: ${generatedLink.allowed_cities.join(", ")}`
                    : "Cities: all permitted cities"}
                </span>
                <span>
                  {generatedLink?.eligible_unit_count ?? 0} published eligible
                  unit
                  {(generatedLink?.eligible_unit_count ?? 0) === 1 ? "" : "s"}
                </span>
                <span>
                  Pricing:{" "}
                  {generatedLink?.effective_show_rates
                    ? "standard rates visible"
                    : "rates hidden"}
                </span>
                <span>
                  Expiry:{" "}
                  {generatedLink?.expires_at
                    ? new Date(generatedLink.expires_at).toLocaleString()
                    : "no expiry set"}
                </span>
                <span>
                  Proposals:{" "}
                  {generatedLink?.allow_proposal_submission
                    ? "enabled"
                    : "disabled"}
                </span>
              </div>
              {generatedLink?.eligible_unit_count === 0 ? (
                <p className="planner-link-warning">
                  This planner link currently contains no eligible media units.
                </p>
              ) : null}
              <div className="planner-eligibility-preview">
                <div>
                  <strong>Eligible inventory preview</strong>
                  <span>
                    {eligibilityPreview
                      ? `${eligibilityPreview.counts.eligible} published eligible unit${
                          eligibilityPreview.counts.eligible === 1 ? "" : "s"
                        }`
                      : isPreviewLoading
                        ? "Checking eligible inventory..."
                        : "Preview eligible inventory before sharing."}
                  </span>
                </div>
                <button
                  className="ghost"
                  type="button"
                  disabled={isPreviewLoading}
                  onClick={() => void loadEligibilityPreview()}
                >
                  Preview eligible inventory
                </button>
                {eligibilityPreview ? (
                  <dl>
                    <div>
                      <dt>Published eligible units</dt>
                      <dd>{eligibilityPreview.counts.eligible}</dd>
                    </div>
                    <div>
                      <dt>Excluded units</dt>
                      <dd>
                        {Object.values(eligibilityPreview.excluded).reduce(
                          (sum, value) => sum + value,
                          0,
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Allowed cities</dt>
                      <dd>
                        {generatedLink?.allowed_cities?.length
                          ? generatedLink.allowed_cities.join(", ")
                          : "All permitted cities"}
                      </dd>
                    </div>
                    {Object.entries(eligibilityPreview.excluded)
                      .filter(([, value]) => value > 0)
                      .map(([key, value]) => (
                        <div key={key}>
                          <dt>{key.replaceAll("_", " ")}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                  </dl>
                ) : null}
              </div>
              <input
                readOnly
                value={generatedUrl}
                onFocus={(event) => event.currentTarget.select()}
              />
              <button
                className="ghost"
                type="button"
                onClick={() => void copyGeneratedLink()}
              >
                Copy link
              </button>
              <small>
                The full token is shown once and is not stored in OMMS.
              </small>
            </div>
          ) : null}
        </article>
        <article className="module-card planner-link-history">
          <div className="module-head">
            <div>
              <p className="site-code">ACCESS CONTROL</p>
              <h2>Recent planner links</h2>
            </div>
          </div>
          {recentPlannerLinks.length ? (
            <div className="planner-link-table-wrap">
              <table className="planner-link-table" aria-label="Recent planner links">
                <thead>
                  <tr>
                    <th scope="col">Planner Link</th>
                    <th scope="col">Client / Company</th>
                    <th scope="col">Inventory</th>
                    <th scope="col">Status</th>
                    {showPlannerDateColumn ? <th scope="col">Created / Expiry</th> : null}
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recentPlannerLinks.map((link) => {
                    const diagnostics = diagnosticsByLink[link.id];
                    const canCopyPlannerLink = isCopyablePlannerLink(link);
                    const isCopied = copiedPlannerLinkId === link.id;
                    const isCopying = copyingPlannerLinkId === link.id;
                    const status = getPlannerLinkStatus(link);
                    const clientPrimary = link.client_name || link.tenant_name || userCompanyName;
                    const clientSecondary = link.client_name && link.tenant_name ? link.tenant_name : "";
                    const createdDate = formatPlannerDate(link.created_at);
                    const expiryDate = formatPlannerDate(link.expires_at);
                    return (
                      <Fragment key={link.id}>
                        <tr className="planner-link-row">
                          <td data-label="Planner Link">
                            <div className="planner-link-main">
                              <strong>{link.title}</strong>
                              <span>
                                {link.client_name ? "Client-specific link" : "General client link"} ·{" "}
                                {formatPlannerPricing(link.pricing_mode)}
                              </span>
                            </div>
                          </td>
                          <td data-label="Client / Company">
                            <div className="planner-link-client">
                              <strong>{clientPrimary}</strong>
                              {clientSecondary ? <span>{clientSecondary}</span> : null}
                            </div>
                          </td>
                          <td data-label="Inventory">
                            <dl className="planner-link-inventory">
                              <div>
                                <dt>Eligible</dt>
                                <dd>{diagnostics?.link.eligible_count ?? link.eligible_unit_count ?? 0}</dd>
                              </div>
                              <div>
                                <dt>Published</dt>
                                <dd>{diagnostics?.link.published_count ?? "pending"}</dd>
                              </div>
                              <div>
                                <dt>Excluded</dt>
                                <dd>{diagnostics?.link.excluded_count ?? "pending"}</dd>
                              </div>
                            </dl>
                          </td>
                          <td data-label="Status">
                            <span className={`status-pill status-${status}`}>
                              {status.toUpperCase()}
                            </span>
                          </td>
                          {showPlannerDateColumn ? (
                            <td data-label="Created / Expiry">
                              <div className="planner-link-dates">
                                {createdDate ? <span>Created {createdDate}</span> : null}
                                <span>{expiryDate ? `Expires ${expiryDate}` : "No expiry"}</span>
                              </div>
                            </td>
                          ) : null}
                          <td data-label="Actions">
                            <div className="planner-link-actions">
                              {canCopyPlannerLink ? (
                                <button
                                  className={`ghost planner-copy-link-button${isCopied ? " is-copied" : ""}`}
                                  type="button"
                                  aria-label="Copy Live Media Planner link"
                                  disabled={isCopying}
                                  onClick={(event) => void copyPlannerHistoryLink(event, link)}
                                >
                                  {isCopied ? <CheckIcon /> : <CopyLinkIcon />}
                                  {isCopied ? "Copied" : "Copy Link"}
                                </button>
                              ) : null}
                              {isPlatformAdmin ? (
                                <button
                                  className="ghost"
                                  type="button"
                                  disabled={isDiagnosticsLoading}
                                  onClick={() => void openDiagnostics(link)}
                                >
                                  Diagnostics
                                </button>
                              ) : null}
                              {link.is_available &&
                              ["admin", "sales"].includes(user?.role || "") ? (
                                <button
                                  className="ghost"
                                  type="button"
                                  onClick={async () => {
                                    await revokePlannerLink(link.id);
                                    await load();
                                  }}
                                >
                                  Revoke
                                </button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                        {hasTenantMismatch(diagnostics) ? (
                          <tr className="planner-link-warning-row" key={`${link.id}-warning`}>
                            <td colSpan={plannerHistoryColumnCount}>
                              <p className="planner-link-warning">{TENANT_MISMATCH_MESSAGE}</p>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-state">No client planner links yet.</p>
          )}
          {historyCopyFeedback ? <p className="planner-action-feedback" aria-live="polite">{historyCopyFeedback}</p> : null}
          {historyCopyError ? <p className="planner-action-feedback planner-action-feedback-error" aria-live="polite">{historyCopyError}</p> : null}
          {diagnosticsFeedback && !activeDiagnostics ? <p className="planner-action-feedback">{diagnosticsFeedback}</p> : null}
        </article>
      </section>
      {activeDiagnostics ? (
        <div className="modal-backdrop" role="presentation">
          <section
            className="modal-card planner-diagnostics-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Media planner eligibility diagnostics"
          >
            <div className="panel-heading-row">
              <div>
                <span className="eyebrow">Platform diagnostics</span>
                <h2>{activeDiagnostics.link.title}</h2>
                <p className="site-copy">
                  Backend {activeDiagnostics.service.git_sha} · {activeDiagnostics.service.environment} · DB{" "}
                  {activeDiagnostics.database.database_fingerprint}
                </p>
              </div>
              <button className="ghost" type="button" onClick={() => setActiveDiagnostics(null)}>
                Close
              </button>
            </div>
            <div className="diagnostics-warning" role="status">
              <strong>Platform diagnostics.</strong>
              <span>Contains operational metadata. Do not share publicly.</span>
            </div>
            {hasTenantMismatch(activeDiagnostics) ? (
              <div className="planner-link-warning" role="alert">
                {TENANT_MISMATCH_MESSAGE}
              </div>
            ) : null}
            <div className="diagnostics-cards">
              <article className="ops-kpi-card">
                <p className="stat-label">Eligible units</p>
                <strong>{activeDiagnostics.link.eligible_count}</strong>
              </article>
              <article className="ops-kpi-card">
                <p className="stat-label">Published units</p>
                <strong>{activeDiagnostics.link.published_count}</strong>
              </article>
              <article className="ops-kpi-card">
                <p className="stat-label">Excluded units</p>
                <strong>{activeDiagnostics.link.excluded_count}</strong>
              </article>
            </div>
            <DiagnosticsMap title="Pipeline counts" rows={activeDiagnostics.pipeline} />
            <DiagnosticsMap title="Exclusion counts" rows={activeDiagnostics.exclusions} />
            <div>
              <h3>Migration status</h3>
              <div className="diagnostics-migrations">
                {Object.entries(activeDiagnostics.database.migration_status).map(([name, applied]) => (
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
                    <th>Status</th>
                    <th>City</th>
                    <th>Eligible</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {activeDiagnostics.sample_units.map((unit) => (
                    <tr key={unit.code}>
                      <td>{unit.code}</td>
                      <td>{unit.tenant_id ?? "-"}</td>
                      <td>{unit.published ? "Yes" : "No"}</td>
                      <td>{unit.status}</td>
                      <td>{unit.city_raw || "-"}</td>
                      <td>{unit.eligible ? "Yes" : "No"}</td>
                      <td>{unit.exclusion_reason ?? "Included"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="modal-actions">
              <button className="primary" type="button" onClick={() => void copyDiagnosticsReport()}>
                Copy diagnostic report
              </button>
              <button className="ghost" type="button" onClick={() => setActiveDiagnostics(null)}>
                Close
              </button>
            </div>
            <p className="planner-action-feedback" aria-live="polite">{diagnosticsFeedback}</p>
            <textarea
              className="diagnostics-json-source"
              readOnly
              aria-label="Diagnostic report JSON"
              value={JSON.stringify(activeDiagnostics, null, 2)}
              onFocus={(event) => event.currentTarget.select()}
            />
          </section>
        </div>
      ) : null}
      <section className="module-card planner-proposals-card">
        <div className="module-head">
          <div>
            <p className="site-code">PROPOSAL PIPELINE</p>
            <h2>Submitted client proposals</h2>
          </div>
          <label className="compact-field">
            <span>Status</span>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              {[
                "submitted",
                "under_review",
                "availability_confirmed",
                "estimate_prepared",
                "sent_to_client",
                "client_approved",
                "client_rejected",
                "converted_to_campaign",
              ].map((value) => (
                <option key={value} value={value}>
                  {value.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {isLoading ? (
          <p className="empty-state">Loading proposals...</p>
        ) : proposals.length ? (
          <div className="inventory-table-wrap">
            <table className="inventory-table planner-proposal-table">
              <thead>
                <tr>
                  <th>Proposal</th>
                  <th>Client / campaign</th>
                  <th>Timeline</th>
                  <th>Units</th>
                  <th>Preliminary value</th>
                  <th>Conflicts</th>
                  <th>Status</th>
                  <th>Owner</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {proposals.map((proposal) => (
                  <tr key={proposal.id}>
                    <td>
                      <strong>{proposal.reference}</strong>
                      <br />
                      <span className="site-code">
                        {new Date(proposal.submitted_at).toLocaleString()}
                      </span>
                    </td>
                    <td>
                      <strong>{proposal.client_name}</strong>
                      <br />
                      {proposal.campaign_name}
                    </td>
                    <td>
                      {proposal.requested_start_date}
                      <br />
                      to {proposal.requested_end_date}
                    </td>
                    <td>{proposal.selected_unit_count}</td>
                    <td>
                      {Number(proposal.preliminary_subtotal)
                        ? `INR ${Number(proposal.preliminary_subtotal).toLocaleString("en-IN")}`
                        : "Rate review"}
                    </td>
                    <td>
                      <span
                        className={`status-pill ${proposal.availability_conflict_count ? "status-failed" : "status-active"}`}
                      >
                        {proposal.availability_conflict_count}
                      </span>
                    </td>
                    <td>
                      <span className={`status-pill status-${proposal.status}`}>
                        {proposal.status.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td>{proposal.assigned_to_name}</td>
                    <td>
                      <Link
                        className="ghost table-link"
                        href={`/sales/proposals/${proposal.id}`}
                      >
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-state">No proposals match this view.</p>
        )}
      </section>
    </AppShell>
  );
}

function CopyLinkIcon() {
  return (
    <svg aria-hidden="true" focusable="false" viewBox="0 0 20 20">
      <rect x="7" y="7" width="9" height="9" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M4 13V5.8C4 4.8 4.8 4 5.8 4H13" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg aria-hidden="true" data-testid="planner-copy-check-icon" focusable="false" viewBox="0 0 20 20">
      <path d="M16.3 5.7 8.7 13.3 4.5 9.1" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
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
