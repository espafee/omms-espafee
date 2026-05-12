"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { fetchPublicIssueReport, submitPublicIssueReport, type PublicIssueReportContext } from "@/lib/issues";

const ISSUE_TYPES = [
  { value: "damage", label: "Damage" },
  { value: "missing", label: "Missing" },
  { value: "wrong", label: "Wrong creative or placement" },
  { value: "other", label: "Other" },
];

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export default function ReportIssuePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [context, setContext] = useState<PublicIssueReportContext | null>(null);
  const [issueType, setIssueType] = useState("damage");
  const [description, setDescription] = useState("");
  const [contact, setContact] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    async function loadContext() {
      setError("");
      setIsLoading(true);
      try {
        setContext(await fetchPublicIssueReport(token));
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "This issue reporting link is not available.");
      } finally {
        setIsLoading(false);
      }
    }

    void loadContext();
  }, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setError("");
    setSuccess("");
    setIsSubmitting(true);

    try {
      const formData = new FormData();
      formData.append("issue_type", issueType);
      formData.append("description", description.trim());
      if (contact.trim()) {
        formData.append("contact", contact.trim());
      }
      if (image) {
        formData.append("image", image);
      }

      const response = await submitPublicIssueReport(token, formData);
      setSuccess(`${response.detail} Priority: ${response.priority.replace("_", " ")}.`);
      setDescription("");
      setContact("");
      setImage(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to submit the issue report.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="public-shell">
      <section className="public-panel">
        <article className="module-card public-hero-card">
          <span className="eyebrow dashboard-eyebrow">Issue reporting</span>
          <h1 className="workspace-title public-title">Report a site issue</h1>
          <p className="workspace-copy">
            Use this secure link to report damage, missing creative, wrong installation, or any site concern to the
            operations team.
          </p>
        </article>

        {isLoading ? <p className="info">Checking this reporting link...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {success ? <p className="success">{success}</p> : null}

        {context && !error ? (
          <section className="public-grid">
            <article className="module-card">
              <div className="module-head">
                <h2>Booking context</h2>
                <span>Read only</span>
              </div>
              <div className="module-stats">
                <div className="module-stat">
                  <p className="stat-label">Campaign</p>
                  <p className="stat-value field-summary-value">{context.campaign_name}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Site</p>
                  <p className="site-copy">
                    {context.site_name} | {context.unit_name}
                  </p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Location</p>
                  <p className="site-copy">{context.location || "Location details unavailable"}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Campaign window</p>
                  <p className="site-copy">
                    {formatDate(context.booking_start)} - {formatDate(context.booking_end)}
                  </p>
                </div>
              </div>
            </article>

            <article className="module-card">
              <div className="module-head">
                <h2>Issue details</h2>
                <span>Client report</span>
              </div>
              <form className="site-form-grid" onSubmit={handleSubmit}>
                <div className="field">
                  <label htmlFor="issue-type">Issue type</label>
                  <select id="issue-type" value={issueType} onChange={(event) => setIssueType(event.target.value)}>
                    {ISSUE_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label htmlFor="issue-contact">Contact (optional)</label>
                  <input
                    id="issue-contact"
                    value={contact}
                    onChange={(event) => setContact(event.target.value)}
                    placeholder="Email or phone"
                  />
                </div>

                <div className="field field-full">
                  <label htmlFor="issue-description">Description</label>
                  <textarea
                    id="issue-description"
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder="Tell us what happened at this site."
                    rows={5}
                    required
                  />
                  <p className="field-help">Reports are automatically prioritized and sent to operations.</p>
                </div>

                <div className="field field-full">
                  <label htmlFor="issue-image">Photo (optional)</label>
                  <input
                    id="issue-image"
                    type="file"
                    accept="image/*"
                    onChange={(event) => setImage(event.target.files?.[0] ?? null)}
                  />
                </div>

                <div className="form-actions field-full">
                  <button className="submit" type="submit" disabled={isSubmitting || description.trim().length < 8}>
                    {isSubmitting ? "Submitting..." : "Submit issue"}
                  </button>
                </div>
              </form>
            </article>
          </section>
        ) : null}
      </section>
    </main>
  );
}
