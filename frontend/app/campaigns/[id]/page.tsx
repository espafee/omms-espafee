"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { fetchCampaign, type Campaign } from "@/lib/campaigns";
import { formatCurrency } from "@/lib/dashboard";

type StoredUser = {
  email?: string;
  role?: string;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    const storedUser = getStoredUser();
    setUser(storedUser);
    const campaignId = Number(params.id);
    if (!Number.isInteger(campaignId) || campaignId <= 0) {
      setError("This campaign reference is invalid.");
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    async function load() {
      try {
        const [currentUser, campaignPayload] = await Promise.all([
          fetchCurrentUser(),
          fetchCampaign(campaignId),
        ]);
        if (isMounted) {
          setUser(currentUser ?? storedUser);
          setCampaign(campaignPayload);
        }
      } catch (loadError) {
        if (isMounted) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load this campaign.");
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
  }, [params.id, router]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  return (
    <AppShell
      active="campaigns"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title={campaign?.name ?? "Campaign details"}
      eyebrow="Campaign record"
      description="Internal campaign detail. Access follows your OMMS role and company permissions."
      onLogout={handleLogout}
    >
      <div className="campaign-detail-navigation">
        <Link className="ghost" href="/campaigns">← Back to campaign roster</Link>
        {campaign ? (
          <span className={`status-pill status-${campaign.effective_status}`}>
            {campaign.effective_status.replaceAll("_", " ")}
          </span>
        ) : null}
      </div>

      {error ? <p className="error dashboard-error">{error}</p> : null}
      {isLoading ? <p className="empty-state">Loading campaign details...</p> : null}

      {!isLoading && campaign ? (
        <>
          <section className="summary-row" aria-label="Campaign detail summary">
            <article className="summary-card">
              <p className="stat-label">Campaign code</p>
              <p className="summary-value campaign-detail-code">{campaign.code}</p>
            </article>
            <article className="summary-card">
              <p className="stat-label">POE completion</p>
              <p className="summary-value">{campaign.performance?.poe_completion_percentage ?? 0}%</p>
            </article>
            <article className="summary-card">
              <p className="stat-label">Pending POE</p>
              <p className="summary-value">{campaign.performance?.pending_poe_count ?? 0}</p>
            </article>
            <article className="summary-card">
              <p className="stat-label">Budget</p>
              <p className="summary-value campaign-detail-currency">{formatCurrency(campaign.budget)}</p>
            </article>
          </section>

          <section className="campaign-detail-layout">
            <article className="module-card">
              <div className="module-head">
                <h2>Campaign brief</h2>
                <span>Internal</span>
              </div>
              <div className="campaign-detail-facts">
                <div><span>Timeline</span><strong>{formatDate(campaign.start_date)} – {formatDate(campaign.end_date)}</strong></div>
                <div><span>Lifecycle</span><strong>{campaign.effective_status.replaceAll("_", " ")}</strong></div>
                <div><span>Administrative status</span><strong>{campaign.status.replaceAll("_", " ")}</strong></div>
                <div><span>Assets</span><strong>{campaign.assets.length}</strong></div>
                <div><span>Operational risk</span><strong>{(campaign.performance?.risk_status ?? "on_track").replaceAll("_", " ")}</strong></div>
                <div><span>Billing</span><strong>{(campaign.performance?.billing_status ?? "hidden").replaceAll("_", " ")}</strong></div>
              </div>
              <div className="campaign-detail-objective">
                <p className="stat-label">Objective</p>
                <p className="site-copy">{campaign.objective || "No objective has been added."}</p>
              </div>
            </article>

            <article className="module-card">
              <div className="module-head">
                <h2>Creative assets</h2>
                <span>{campaign.assets.length} items</span>
              </div>
              <div className="asset-list">
                {campaign.assets.map((asset) => (
                  <article className="asset-card" key={asset.id}>
                    <div className="asset-head">
                      <div>
                        <p className="site-code">{asset.asset_type}</p>
                        <h3>{asset.name}</h3>
                      </div>
                      <span className={`status-pill ${asset.is_approved ? "status-approved" : "status-draft"}`}>
                        {asset.is_approved ? "approved" : "pending"}
                      </span>
                    </div>
                    <p className="site-copy">Version {asset.version}</p>
                    <a className="asset-link" href={asset.file_url} target="_blank" rel="noreferrer">Open asset</a>
                  </article>
                ))}
                {campaign.assets.length === 0 ? <p className="empty-state">No assets are attached to this campaign.</p> : null}
              </div>
            </article>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
