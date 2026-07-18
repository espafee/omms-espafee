"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { SafeImage } from "@/components/safe-image";
import {
  clearAuthSession,
  getAccessToken,
  getStoredUser,
  type AuthUser,
} from "@/lib/auth";
import {
  fetchPlannerProposal,
  plannerProposalAction,
  type PlannerProposal,
} from "@/lib/planner";

export default function ProposalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [proposal, setProposal] = useState<PlannerProposal | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    try {
      setProposal(await fetchPlannerProposal(id));
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load proposal.",
      );
    }
  }, [id]);
  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    setUser(getStoredUser());
    void load();
  }, [load, router]);
  async function act(action: string, body: Record<string, unknown> = {}) {
    setBusy(action);
    setError("");
    setMessage("");
    try {
      await plannerProposalAction(Number(id), action, body);
      await load();
      setMessage("Proposal updated successfully.");
    } catch (actionError) {
      setError(
        actionError instanceof Error
          ? actionError.message
          : "Unable to update proposal.",
      );
    } finally {
      setBusy("");
    }
  }
  function logout() {
    clearAuthSession();
    router.replace("/login");
  }
  async function createEstimate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const client = String(data.get("client") || "").trim();
    await act("create-estimate", client ? { client: Number(client) } : {});
  }
  async function assign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const owner = String(data.get("assigned_to") || "").trim();
    await act("assign", { assigned_to: owner ? Number(owner) : null });
  }
  async function convert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await act("convert-to-campaign", {
      campaign_code: String(data.get("campaign_code") || "").trim(),
    });
  }
  return (
    <AppShell
      active="proposals"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? ""}
      onLogout={logout}
      title={
        proposal
          ? `${proposal.reference} · ${proposal.campaign_name}`
          : "Proposal review"
      }
      description="Validate inventory, prepare the formal estimate, and convert only after client approval."
    >
      <div className="planner-detail-top">
        <Link className="ghost table-link" href="/sales/proposals">
          Back to proposals
        </Link>
        {proposal ? (
          <span className={`status-pill status-${proposal.status}`}>
            {proposal.status.replaceAll("_", " ")}
          </span>
        ) : null}
      </div>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="success" role="status">
          {message}
        </p>
      ) : null}
      {!proposal ? (
        <p className="empty-state">Loading proposal...</p>
      ) : (
        <>
          <section className="planner-detail-grid">
            <article className="module-card">
              <p className="site-code">CLIENT REQUEST</p>
              <h2>{proposal.client_name}</h2>
              <dl className="planner-detail-facts">
                <div>
                  <dt>Contact</dt>
                  <dd>
                    {proposal.contact_name}
                    <br />
                    {proposal.contact_email}
                    <br />
                    {proposal.contact_phone || "Phone not provided"}
                  </dd>
                </div>
                <div>
                  <dt>Campaign window</dt>
                  <dd>
                    {proposal.requested_start_date} to{" "}
                    {proposal.requested_end_date}
                  </dd>
                </div>
                <div>
                  <dt>Selected media</dt>
                  <dd>{proposal.selected_unit_count} units</dd>
                </div>
                <div>
                  <dt>Pricing snapshot</dt>
                  <dd>
                    {Number(proposal.preliminary_subtotal)
                      ? `INR ${Number(proposal.preliminary_subtotal).toLocaleString("en-IN")}`
                      : "Rates hidden / formal review"}
                  </dd>
                </div>
                <div>
                  <dt>GSTIN</dt>
                  <dd>{proposal.billing_gstin || "Not provided"}</dd>
                </div>
                <div>
                  <dt>Owner</dt>
                  <dd>{proposal.assigned_to_name}</dd>
                </div>
              </dl>
              {proposal.notes ? (
                <div className="planner-notes">
                  <strong>Client notes</strong>
                  <p>{proposal.notes}</p>
                </div>
              ) : null}
            </article>
            <article className="module-card planner-review-actions">
              <p className="site-code">CONTROLLED WORKFLOW</p>
              <h2>Review actions</h2>
              <form onSubmit={assign}>
                <label>
                  <span>Owner user ID</span>
                  <input name="assigned_to" type="number" min="1" placeholder="Leave blank to unassign" />
                </label>
                <button className="ghost" type="submit" disabled={Boolean(busy)}>Assign owner</button>
              </form>
              <button
                className="ghost"
                type="button"
                disabled={Boolean(busy)}
                onClick={() =>
                  void act("set-status", { status: "under_review" })
                }
              >
                Mark under review
              </button>
              <button
                className="ghost"
                type="button"
                disabled={Boolean(busy)}
                onClick={() => void act("recheck-availability")}
              >
                Recheck live availability
              </button>
              {["admin", "finance"].includes(user?.role || "") ? (
                <form onSubmit={createEstimate}>
                  <label>
                    <span>Client user ID (only if not linked)</span>
                    <input name="client" type="number" min="1" />
                  </label>
                  <button
                    className="submit"
                    type="submit"
                    disabled={
                      Boolean(busy) || Boolean(proposal.estimate_number)
                    }
                  >
                    Prepare draft estimate
                  </button>
                </form>
              ) : null}
              {proposal.estimate_number ? (
                <p className="planner-linked-record">
                  Estimate: <strong>{proposal.estimate_number}</strong>
                </p>
              ) : null}
              {["admin", "sales"].includes(user?.role || "") ? (
                <form onSubmit={convert}>
                  <label>
                    <span>Campaign code</span>
                    <input
                      name="campaign_code"
                      required
                      placeholder="Preserves existing campaign code rules"
                    />
                  </label>
                  <button
                    className="submit"
                    type="submit"
                    disabled={
                      Boolean(busy) || proposal.status !== "client_approved"
                    }
                  >
                    Convert approved proposal
                  </button>
                </form>
              ) : null}
              <button
                className="ghost ghost-danger"
                type="button"
                disabled={Boolean(busy)}
                onClick={() =>
                  void act("set-status", { status: "client_rejected" })
                }
              >
                Reject / close proposal
              </button>
              <p className="field-help">
                Draft estimates do not reserve inventory. Conversion rechecks
                availability and creates draft campaign records with pending
                bookings.
              </p>
            </article>
          </section>
          <section className="module-card">
            <div className="module-head">
              <div>
                <p className="site-code">SELECTED INVENTORY</p>
                <h2>Availability and pricing snapshots</h2>
              </div>
              <span
                className={`status-pill ${proposal.availability_conflict_count ? "status-failed" : "status-active"}`}
              >
                {proposal.availability_conflict_count} conflicts
              </span>
            </div>
            <div className="planner-line-grid">
              {proposal.lines.map((line) => (
                <article className="planner-line-card" key={line.id}>
                  <SafeImage
                    src={line.photo_url}
                    alt={`${line.unit_code} at ${line.location_name}`}
                    className="planner-line-photo"
                    fallback={
                      <div className="planner-line-photo planner-photo-empty">
                        No photo
                      </div>
                    }
                  />
                  <div>
                    <p className="site-code">{line.city}</p>
                    <h3>{line.unit_code}</h3>
                    <p>{line.location_name}</p>
                    <span
                      className={`planner-status status-${line.current_availability.status}`}
                    >
                      {line.current_availability.label}
                    </span>
                    <small>{line.current_availability.reason}</small>
                    <strong>
                      {line.monthly_rate_snapshot
                        ? `INR ${Number(line.monthly_rate_snapshot).toLocaleString("en-IN")}`
                        : "Rate hidden"}
                    </strong>
                  </div>
                </article>
              ))}
            </div>
          </section>
          <section className="module-card planner-audit-card">
            <div className="module-head">
              <div>
                <p className="site-code">AUDIT TIMELINE</p>
                <h2>Proposal activity</h2>
              </div>
            </div>
            {proposal.audit_events.length ? (
              <div className="planner-audit-list">
                {proposal.audit_events.map((event, index) => (
                  <article
                    key={`${event.event_type}-${event.created_at}-${index}`}
                  >
                    <span className={`status-pill status-${event.severity}`}>
                      {event.severity}
                    </span>
                    <div>
                      <strong>{event.summary}</strong>
                      <small>
                        {event.actor} ·{" "}
                        {new Date(event.created_at).toLocaleString()}
                      </small>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-state">
                No proposal activity has been recorded yet.
              </p>
            )}
          </section>
        </>
      )}
    </AppShell>
  );
}
