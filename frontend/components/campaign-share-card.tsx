"use client";

import type { Campaign } from "@/lib/campaigns";
import {
  getShareLinkStatusLabel,
  type CampaignAccessLink,
  type CampaignAccessLinkStatus,
} from "@/lib/campaign-share-links";

type CampaignShareCardProps = {
  campaign: Campaign;
  accessLink: CampaignAccessLink | null;
  accessLinkUrl: string | null;
  status: CampaignAccessLinkStatus | null;
  isLoading: boolean;
  isActing: boolean;
  onGenerate: (campaignId: number) => Promise<void>;
  onCopy: (url: string) => Promise<void>;
  onRevoke: (link: CampaignAccessLink) => Promise<void>;
};

function formatDate(value: string | null) {
  if (!value) {
    return "No expiry";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function CampaignShareCard({
  campaign,
  accessLink,
  accessLinkUrl,
  status,
  isLoading,
  isActing,
  onGenerate,
  onCopy,
  onRevoke,
}: CampaignShareCardProps) {
  const statusLabel = status ? getShareLinkStatusLabel(status) : "no link";
  const canGenerate = !accessLink || status !== "active";
  const canCopy = Boolean(accessLinkUrl);
  const canRevoke = Boolean(accessLink && status === "active");

  return (
    <article className="module-card campaign-share-card">
      <div className="module-head">
        <div>
          <p className="site-code">{campaign.code}</p>
          <h2>{campaign.name}</h2>
        </div>
        <span className={`status-pill ${status ? `status-${status}` : "status-draft"}`}>{statusLabel}</span>
      </div>

      <div className="module-stats">
        <div className="module-stat">
          <p className="stat-label">Timeline</p>
          <p className="site-copy">
            {campaign.start_date} to {campaign.end_date}
          </p>
        </div>

        <div className="module-stat">
          <p className="stat-label">Link status</p>
          <p className="site-copy">
            {accessLink
              ? `Prefix ${accessLink.token_prefix} • ${statusLabel}`
              : "No client share link has been generated yet."}
          </p>
        </div>

        {accessLink ? (
          <div className="module-stat">
            <p className="stat-label">Expiry</p>
            <p className="site-copy">{formatDate(accessLink.expires_at)}</p>
          </div>
        ) : null}
      </div>

      <div className="field field-full campaign-share-link-field">
        <label htmlFor={`campaign-share-${campaign.id}`}>Client share link</label>
        <input
          id={`campaign-share-${campaign.id}`}
          value={accessLinkUrl ?? ""}
          placeholder={
            accessLink
              ? "Full link is available on this device only if it was generated here."
              : "Generate a secure link to share this campaign with the client."
          }
          readOnly
        />
        {accessLink && !accessLinkUrl ? (
          <p className="field-help">
            This token exists, but the full URL was not generated in this browser. Revoke it and generate a fresh link here if you need to copy it again.
          </p>
        ) : null}
      </div>

      <div className="campaign-share-actions">
        <button
          className="submit"
          type="button"
          disabled={isLoading || isActing || !canGenerate}
          onClick={() => void onGenerate(campaign.id)}
        >
          {isActing && canGenerate ? "Generating..." : "Generate Link"}
        </button>
        <button
          className="ghost"
          type="button"
          disabled={isLoading || isActing || !canCopy}
          onClick={() => accessLinkUrl && void onCopy(accessLinkUrl)}
        >
          Copy
        </button>
        <button
          className="ghost ghost-danger"
          type="button"
          disabled={isLoading || isActing || !canRevoke}
          onClick={() => accessLink && void onRevoke(accessLink)}
        >
          {isActing && canRevoke ? "Revoking..." : "Revoke"}
        </button>
      </div>
    </article>
  );
}
