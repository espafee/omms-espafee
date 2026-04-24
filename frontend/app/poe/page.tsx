"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { PoeCreatePanel, type PoeFormState } from "@/components/poe-create-panel";
import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { createPoeWorkflow, fetchPoeData, getPoeCreateError, type PoePayload } from "@/lib/poe";

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

  const bookingMap = useMemo(() => {
    const map = new Map<number, BookingDetails>();
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

  const quickStats = useMemo(() => {
    const records = poeData?.records ?? [];
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
  }, [poeData]);

  const recentMedia = useMemo(() => {
    return (poeData?.records ?? [])
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
  }, [poeData]);

  return (
    <AppShell
      active="poe"
      roleLabel={user?.role ?? "Authenticated"}
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
            <span>{poeData?.records.length ?? 0} items</span>
          </div>
          <div className="inventory-table-wrap">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Unit</th>
                  <th>Executed on</th>
                  <th>Status</th>
                  <th>Media</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {(poeData?.records ?? []).map((record) => {
                  const booking = bookingMap.get(record.booking);
                  const campaign = booking ? campaignMap.get(booking.campaign) : null;
                  const unit = booking ? unitMap.get(booking.media_unit) : null;

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
                      <td>{record.media_items.length}</td>
                      <td className="table-wrap">{record.notes || "No field notes recorded."}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!isLoading && (poeData?.records.length ?? 0) === 0 ? (
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
