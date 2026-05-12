"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { PoeCreatePanel, type PoeFormState } from "@/components/poe-create-panel";
import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { createPoeWorkflow, fetchPoeData, getPoeCreateError, quickApprovePoe, quickRejectPoe, type PoePayload, type PoeRecord } from "@/lib/poe";
import type { Booking } from "@/lib/bookings";

type StoredUser = {
  id?: number;
  email?: string;
  role?: string;
};

const WRITE_ROLES = new Set(["admin", "operations"]);

const INITIAL_FORM: PoeFormState = {
  booking: 0,
  executed_on: "",
  verification_status: "pending",
  notes: "",
  media_type: "image",
  captured_at: "",
};

function formatDate(dateValue: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(dateValue));
}

function formatDateTime(dateValue: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(dateValue));
}

function getDefaultCapturedAt() {
  const now = new Date();
  const timezoneOffset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - timezoneOffset).toISOString().slice(0, 16);
}

export default function PoePage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [poeData, setPoeData] = useState<PoePayload | null>(null);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [form, setForm] = useState<PoeFormState>(INITIAL_FORM);
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [reviewActionId, setReviewActionId] = useState<number | null>(null);
  const [filters, setFilters] = useState({
    campaign: "",
    site: "",
    fieldAgent: "",
    status: "",
    suspiciousOnly: false,
    fromDate: "",
    toDate: "",
  });

  const canManagePoe = WRITE_ROLES.has(user?.role ?? "");

  function hydratePoeForm(payload: PoePayload, profile?: StoredUser | null) {
    const firstBooking = payload.bookings[0];

    setForm((current) => ({
      ...current,
      booking: current.booking || firstBooking?.id || 0,
      executed_on: current.executed_on || new Date().toISOString().slice(0, 10),
      captured_at: current.captured_at || getDefaultCapturedAt(),
    }));

    if (profile) {
      setUser(profile);
    }
  }

  async function loadPoe(profileHint?: StoredUser | null) {
    setIsLoading(true);
    setError("");

    try {
      const profile = profileHint ?? (await fetchCurrentUser());
      if (profile) {
        setUser(profile);
      }

      const payload = await fetchPoeData();
      setPoeData(payload);
      hydratePoeForm(payload, profile);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load proof-of-execution data.";
      setError(message);
      if (message.includes("sign in again")) {
        router.replace("/login");
      }
    } finally {
      setIsLoading(false);
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
    void loadPoe(storedUser);
  }, [router]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  function updateForm<K extends keyof PoeFormState>(field: K, value: PoeFormState[K]) {
    setFormError("");
    setFormSuccess("");
    setFieldErrors({});
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleCreatePoe(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setFormError("");
    setFormSuccess("");
    setFieldErrors({});
    setIsSubmitting(true);

    try {
      const evidence = evidenceFiles.map((file) => ({
        image: file,
        media_type: form.media_type,
        captured_at: new Date(form.captured_at || getDefaultCapturedAt()).toISOString(),
      }));

      const result = await createPoeWorkflow({
        record: {
          booking: form.booking,
          executed_on: form.executed_on,
          verification_status: form.verification_status,
          notes: form.notes,
          checked_by: form.verification_status === "pending" ? null : user?.id ?? null,
        },
        evidence,
      });

      setFormSuccess(
        result.evidence.length > 0
          ? `POE record created with ${result.evidence.length} uploaded evidence item(s).`
          : "POE record created successfully.",
      );
      setEvidenceFiles([]);
      setForm((current) => ({
        ...INITIAL_FORM,
        booking: current.booking,
        executed_on: new Date().toISOString().slice(0, 10),
        verification_status: "pending",
        captured_at: getDefaultCapturedAt(),
      }));
      await loadPoe(user);
    } catch (submitError) {
      const normalized = getPoeCreateError(submitError);
      setFormError(normalized.message);
      setFieldErrors(normalized.fieldErrors);
      if (normalized.partialSuccess) {
        await loadPoe(user);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function updateFilter(field: keyof typeof filters, value: string | boolean) {
    setFilters((current) => ({ ...current, [field]: value }));
  }

  function formatDistance(value: string | null | undefined) {
    if (value === null || value === undefined || value === "") {
      return "Not measured";
    }
    const distance = Number(value);
    return Number.isFinite(distance) ? `${distance.toFixed(1)}m` : "Not measured";
  }

  async function handleQuickApprove(record: PoeRecord) {
    if (reviewActionId) {
      return;
    }
    const comment = window.prompt("Optional reviewer comment for approval:") ?? "";
    setReviewActionId(record.id);
    setFormError("");
    setFormSuccess("");
    try {
      await quickApprovePoe(record.id, comment.trim());
      setFormSuccess("POE approved from review queue.");
      await loadPoe(user);
    } catch (actionError) {
      setFormError(actionError instanceof Error ? actionError.message : "Unable to approve POE.");
    } finally {
      setReviewActionId(null);
    }
  }

  async function handleQuickReject(record: PoeRecord) {
    if (reviewActionId) {
      return;
    }
    const reason = window.prompt("Enter rejection reason for this POE:");
    if (!reason?.trim()) {
      setFormError("Rejection reason is required.");
      return;
    }
    const comment = window.prompt("Optional reviewer comment for rejection:") ?? "";
    setReviewActionId(record.id);
    setFormError("");
    setFormSuccess("");
    try {
      await quickRejectPoe(record.id, reason.trim(), comment.trim());
      setFormSuccess("POE rejected from review queue.");
      await loadPoe(user);
    } catch (actionError) {
      setFormError(actionError instanceof Error ? actionError.message : "Unable to reject POE.");
    } finally {
      setReviewActionId(null);
    }
  }

  const bookingMap = useMemo(() => {
    const map = new Map<number, Booking>();
    for (const booking of poeData?.bookings ?? []) {
      map.set(booking.id, booking);
    }
    return map;
  }, [poeData]);

  const campaignMap = useMemo(() => {
    const map = new Map<number, { name: string; code: string }>();
    for (const campaign of poeData?.campaigns ?? []) {
      map.set(campaign.id, { name: campaign.name, code: campaign.code });
    }
    return map;
  }, [poeData]);

  const unitMap = useMemo(() => {
    const map = new Map<number, { unitCode: string; status: string; imageUrl: string | null; siteId: number }>();
    for (const unit of poeData?.units ?? []) {
      map.set(unit.id, {
        unitCode: unit.unit_code,
        status: unit.status,
        imageUrl: unit.primary_image?.image_url ?? null,
        siteId: unit.site,
      });
    }
    return map;
  }, [poeData]);

  const siteMap = useMemo(() => {
    const map = new Map<number, { name: string; imageUrl: string | null }>();
    for (const site of poeData?.sites ?? []) {
      map.set(site.id, {
        name: site.name,
        imageUrl: site.primary_image?.image_url ?? null,
      });
    }
    return map;
  }, [poeData]);

  const filteredRecords = useMemo(() => {
    return (poeData?.records ?? []).filter((record) => {
      const booking = bookingMap.get(record.booking);
      const unit = booking ? unitMap.get(booking.media_unit) : null;
      const site = unit ? siteMap.get(unit.siteId) : null;
      const mediaCapturedBy = record.media_items.map((item) => String(item.captured_by ?? "")).join(" ");
      const executedOn = new Date(record.executed_on).getTime();

      if (filters.campaign && String(booking?.campaign ?? "") !== filters.campaign) {
        return false;
      }
      if (filters.site && String(unit?.siteId ?? "") !== filters.site) {
        return false;
      }
      if (filters.status && record.verification_status !== filters.status) {
        return false;
      }
      if (filters.suspiciousOnly && record.location_confidence?.location_confidence_status !== "suspicious" && record.verification_status !== "suspicious" && record.verification_status !== "rejected") {
        return false;
      }
      if (filters.fieldAgent && !mediaCapturedBy.includes(filters.fieldAgent.trim())) {
        return false;
      }
      if (filters.fromDate && executedOn < new Date(filters.fromDate).getTime()) {
        return false;
      }
      if (filters.toDate && executedOn > new Date(filters.toDate).getTime()) {
        return false;
      }
      return Boolean(site || !filters.site);
    });
  }, [bookingMap, filters, poeData, siteMap, unitMap]);

  const quickStats = useMemo(() => {
    const records = filteredRecords;
    return [
      { label: "POE records", value: String(records.length) },
      {
        label: "Verified",
        value: String(records.filter((record) => record.verification_status === "verified").length),
      },
      {
        label: "Pending",
        value: String(records.filter((record) => record.verification_status === "pending").length),
      },
      {
        label: "Media items",
        value: String(records.reduce((count, record) => count + record.media_items.length, 0)),
      },
    ];
  }, [filteredRecords]);

  const recentMedia = useMemo(() => {
    return filteredRecords
      .flatMap((record) =>
        record.media_items.map((media) => ({
          ...media,
          executedOn: record.executed_on,
          verificationStatus: record.verification_status,
          bookingId: record.booking,
        })),
      )
      .sort((left, right) => right.captured_at.localeCompare(left.captured_at))
      .slice(0, 6);
  }, [filteredRecords]);

  return (
    <AppShell
      active="poe"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title="Proof of execution"
      eyebrow="POE"
      description="Review executed placements, verification status, and uploaded evidence so campaign delivery can be audited from the same workspace."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}

      {canManagePoe ? (
        <PoeCreatePanel
          bookings={poeData?.bookings ?? []}
          campaigns={poeData?.campaigns ?? []}
          units={poeData?.units ?? []}
          sites={poeData?.sites ?? []}
          form={form}
          evidenceFiles={evidenceFiles}
          fieldErrors={fieldErrors}
          formError={formError}
          formSuccess={formSuccess}
          isLoading={isLoading}
          isSubmitting={isSubmitting}
          onSubmit={handleCreatePoe}
          onChange={updateForm}
          onFilesChange={setEvidenceFiles}
        />
      ) : null}

      <section className="summary-row" aria-label="POE stats">
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
            <h2>Verification mix</h2>
            <span>Compliance</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Verified</p>
              <p className="stat-value">
                {isLoading
                  ? "..."
                  : (poeData?.records ?? []).filter((record) => record.verification_status === "verified").length}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Pending</p>
              <p className="stat-value">
                {isLoading
                  ? "..."
                  : (poeData?.records ?? []).filter((record) => record.verification_status === "pending").length}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Rejected</p>
              <p className="stat-value">
                {isLoading
                  ? "..."
                  : (poeData?.records ?? []).filter((record) => record.verification_status === "rejected").length}
              </p>
            </div>
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Execution coverage</h2>
            <span>Operations</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Booked units with POE</p>
              <p className="stat-value">
                {isLoading
                  ? "..."
                  : new Set((poeData?.records ?? []).map((record) => bookingMap.get(record.booking)?.media_unit)).size}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Campaigns represented</p>
              <p className="stat-value">
                {isLoading
                  ? "..."
                  : new Set((poeData?.records ?? []).map((record) => bookingMap.get(record.booking)?.campaign)).size}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Media proofs</p>
              <p className="stat-value">
                {isLoading
                  ? "..."
                  : (poeData?.records ?? []).reduce((count, record) => count + record.media_items.length, 0)}
              </p>
            </div>
          </div>
        </article>

        <article className="module-card module-card-highlight">
          <div className="module-head">
            <h2>Field capture</h2>
            <span>Mobile</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Fast path</p>
              <p className="table-wrap">
                Use the dedicated field capture page on mobile to create a pending POE record with image evidence in a simpler touch-friendly flow.
              </p>
            </div>
            <div className="module-stat">
              <Link className="submit inline-link-button" href="/poe/capture">
                Open field capture
              </Link>
            </div>
          </div>
        </article>
      </section>

      <section className="poe-layout">
        <article className="module-card module-card-wide">
          <div className="module-head">
            <h2>Execution log</h2>
            <span>{filteredRecords.length} items</span>
          </div>
          <div className="campaign-form-grid">
            <div className="field">
              <label htmlFor="poe-filter-campaign">Campaign</label>
              <select id="poe-filter-campaign" value={filters.campaign} onChange={(event) => updateFilter("campaign", event.target.value)}>
                <option value="">All campaigns</option>
                {(poeData?.campaigns ?? []).map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="poe-filter-site">Site</label>
              <select id="poe-filter-site" value={filters.site} onChange={(event) => updateFilter("site", event.target.value)}>
                <option value="">All sites</option>
                {(poeData?.sites ?? []).map((site) => (
                  <option key={site.id} value={site.id}>{site.name}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="poe-filter-agent">Field agent ID</label>
              <input id="poe-filter-agent" value={filters.fieldAgent} onChange={(event) => updateFilter("fieldAgent", event.target.value)} placeholder="Captured by user ID" />
            </div>
            <div className="field">
              <label htmlFor="poe-filter-status">POE status</label>
              <select id="poe-filter-status" value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
                <option value="">All statuses</option>
                <option value="pending">Pending</option>
                <option value="verified">Verified</option>
                <option value="suspicious">Suspicious</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="poe-filter-from">From</label>
              <input id="poe-filter-from" type="date" value={filters.fromDate} onChange={(event) => updateFilter("fromDate", event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="poe-filter-to">To</label>
              <input id="poe-filter-to" type="date" value={filters.toDate} onChange={(event) => updateFilter("toDate", event.target.value)} />
            </div>
            <label className="field field-full">
              <span>Suspicious only</span>
              <input type="checkbox" checked={filters.suspiciousOnly} onChange={(event) => updateFilter("suspiciousOnly", event.target.checked)} />
            </label>
          </div>
          <div className="inventory-table-wrap">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Unit</th>
                  <th>Executed on</th>
                  <th>Status</th>
                  <th>Review SLA</th>
                  <th>GPS confidence</th>
                  <th>Media</th>
                  <th>Notes</th>
                  {canManagePoe ? <th>Review</th> : null}
                </tr>
              </thead>
              <tbody>
                {filteredRecords.map((record) => {
                  const booking = bookingMap.get(record.booking);
                  const campaign = booking ? campaignMap.get(booking.campaign) : null;
                  const unit = booking ? unitMap.get(booking.media_unit) : null;
                  const confidence = record.location_confidence;

                  return (
                    <tr key={record.id}>
                      <td>
                        <div className="table-primary">
                          <strong>{campaign?.name ?? `Campaign #${booking?.campaign ?? "Unknown"}`}</strong>
                          <span>{campaign?.code ?? "Unknown code"}</span>
                        </div>
                      </td>
                      <td>
                        <div className="table-primary">
                          <strong>{unit?.unitCode ?? `Unit #${booking?.media_unit ?? "Unknown"}`}</strong>
                          <span>{unit?.status ?? "Unknown status"}</span>
                        </div>
                      </td>
                      <td>{formatDate(record.executed_on)}</td>
                      <td>
                        <span className={`status-pill status-${record.verification_status}`}>
                          {record.verification_status}
                        </span>
                      </td>
                      <td>
                        <div className="table-primary">
                          <strong>
                            <span className={`status-pill status-${record.review_sla_status}`}>
                              {record.review_sla_status?.replaceAll("_", " ") ?? "on track"}
                            </span>
                          </strong>
                          <span>{record.review_due_at ? `Due ${formatDateTime(record.review_due_at)}` : "No review due date"}</span>
                          {record.review_comment ? <span>{record.review_comment}</span> : null}
                        </div>
                      </td>
                      <td>
                        <div className="table-primary">
                          <strong>{confidence?.location_confidence_status?.replaceAll("_", " ") ?? "Not checked"}</strong>
                          <span>{formatDistance(confidence?.distance_meters)} / {formatDistance(confidence?.threshold_meters)}</span>
                          <span>{confidence?.captured_latitude ?? "-"}, {confidence?.captured_longitude ?? "-"}</span>
                        </div>
                      </td>
                      <td>{record.media_items.length}</td>
                      <td className="table-wrap">{record.notes || "No field notes recorded."}</td>
                      {canManagePoe ? (
                        <td>
                          <div className="form-actions">
                            <button className="ghost table-action" type="button" disabled={reviewActionId === record.id} onClick={() => void handleQuickApprove(record)}>
                              Approve
                            </button>
                            <button className="ghost table-action" type="button" disabled={reviewActionId === record.id} onClick={() => void handleQuickReject(record)}>
                              Reject
                            </button>
                          </div>
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!isLoading && filteredRecords.length === 0 ? (
            <p className="empty-state">No proof-of-execution records are visible for the current account.</p>
          ) : null}
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Recent evidence</h2>
            <span>Media</span>
          </div>
          <div className="asset-list">
            {recentMedia.map((media) => {
              const booking = bookingMap.get(media.bookingId);
              const unit = booking ? unitMap.get(booking.media_unit) : null;
              const site = unit ? siteMap.get(unit.siteId) : null;
              const mediaLink = media.image_url || media.media_url;

              return (
                <article className="asset-card asset-card-media" key={media.id}>
                  {media.image_url ? (
                    <img className="asset-image" src={media.image_url} alt={media.note || "POE evidence"} />
                  ) : (
                    <div className="image-reference-empty asset-image-placeholder">
                      <span>{media.media_type}</span>
                    </div>
                  )}
                  <div className="asset-head">
                    <div>
                      <p className="site-code">{media.media_type}</p>
                      <h3>{formatDateTime(media.captured_at)}</h3>
                    </div>
                    <span className={`status-pill status-${media.verificationStatus}`}>{media.verificationStatus}</span>
                  </div>
                  <p className="site-copy">
                    {(site?.name ?? "Unknown site") + " • " + (unit?.unitCode ?? "Unknown unit")}
                  </p>
                  <p className="site-copy">{media.note || `Executed on ${formatDate(media.executedOn)}`}</p>
                  {mediaLink ? (
                    <a className="asset-link" href={mediaLink} rel="noreferrer" target="_blank">
                      Open proof media
                    </a>
                  ) : null}
                </article>
              );
            })}
            {!isLoading && recentMedia.length === 0 ? (
              <p className="empty-state">No proof media is available for the current execution scope.</p>
            ) : null}
          </div>
        </article>
      </section>
    </AppShell>
  );
}

type BookingDetails = {
  id: number;
  campaign: number;
  media_unit: number;
};
