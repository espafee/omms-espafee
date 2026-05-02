"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { fetchBillingData, type BillingPayload } from "@/lib/billing";
import { formatCurrency } from "@/lib/dashboard";

type StoredUser = {
  email?: string;
  role?: string;
};

function formatDate(dateValue: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(dateValue));
}

export default function BillingPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [billingData, setBillingData] = useState<BillingPayload | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

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

    async function loadBilling() {
      setIsLoading(true);
      setError("");

      try {
        const [profile, payload] = await Promise.all([fetchCurrentUser(), fetchBillingData()]);
        if (profile) {
          setUser(profile);
        }
        setBillingData(payload);
      } catch (loadError) {
        const message = loadError instanceof Error ? loadError.message : "Unable to load billing data.";
        setError(message);
        if (message.includes("sign in again")) {
          router.replace("/login");
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadBilling();
  }, [router]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  const campaignMap = useMemo(() => {
    const map = new Map<number, { name: string; code: string }>();
    for (const campaign of billingData?.campaigns ?? []) {
      map.set(campaign.id, { name: campaign.name, code: campaign.code });
    }
    return map;
  }, [billingData]);

  const quickStats = useMemo(() => {
    if (!billingData) {
      return [];
    }

    return [
      { label: "Campaign estimates", value: String(billingData.estimates.length) },
      { label: "Finalized estimates", value: String(billingData.estimates.filter((estimate) => estimate.status === "finalized").length) },
      { label: "Generated invoices", value: String(billingData.summary.total_invoices) },
      { label: "Outstanding", value: formatCurrency(billingData.summary.outstanding_amount) },
    ];
  }, [billingData]);

  const recentPayments = useMemo(() => {
    return (billingData?.invoices ?? [])
      .flatMap((invoice) =>
        invoice.payments.map((payment) => ({
          ...payment,
          invoiceNumber: invoice.invoice_number,
        })),
      )
      .sort((left, right) => right.payment_date.localeCompare(left.payment_date))
      .slice(0, 6);
  }, [billingData]);

  return (
    <AppShell
      active="billing"
      roleLabel={user?.role ?? "Authenticated"}
      userEmail={user?.email ?? "Loading user..."}
      title="Estimate and invoice desk"
      eyebrow="Billing"
      description="Campaign Estimate is shared before booking. Invoice is generated after campaign starts."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}

      <section className="module-card creation-panel">
        <div className="module-head">
          <div>
            <h2>Campaign Estimate → Client Approval → Booking → Invoice</h2>
            <p className="section-copy">
              Create a Campaign Estimate before booking inventory, share it for approval, finalize it, then create confirmed bookings. Invoices are generated from confirmed bookings only once the campaign start date is today or in the past.
            </p>
          </div>
          <span>Lifecycle</span>
        </div>
        <div className="campaign-share-actions">
          <button className="submit" type="button" onClick={() => router.push("/campaigns")}>
            Create Campaign Estimate
          </button>
          <button className="ghost" type="button" onClick={() => router.push("/bookings")}>
            Generate Invoice
          </button>
        </div>
      </section>

      <section className="summary-row" aria-label="Billing stats">
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
            <h2>Campaign Estimate status</h2>
            <span>Pre-booking</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Draft/shared</p>
              <p className="stat-value">
                {isLoading ? "..." : (billingData?.estimates ?? []).filter((estimate) => ["draft", "shared"].includes(estimate.status)).length}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Approved</p>
              <p className="stat-value">
                {isLoading ? "..." : (billingData?.estimates ?? []).filter((estimate) => estimate.status === "approved").length}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Finalized</p>
              <p className="stat-value">{isLoading ? "..." : (billingData?.estimates ?? []).filter((estimate) => estimate.status === "finalized").length}</p>
            </div>
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Exposure watch</h2>
            <span>Risk</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Total invoiced</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(billingData?.summary.total_invoiced ?? "0.00")}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Overdue invoices</p>
              <p className="stat-value">{isLoading ? "..." : billingData?.summary.overdue_invoices ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Overdue amount</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(billingData?.summary.overdue_amount ?? "0.00")}
              </p>
            </div>
          </div>
        </article>

        <article className="module-card module-card-highlight">
          <div className="module-head">
            <h2>Invoice status</h2>
            <span>Post-start</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Issued</p>
              <p className="stat-value">{isLoading ? "..." : billingData?.summary.issued_invoices ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Paid</p>
              <p className="stat-value">
                {isLoading ? "..." : billingData?.summary.paid_invoices ?? 0}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Collected</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(billingData?.summary.total_paid ?? "0.00")}
              </p>
            </div>
          </div>
        </article>
      </section>

      <section className="module-card module-card-wide inventory-section">
        <div className="module-head">
          <h2>Campaign Estimate roster</h2>
          <span>{billingData?.estimates.length ?? 0} items</span>
        </div>
        <div className="inventory-table-wrap">
          <table className="inventory-table">
            <thead>
              <tr>
                <th>Campaign Estimate</th>
                <th>Client</th>
                <th>Proposed dates</th>
                <th>Status</th>
                <th>Total</th>
                <th>Lines</th>
              </tr>
            </thead>
            <tbody>
              {(billingData?.estimates ?? []).map((estimate) => (
                <tr key={estimate.id}>
                  <td>
                    <div className="table-primary">
                      <strong>{estimate.estimate_number ?? "Draft estimate"}</strong>
                      <span>{estimate.title}</span>
                    </div>
                  </td>
                  <td>{estimate.client_name}</td>
                  <td>{formatDate(estimate.start_date)} - {formatDate(estimate.end_date)}</td>
                  <td>
                    <span className={`status-pill status-${estimate.status}`}>{estimate.status}</span>
                  </td>
                  <td>{formatCurrency(estimate.total_amount)}</td>
                  <td>{estimate.lines.length} proposed item(s)</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!isLoading && (billingData?.estimates.length ?? 0) === 0 ? (
          <p className="empty-state">No Campaign Estimates yet. Start with “Create Campaign Estimate” before booking inventory.</p>
        ) : null}
      </section>

      <section className="billing-layout">
        <article className="module-card module-card-wide">
          <div className="module-head">
            <h2>Invoice roster</h2>
            <span>{billingData?.invoices.length ?? 0} items</span>
          </div>
          <div className="inventory-table-wrap">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Campaign</th>
                  <th>Issue date</th>
                  <th>Due date</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Paid</th>
                </tr>
              </thead>
              <tbody>
                {(billingData?.invoices ?? []).map((invoice) => {
                  const campaign = campaignMap.get(invoice.campaign);
                  const totalPaid = invoice.payments.reduce(
                    (sum, payment) => sum + Number(payment.amount),
                    0,
                  );

                  return (
                    <tr key={invoice.id}>
                      <td>
                        <div className="table-primary">
                          <strong>{invoice.invoice_number ?? "Draft invoice"}</strong>
                          <span>{invoice.lines.length} line item(s)</span>
                        </div>
                      </td>
                      <td>
                        <div className="table-primary">
                          <strong>{campaign?.name ?? `Campaign #${invoice.campaign}`}</strong>
                          <span>{campaign?.code ?? "Unknown code"}</span>
                        </div>
                      </td>
                      <td>{invoice.issue_date ? formatDate(invoice.issue_date) : "Draft"}</td>
                      <td>{invoice.due_date ? formatDate(invoice.due_date) : "Not set"}</td>
                      <td>
                        <span className={`status-pill status-${invoice.status}`}>{invoice.status.replaceAll("_", " ")}</span>
                      </td>
                      <td>{formatCurrency(invoice.total_amount)}</td>
                      <td>{formatCurrency(String(totalPaid))}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!isLoading && (billingData?.invoices.length ?? 0) === 0 ? (
            <p className="empty-state">No invoices yet. Generate Invoice after the campaign starts and bookings are confirmed.</p>
          ) : null}
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Recent payments</h2>
            <span>Receipts</span>
          </div>
          <div className="asset-list">
            {recentPayments.map((payment) => (
              <article className="asset-card" key={payment.id}>
                <div className="asset-head">
                  <div>
                    <p className="site-code">{payment.invoiceNumber}</p>
                    <h3>{formatCurrency(payment.amount)}</h3>
                  </div>
                  <span className="status-pill status-paid">{payment.method.replaceAll("_", " ")}</span>
                </div>
                <p className="site-copy">Paid on {formatDate(payment.payment_date)}</p>
                <p className="site-copy">{payment.reference_number || "No reference number recorded."}</p>
              </article>
            ))}
            {!isLoading && recentPayments.length === 0 ? (
              <p className="empty-state">No payments are available for the current billing scope.</p>
            ) : null}
          </div>
        </article>
      </section>
    </AppShell>
  );
}
