"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, getAccessToken, getStoredUser, type AuthUser } from "@/lib/auth";

const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";

type TrainingGuide = {
  slug: string;
  title: string;
  audience: string;
  description: string;
  allowedRoles?: string[];
};

const ADMIN_ROLES = new Set(["admin", "super_admin", "owner"]);

const trainingGuides: TrainingGuide[] = [
  {
    slug: "master-manual",
    title: "OMMS Master Training Manual",
    audience: "All OMMS users",
    description: "Complete onboarding handbook for the OMMS lifecycle, daily workflows, security, and troubleshooting.",
  },
  {
    slug: "field-staff",
    title: "Field Staff Training Guide",
    audience: "Field staff and execution teams",
    description: "Daily mobile workflow for assigned work, POE upload, GPS capture, issue reporting, and replacement POE.",
    allowedRoles: ["admin", "super_admin", "owner", "operations", "field_staff"],
  },
  {
    slug: "finance-team",
    title: "Finance Team Guide",
    audience: "Finance and accounts teams",
    description: "Campaign estimates, GST-ready invoices, payment recording, overdue follow-up, and client statements.",
    allowedRoles: ["admin", "super_admin", "owner", "finance"],
  },
  {
    slug: "operations-team",
    title: "Operations Team Guide",
    audience: "Operations managers",
    description: "Campaign execution, assignment visibility, POE review, issue handling, alerts, and daily monitoring.",
    allowedRoles: ["admin", "super_admin", "owner", "operations"],
  },
  {
    slug: "inventory-management",
    title: "Inventory Management Guide",
    audience: "Inventory managers",
    description: "Clean site records, media units, photos, dimensions, availability, and first verified POE GPS strategy.",
    allowedRoles: ["admin", "super_admin", "owner", "operations", "inventory"],
  },
  {
    slug: "admin-super-admin",
    title: "Admin and Super Admin Guide",
    audience: "Admins and owners",
    description: "Setup, users, permissions, diagnostics, notifications, audit trails, imports, exports, and controls.",
    allowedRoles: ["admin", "super_admin", "owner"],
  },
];

function canViewGuide(role: string | undefined, guide: TrainingGuide) {
  if (!guide.allowedRoles?.length) {
    return true;
  }
  if (!role) {
    return false;
  }
  return ADMIN_ROLES.has(role) || guide.allowedRoles.includes(role);
}

export default function TrainingPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [downloadingSlug, setDownloadingSlug] = useState("");

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    setUser(getStoredUser());
    setIsReady(true);
  }, [router]);

  const visibleGuides = useMemo(
    () => trainingGuides.filter((guide) => canViewGuide(user?.role, guide)),
    [user?.role],
  );

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  async function handleOpenGuide(guide: TrainingGuide) {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    setDownloadError("");
    setDownloadingSlug(guide.slug);

    try {
      const response = await fetch(
        `${API_ROOT.replace(/\/$/, "")}/training/documents/${guide.slug}/download/`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (response.status === 401) {
        clearAuthSession();
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error("Training document could not be opened.");
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const downloadLink = document.createElement("a");
      downloadLink.href = objectUrl;
      downloadLink.download = `${guide.title}.pdf`;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      downloadLink.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
    } catch {
      setDownloadError("We could not open this training document. Please try again or contact an admin.");
    } finally {
      setDownloadingSlug("");
    }
  }

  return (
    <AppShell
      active="training"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title="Training and help center"
      description="Access OMMS manuals, role-based training guides, onboarding documents, and future help resources."
      onLogout={handleLogout}
    >
      <section className="summary-row" aria-label="Training summary">
        <article className="summary-card">
          <p className="stat-label">Available guides</p>
          <p className="summary-value">{isReady ? visibleGuides.length : "..."}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Role visibility</p>
          <p className="summary-value">{user?.role ? user.role.replace("_", " ") : "..."}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Formats</p>
          <p className="summary-value">PDF</p>
        </article>
      </section>

      <section className="training-grid" aria-label="OMMS training documents">
        {visibleGuides.map((guide) => (
          <article className="module-card training-card" key={guide.slug} data-testid={`training-card-${guide.slug}`}>
            <div className="module-head">
              <h2>{guide.title}</h2>
              <span>{guide.audience}</span>
            </div>
            <p className="site-copy">{guide.description}</p>
            <div className="form-actions">
              <button
                className="submit training-download"
                data-testid={`training-download-${guide.slug}`}
                disabled={downloadingSlug === guide.slug}
                onClick={() => handleOpenGuide(guide)}
                type="button"
              >
                {downloadingSlug === guide.slug ? "Opening..." : "Open PDF"}
              </button>
            </div>
          </article>
        ))}
      </section>

      {downloadError ? <p className="error">{downloadError}</p> : null}

      {isReady && visibleGuides.length === 0 ? (
        <p className="empty-state">No training guides are assigned to your role yet. Please contact an admin.</p>
      ) : null}
    </AppShell>
  );
}
