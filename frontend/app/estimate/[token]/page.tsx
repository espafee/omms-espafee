"use client";

import { useEffect, useState } from "react";

import {
  fetchPublicEstimate,
  getPublicEstimateActionError,
  submitPublicEstimateDecision,
  type PublicEstimatePayload,
} from "@/lib/public-estimate";
import { formatCurrency } from "@/lib/dashboard";

type EstimatePageProps = {
  params: {
    token: string;
  };
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function formatStatusLabel(value: string) {
  return value.replaceAll("_", " ");
}

export default function PublicEstimatePage({ params }: EstimatePageProps) {
  const [estimate, setEstimate] = useState<PublicEstimatePayload | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [comment, setComment] = useState("");

  useEffect(() => {
    async function loadEstimate() {
      setIsLoading(true);
      setError("");
      try {
        setEstimate(await fetchPublicEstimate(params.token));
      } catch (loadError) {
        setError(getPublicEstimateActionError(loadError));
      } finally {
        setIsLoading(false);
      }
    }

    void loadEstimate();
  }, [params.token]);

  async function handleDecision(decision: "approve" | "reject") {
    if (isSubmitting) {
      return;
    }

    setError("");
    setSuccess("");
    setIsSubmitting(true);

    try {
      const updated = await submitPublicEstimateDecision(params.token, decision, comment.trim());
      setEstimate(updated);
      setComment("");
      setSuccess(
        decision === "approve"
          ? "Estimate approved successfully."
          : "Estimate rejected. The OMMS team will be able to revise and resend it.",
      );
    } catch (decisionError) {
      setError(getPublicEstimateActionError(decisionError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="public-shell">
      <section className="public-panel">
        <article className="module-card public-hero-card">
          <span className="eyebrow dashboard-eyebrow">Campaign Estimate</span>
          <h1 className="workspace-title public-title">Review campaign estimate</h1>
          <p className="workspace-copy">
            Review the proposed media plan, dates, rates, and taxes. You can approve or reject this estimate using this secure link.
          </p>
        </article>

        {isLoading ? <p className="info">Loading estimate...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {success ? <p className="success">{success}</p> : null}

        {estimate && !error ? (
          <>
            <section className="summary-row" aria-label="Estimate summary">
              <article className="summary-card">
                <p className="stat-label">Client</p>
                <p className="summary-value">{estimate.client_name}</p>
              </article>
              <article className="summary-card">
                <p className="stat-label">Campaign</p>
                <p className="summary-value">{estimate.campaign_name || "Not linked"}</p>
              </article>
              <article className="summary-card">
                <p className="stat-label">Status</p>
                <p className="summary-value">{formatStatusLabel(estimate.status)}</p>
              </article>
              <article className="summary-card">
                <p className="stat-label">Total</p>
                <p className="summary-value">{formatCurrency(estimate.total_amount)}</p>
              </article>
            </section>

            <section className="public-grid">
              <article className="module-card">
                <div className="module-head">
                  <h2>Estimate details</h2>
                  <span>{estimate.estimate_number || "Draft estimate"}</span>
                </div>
                <div className="module-stats">
                  <div className="module-stat">
                    <p className="stat-label">Title</p>
                    <p className="field-summary-value">{estimate.title}</p>
                  </div>
                  <div className="module-stat">
                    <p className="stat-label">Campaign window</p>
                    <p className="field-summary-value">
                      {formatDate(estimate.start_date)} - {formatDate(estimate.end_date)}
                    </p>
                  </div>
                  <div className="module-stat">
                    <p className="stat-label">Shared on</p>
                    <p className="field-summary-value">{estimate.shared_at ? formatDate(estimate.shared_at) : "Not available"}</p>
                  </div>
                </div>
                <p className="section-copy">{estimate.notes || "No additional estimate notes were included."}</p>
                <div className="field field-full">
                  <label htmlFor="estimate-comment">Comment (optional)</label>
                  <textarea
                    id="estimate-comment"
                    rows={3}
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                    placeholder="Add an approval note or explain why this estimate is being rejected."
                  />
                </div>
                <div className="form-actions">
                  <button
                    className="submit"
                    type="button"
                    disabled={isSubmitting || estimate.status !== "sent"}
                    onClick={() => void handleDecision("approve")}
                  >
                    {isSubmitting ? "Submitting..." : "Approve estimate"}
                  </button>
                  <button
                    className="ghost"
                    type="button"
                    disabled={isSubmitting || estimate.status !== "sent"}
                    onClick={() => void handleDecision("reject")}
                  >
                    Reject estimate
                  </button>
                </div>
              </article>

              <article className="module-card">
                <div className="module-head">
                  <h2>Financial summary</h2>
                  <span>Read only</span>
                </div>
                <div className="module-stats">
                  <div className="module-stat">
                    <p className="stat-label">Subtotal</p>
                    <p className="stat-value">{formatCurrency(estimate.subtotal)}</p>
                  </div>
                  <div className="module-stat">
                    <p className="stat-label">Tax</p>
                    <p className="stat-value">{formatCurrency(estimate.tax_amount)}</p>
                  </div>
                  <div className="module-stat">
                    <p className="stat-label">Total</p>
                    <p className="stat-value">{formatCurrency(estimate.total_amount)}</p>
                  </div>
                </div>
              </article>
            </section>

            <section className="module-card">
              <div className="module-head">
                <h2>Proposed media plan</h2>
                <span>{estimate.lines.length} item(s)</span>
              </div>
              <div className="inventory-table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Site / unit</th>
                      <th>Description</th>
                      <th>Dates</th>
                      <th>Qty</th>
                      <th>Rate</th>
                      <th>Tax</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {estimate.lines.map((line) => (
                      <tr key={line.id}>
                        <td>
                          <div className="table-primary">
                            <strong>{line.site_name || "Site pending"}</strong>
                            <span>{line.media_unit_label || "Unit pending"}</span>
                          </div>
                        </td>
                        <td>{line.description}</td>
                        <td>{formatDate(line.start_date)} - {formatDate(line.end_date)}</td>
                        <td>{line.quantity}</td>
                        <td>{formatCurrency(line.unit_rate)}</td>
                        <td>{line.tax_rate}%</td>
                        <td>{formatCurrency(line.total_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}
