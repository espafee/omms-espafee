"use client";

import { useEffect, useMemo, useState } from "react";

import {
  PublicCampaignAccessError,
  fetchPublicCampaignAccess,
  type PublicCampaignAccessPayload,
  type PublicPoeMedia,
} from "@/lib/public-campaign";

function formatDate(value: string) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function formatDateRange(startDate: string, endDate: string) {
  return `${formatDate(startDate)} - ${formatDate(endDate)}`;
}

function getMediaPreview(media: PublicPoeMedia) {
  return media.image_url || media.media_url || "";
}

export default function PublicCampaignPage({ params }: { params: { token: string } }) {
  const [payload, setPayload] = useState<PublicCampaignAccessPayload | null>(null);
  const [error, setError] = useState<PublicCampaignAccessError | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetchPublicCampaignAccess(params.token);
        if (isMounted) {
          setPayload(response);
        }
      } catch (loadError) {
        if (isMounted) {
          const normalized =
            loadError instanceof PublicCampaignAccessError
              ? loadError
              : new PublicCampaignAccessError(
                  "This campaign link is not available right now.",
                  500,
                  "access_unavailable",
                );
          setError(normalized);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void load();

    return () => {
      isMounted = false;
    };
  }, [params.token]);

  const summary = useMemo(() => {
    const bookings = payload?.campaign.bookings ?? [];
    const poeRecords = bookings.flatMap((booking) => booking.poe_records);

    return {
      totalBookings: bookings.length,
      liveBookings: bookings.filter((booking) => booking.status === "live").length,
      totalPoe: poeRecords.length,
      verifiedPoe: poeRecords.filter((record) => record.verification_status === "verified").length,
    };
  }, [payload]);

  const stateLabel =
    error?.code === "expired_token"
      ? "Expired link"
      : error?.code === "revoked_token"
        ? "Revoked link"
        : error?.code === "campaign_ended"
          ? "Campaign closed"
          : "Invalid link";

  return (
    <main className="public-shell">
      <section className="public-panel">
        {isLoading ? (
          <section className="module-card">
            <div className="module-head">
              <h2>Loading campaign link</h2>
              <span>Read only</span>
            </div>
            <p className="section-copy">
              We&apos;re fetching the latest campaign view for this secure link.
            </p>
          </section>
        ) : null}

        {!isLoading && error ? (
          <section className="module-card">
            <div className="module-head">
              <h2>{stateLabel}</h2>
              <span>Access unavailable</span>
            </div>
            <p className="error">{error.message}</p>
            <p className="section-copy">
              This public link is read only and only works while the share token is active and the campaign is still in
              progress.
            </p>
          </section>
        ) : null}

        {!isLoading && payload ? (
          <>
            <section className="module-card public-hero-card">
              <div className="module-head">
                <div>
                  <span className="eyebrow dashboard-eyebrow">Client Campaign View</span>
                  <h1 className="workspace-title public-title">{payload.campaign.name}</h1>
                </div>
                <span className={`status-pill status-${payload.campaign.status}`}>{payload.campaign.status}</span>
              </div>
              <p className="workspace-copy">
                {payload.campaign.objective || "No campaign objective was shared for this view."}
              </p>
              <div className="public-meta-grid">
                <div className="module-stat">
                  <p className="stat-label">Campaign code</p>
                  <p className="field-summary-value">{payload.campaign.code}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Timeline</p>
                  <p className="field-summary-value">
                    {formatDateRange(payload.campaign.start_date, payload.campaign.end_date)}
                  </p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Access valid until</p>
                  <p className="field-summary-value">
                    {payload.access_expires_at ? formatDate(payload.access_expires_at) : "Campaign end"}
                  </p>
                </div>
              </div>
            </section>

            <section className="summary-row" aria-label="Public campaign stats">
              <article className="summary-card">
                <p className="stat-label">Bookings</p>
                <p className="summary-value">{summary.totalBookings}</p>
              </article>
              <article className="summary-card">
                <p className="stat-label">Live placements</p>
                <p className="summary-value">{summary.liveBookings}</p>
              </article>
              <article className="summary-card">
                <p className="stat-label">POE records</p>
                <p className="summary-value">{summary.totalPoe}</p>
              </article>
              <article className="summary-card">
                <p className="stat-label">Verified POE</p>
                <p className="summary-value">{summary.verifiedPoe}</p>
              </article>
            </section>

            <section className="public-grid">
              <article className="module-card">
                <div className="module-head">
                  <h2>Approved creatives</h2>
                  <span>{payload.campaign.assets.length} items</span>
                </div>
                <div className="asset-list">
                  {payload.campaign.assets.map((asset) => (
                    <article className="asset-card" key={asset.id}>
                      <div className="asset-head">
                        <div>
                          <p className="site-code">{asset.asset_type}</p>
                          <h3>{asset.name}</h3>
                        </div>
                        <span className="status-pill status-approved">{asset.version}</span>
                      </div>
                      <a className="asset-link" href={asset.file_url} target="_blank" rel="noreferrer">
                        Open approved asset
                      </a>
                    </article>
                  ))}
                  {payload.campaign.assets.length === 0 ? (
                    <p className="empty-state">No approved campaign assets are available in this share view.</p>
                  ) : null}
                </div>
              </article>

              <article className="module-card">
                <div className="module-head">
                  <h2>Delivery overview</h2>
                  <span>Read only</span>
                </div>
                <div className="module-stats">
                  <div className="module-stat">
                    <p className="stat-label">Sharing mode</p>
                    <p className="field-summary-value">Secure token link</p>
                  </div>
                  <div className="module-stat">
                    <p className="stat-label">Evidence visibility</p>
                    <p className="table-wrap">Only linked booking progress and POE evidence are shown here.</p>
                  </div>
                  <div className="module-stat">
                    <p className="stat-label">Editing</p>
                    <p className="field-summary-value">Disabled</p>
                  </div>
                </div>
              </article>
            </section>

            <section className="module-card">
              <div className="module-head">
                <h2>Booked inventory and proof of execution</h2>
                <span>{payload.campaign.bookings.length} placements</span>
              </div>
              <div className="public-booking-grid">
                {payload.campaign.bookings.map((booking) => (
                  <article className="public-booking-card" key={booking.id}>
                    <div className="module-head">
                      <div>
                        <p className="site-code">{booking.media_unit.unit_code}</p>
                        <h3>{booking.site.name}</h3>
                      </div>
                      <span className={`status-pill status-${booking.status}`}>{booking.status}</span>
                    </div>
                    <div className="image-reference-card">
                      <div className="image-reference-frame">
                        {booking.site.primary_image?.image_url ? (
                          <img
                            className="image-reference-asset"
                            src={booking.site.primary_image.image_url}
                            alt={booking.site.primary_image.caption || booking.site.name}
                          />
                        ) : (
                          <div className="image-reference-empty">No site image available for this placement.</div>
                        )}
                      </div>
                      <div className="image-reference-copy">
                        <p className="section-copy">
                          <strong>{booking.site.code}</strong> in {booking.site.city}, {booking.site.state}
                        </p>
                        <p className="section-copy">
                          Scheduled for {formatDateRange(booking.start_date, booking.end_date)}
                        </p>
                        <p className="section-copy">
                          Unit status: <span className={`status-pill status-${booking.media_unit.status}`}>{booking.media_unit.status}</span>
                        </p>
                        <p className="section-copy">
                          Lighting: {booking.media_unit.is_illuminated ? "Illuminated" : "Non-illuminated"}
                        </p>
                      </div>
                    </div>

                    <div className="public-evidence-grid">
                      {booking.poe_records.map((record) => (
                        <article className="asset-card asset-card-media" key={record.id}>
                          <div className="asset-head">
                            <div>
                              <p className="site-code">POE {record.id}</p>
                              <h3>{formatDate(record.executed_on)}</h3>
                            </div>
                            <span className={`status-pill status-${record.verification_status}`}>
                              {record.verification_status}
                            </span>
                          </div>
                          <p className="site-copy">
                            Score: {record.verification_score ?? "Pending"} {record.verification_notes ? `• ${record.verification_notes}` : ""}
                          </p>
                          <div className="capture-preview-grid">
                            {record.media_items.map((media) => {
                              const preview = getMediaPreview(media);
                              return (
                                <article className="capture-preview-card" key={media.id}>
                                  {preview ? (
                                    <img
                                      className="capture-preview-image"
                                      src={preview}
                                      alt={`POE evidence ${media.id}`}
                                    />
                                  ) : (
                                    <div className="asset-image-placeholder">No preview available</div>
                                  )}
                                  <div className="capture-preview-name">
                                    <p className="site-copy">{media.media_type}</p>
                                    <p className="site-copy">{formatDate(media.captured_at)}</p>
                                  </div>
                                </article>
                              );
                            })}
                            {record.media_items.length === 0 ? (
                              <p className="empty-state">No POE evidence is attached yet for this placement.</p>
                            ) : null}
                          </div>
                        </article>
                      ))}
                      {booking.poe_records.length === 0 ? (
                        <p className="empty-state">No proof of execution has been published yet for this booking.</p>
                      ) : null}
                    </div>
                  </article>
                ))}
                {payload.campaign.bookings.length === 0 ? (
                  <p className="empty-state">No booked inventory is currently visible for this campaign link.</p>
                ) : null}
              </div>
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}
