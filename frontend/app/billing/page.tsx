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
      { label: "Total invoices", value: String(billingData.summary.total_invoices) },
      { label: "Outstanding", value: formatCurrency(billingData.summary.outstanding_amount) },
      { label: "Collected", value: formatCurrency(billingData.summary.total_paid) },
      { label: "Payments", value: String(billingData.summary.payment_count) },
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
      title="Billing desk"
      eyebrow="Billing"
      description="Track invoices, payment collection, overdue exposure, and billing status across your campaign portfolio from one live finance screen."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}

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
            <h2>Invoice status</h2>
            <span>Ledger</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Issued</p>
              <p className="stat-value">{isLoading ? "..." : billingData?.summary.issued_invoices ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Paid</p>
              <p className="stat-value">{isLoading ? "..." : billingData?.summary.paid_invoices ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Partially paid</p>
              <p className="stat-value">
                {isLoading ? "..." : billingData?.summary.partially_paid_invoices ?? 0}
              </p>
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
            <h2>Payment pulse</h2>
            <span>Collection</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Total paid</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(billingData?.summary.total_paid ?? "0.00")}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Payment entries</p>
              <p className="stat-value">{isLoading ? "..." : billingData?.summary.payment_count ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Outstanding amount</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(billingData?.summary.outstanding_amount ?? "0.00")}
              </p>
            </div>
          </div>
        </article>
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
                          <strong>{invoice.invoice_number}</strong>
                          <span>{invoice.lines.length} line item(s)</span>
                        </div>
                      </td>
                      <td>
                        <div className="table-primary">
                          <strong>{campaign?.name ?? `Campaign #${invoice.campaign}`}</strong>
                          <span>{campaign?.code ?? "Unknown code"}</span>
                        </div>
                      </td>
                      <td>{formatDate(invoice.issue_date)}</td>
                      <td>{formatDate(invoice.due_date)}</td>
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
            <p className="empty-state">No invoices are visible for the current account.</p>
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
