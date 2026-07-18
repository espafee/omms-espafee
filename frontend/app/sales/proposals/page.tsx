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
  fetchPlannerLinks,
  fetchPlannerProposals,
  revokePlannerLink,
  type PlannerLink,
  type PlannerProposal,
} from "@/lib/planner";

export default function ProposalsWorkspacePage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [proposals, setProposals] = useState<PlannerProposal[]>([]);
  const [links, setLinks] = useState<PlannerLink[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [generatedUrl, setGeneratedUrl] = useState("");

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

  async function generateLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
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
      await load();
    } catch (createError) {
      setError(
        createError instanceof Error
          ? createError.message
          : "Unable to create media planner link.",
      );
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
            <button className="submit" type="submit">
              Generate secure link
            </button>
          </form>
          {generatedUrl ? (
            <div className="planner-generated-link" role="status">
              <strong>Copy this link now</strong>
              <input
                readOnly
                value={generatedUrl}
                onFocus={(event) => event.currentTarget.select()}
              />
              <button
                className="ghost"
                type="button"
                onClick={() => navigator.clipboard.writeText(generatedUrl)}
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
            links.slice(0, 8).map((link) => (
              <div className="planner-link-row" key={link.id}>
                <div>
                  <strong>{link.title}</strong>
                  <span>
                    {link.client_name || "General client link"} ·{" "}
                    {link.pricing_mode.replaceAll("_", " ")}
                  </span>
                </div>
                <span
                  className={`status-pill ${link.is_available ? "status-active" : "status-failed"}`}
                >
                  {link.is_available ? "Active" : "Closed"}
                </span>
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
            ))
          ) : (
            <p className="empty-state">No client planner links yet.</p>
          )}
        </article>
      </section>
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
