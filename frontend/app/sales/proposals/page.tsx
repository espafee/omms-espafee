"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
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

const DEFAULT_DIAGNOSTIC_UNITS = "ESPA-001,ESPA-002_1,ESPA-002_2,ESPA-003";

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
  const isPlatformAdmin = Boolean(user?.is_platform_admin);

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

  async function generateLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isGenerating) return;
    setIsGenerating(true);
    setError("");
    setLinkFeedback("");
    setCopyFeedback("");
    const form = new FormData(event.currentTarget);
    try {
      const link = await createPlannerLink({
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
      });
      const url = `${window.location.origin}${link.public_path}`;
      setGeneratedUrl(url);
      setGeneratedLink(link);
      setLinkFeedback("Link generated");
      void loadEligibilityPreview(link.id);
      await load();
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
      await navigator.clipboard.writeText(generatedUrl);
      setCopyFeedback("Link copied");
    } catch {
      setCopyFeedback("Unable to copy link. Select the URL and copy it manually.");
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
    await navigator.clipboard.writeText(JSON.stringify(activeDiagnostics, null, 2));
    setDiagnosticsFeedback("Diagnostic report copied");
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
            <button className="submit" type="submit" disabled={isGenerating}>
              {isGenerating
                ? "Generating..."
                : linkFeedback === "Link generated"
                  ? "Link generated"
                  : "Generate secure link"}
            </button>
          </form>
          <div className="planner-action-feedback" aria-live="polite">
            {copyFeedback || linkFeedback}
          </div>
          {generatedUrl ? (
            <div className="planner-generated-link" role="status">
              <strong>Copy this link now</strong>
              <div className="planner-generated-summary">
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
          {links.length ? (
            links.slice(0, 8).map((link) => {
              const diagnostics = diagnosticsByLink[link.id];
              return (
              <div className="planner-link-row" key={link.id}>
                <div>
                  <strong>{link.title}</strong>
                  <span>
                    {link.client_name || "General client link"} ·{" "}
                    {link.pricing_mode.replaceAll("_", " ")}
                  </span>
                  <span className="planner-link-metrics">
                    Eligible units: {diagnostics?.link.eligible_count ?? link.eligible_unit_count ?? 0}
                    {isPlatformAdmin ? (
                      <>
                        {" · "}Published units: {diagnostics?.link.published_count ?? "pending"}
                        {" · "}Excluded units: {diagnostics?.link.excluded_count ?? "pending"}
                      </>
                    ) : null}
                  </span>
                </div>
                <span
                  className={`status-pill ${link.is_available ? "status-active" : "status-failed"}`}
                >
                  {link.is_available ? "Active" : "Closed"}
                </span>
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
              );
            })
          ) : (
            <p className="empty-state">No client planner links yet.</p>
          )}
          {diagnosticsFeedback ? <p className="planner-action-feedback">{diagnosticsFeedback}</p> : null}
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
