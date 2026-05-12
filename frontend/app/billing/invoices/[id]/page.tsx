"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  cancelInvoice,
  createInvoicePayment,
  downloadInvoicePdf,
  fetchInvoice,
  getInvoiceActionError,
  type Invoice,
  type InvoicePaymentCreateInput,
} from "@/lib/billing";
import { formatCurrency } from "@/lib/dashboard";

type StoredUser = {
  email?: string;
  role?: string;
};

const WRITE_ROLES = new Set(["admin", "finance"]);
const PAYMENT_MODE_OPTIONS = [
  { value: "bank_transfer", label: "Bank transfer" },
  { value: "cash", label: "Cash" },
  { value: "card", label: "Card" },
  { value: "cheque", label: "Cheque" },
];

function formatDate(dateValue: string | null | undefined) {
  if (!dateValue) {
    return "Not set";
  }
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(new Date(dateValue));
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

function getTodayLocalIsoDate() {
  const now = new Date();
  const timezoneOffsetMs = now.getTimezoneOffset() * 60 * 1000;
  return new Date(now.getTime() - timezoneOffsetMs).toISOString().slice(0, 10);
}

function parseMoney(value: string | number | null | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function saveBlobDownload(blob: Blob, filename: string) {
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 60_000);
}

export default function InvoiceDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const invoiceId = Number(params.id);
  const [user, setUser] = useState<StoredUser | null>(null);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [paymentForm, setPaymentForm] = useState<InvoicePaymentCreateInput>({
    amount: "",
    payment_date: getTodayLocalIsoDate(),
    payment_mode: "bank_transfer",
    reference_number: "",
    notes: "",
  });
  const [voidForm, setVoidForm] = useState({
    reason: "",
    credit_amount: "",
    credit_date: getTodayLocalIsoDate(),
    credit_method: "bank_transfer",
    credit_reference_number: "",
    credit_notes: "",
  });
  const [auditFilter, setAuditFilter] = useState("");
  const [auditSearch, setAuditSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingPayment, setIsSavingPayment] = useState(false);
  const [isVoiding, setIsVoiding] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const canManageBilling = WRITE_ROLES.has(user?.role ?? "");

  const loadInvoice = useCallback(async () => {
    if (!invoiceId) {
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const profile = await fetchCurrentUser();
      if (profile) {
        setUser(profile);
      }
      const payload = await fetchInvoice(invoiceId);
      setInvoice(payload);
      setPaymentForm((current) => ({
        ...current,
        amount: parseMoney(payload.balance_due) > 0 ? parseMoney(payload.balance_due).toFixed(2) : "",
      }));
      setVoidForm((current) => ({
        ...current,
        credit_amount: parseMoney(payload.amount_paid) > 0 ? parseMoney(payload.amount_paid).toFixed(2) : "",
      }));
    } catch (loadError) {
      const nextMessage = loadError instanceof Error ? loadError.message : "Unable to load invoice.";
      setError(nextMessage);
      if (nextMessage.includes("sign in again")) {
        router.replace("/login");
      }
    } finally {
      setIsLoading(false);
    }
  }, [invoiceId, router]);

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
    void loadInvoice();
  }, [loadInvoice, router]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  function updatePaymentForm<K extends keyof InvoicePaymentCreateInput>(field: K, value: InvoicePaymentCreateInput[K]) {
    setError("");
    setMessage("");
    setPaymentForm((current) => ({ ...current, [field]: value }));
  }

  function updateVoidForm(field: keyof typeof voidForm, value: string) {
    setError("");
    setMessage("");
    setVoidForm((current) => ({ ...current, [field]: value }));
  }

  const isInvoicePayable = Boolean(
    invoice &&
      canManageBilling &&
      !["draft", "cancelled", "paid"].includes(invoice.payment_status) &&
      parseMoney(invoice.balance_due) > 0,
  );

  const filteredEvents = useMemo(() => {
    const search = auditSearch.trim().toLowerCase();
    return (invoice?.events ?? []).filter((event) => {
      if (auditFilter && event.event_type !== auditFilter) {
        return false;
      }
      if (!search) {
        return true;
      }
      return [event.event_type, event.message, event.actor_name, event.from_status, event.to_status]
        .join(" ")
        .toLowerCase()
        .includes(search);
    });
  }, [auditFilter, auditSearch, invoice]);

  async function handleRecordPayment() {
    if (!invoice || !isInvoicePayable || isSavingPayment) {
      return;
    }
    const amount = parseMoney(paymentForm.amount);
    if (amount <= 0 || amount > parseMoney(invoice.balance_due)) {
      setError(`Payment must be greater than zero and not exceed ${formatCurrency(invoice.balance_due)}.`);
      return;
    }
    if (!paymentForm.payment_date) {
      setError("Payment date is required.");
      return;
    }
    setIsSavingPayment(true);
    setError("");
    setMessage("");
    try {
      await createInvoicePayment(invoice.id, { ...paymentForm, amount: amount.toFixed(2) });
      setMessage("Payment recorded and invoice balance refreshed.");
      await loadInvoice();
    } catch (paymentError) {
      setError(getInvoiceActionError(paymentError));
    } finally {
      setIsSavingPayment(false);
    }
  }

  async function handleVoidInvoice() {
    if (!invoice || !canManageBilling || isVoiding) {
      return;
    }
    if (!voidForm.reason.trim()) {
      setError("Void reason is required.");
      return;
    }
    const hasPayments = parseMoney(invoice.amount_paid) > 0;
    if (hasPayments && (!voidForm.credit_amount || !voidForm.credit_date || !voidForm.credit_method)) {
      setError("Credit/refund amount, date, and method are required when voiding an invoice with payments.");
      return;
    }
    setIsVoiding(true);
    setError("");
    setMessage("");
    try {
      await cancelInvoice(invoice.id, {
        reason: voidForm.reason.trim(),
        ...(hasPayments
          ? {
              credit_amount: parseMoney(voidForm.credit_amount).toFixed(2),
              credit_date: voidForm.credit_date,
              credit_method: voidForm.credit_method,
              credit_reference_number: voidForm.credit_reference_number,
              credit_notes: voidForm.credit_notes,
            }
          : {}),
      });
      setMessage("Invoice voided. Payment history and credit/refund trail were preserved.");
      await loadInvoice();
    } catch (voidError) {
      setError(getInvoiceActionError(voidError));
    } finally {
      setIsVoiding(false);
    }
  }

  async function handleDownloadInvoice() {
    if (!invoice || isDownloading) {
      return;
    }
    setIsDownloading(true);
    setError("");
    setMessage("");
    try {
      const { blob, filename } = await downloadInvoicePdf(invoice.id);
      saveBlobDownload(blob, filename);
      setMessage("Invoice PDF downloaded.");
      await loadInvoice();
    } catch (downloadError) {
      setError(getInvoiceActionError(downloadError));
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <AppShell
      active="billing"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title="Invoice detail"
      eyebrow="Finance control"
      description="Review invoice metadata, payment history, audit trail, PDF actions, and controlled void workflow."
      onLogout={handleLogout}
    >
      <div className="form-actions">
        <Link className="ghost" href="/billing">
          Back to billing
        </Link>
      </div>
      {error ? <p className="error dashboard-error">{error}</p> : null}
      {message ? <p className="success dashboard-error">{message}</p> : null}
      {isLoading || !invoice ? (
        <section className="module-card">
          <p className="empty-state">{isLoading ? "Loading invoice..." : "Invoice not found."}</p>
        </section>
      ) : (
        <>
          <section className="summary-row">
            <article className="summary-card">
              <p className="stat-label">Invoice</p>
              <p className="summary-value">{invoice.invoice_number ?? `Draft #${invoice.id}`}</p>
            </article>
            <article className="summary-card">
              <p className="stat-label">Status</p>
              <p className="summary-value">{invoice.payment_status.replaceAll("_", " ")}</p>
            </article>
            <article className="summary-card">
              <p className="stat-label">Paid</p>
              <p className="summary-value">{formatCurrency(invoice.amount_paid)}</p>
            </article>
            <article className="summary-card">
              <p className="stat-label">Balance</p>
              <p className="summary-value">{formatCurrency(invoice.balance_due)}</p>
            </article>
          </section>

          <section className="billing-layout">
            <article className="module-card module-card-wide">
              <div className="module-head">
                <h2>Invoice metadata</h2>
                <span>{invoice.status}</span>
              </div>
              <div className="module-stats">
                <div className="module-stat">
                  <p className="stat-label">Campaign</p>
                  <p className="field-summary-value">Campaign #{invoice.campaign}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Issue date</p>
                  <p className="field-summary-value">{formatDate(invoice.issue_date)}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Due date</p>
                  <p className="field-summary-value">{formatDate(invoice.due_date)}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Total</p>
                  <p className="field-summary-value">{formatCurrency(invoice.invoice_total)}</p>
                </div>
              </div>
              <div className="form-actions">
                <button className="ghost" type="button" disabled={isDownloading} onClick={() => void handleDownloadInvoice()}>
                  {isDownloading ? "Preparing PDF..." : "Download PDF"}
                </button>
              </div>
              <div className="inventory-table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Description</th>
                      <th>Period</th>
                      <th>Rate</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoice.lines.map((line, index) => (
                      <tr key={line.id}>
                        <td>{index + 1}</td>
                        <td>
                          <div className="table-primary">
                            <strong>{line.description || "Outdoor media service"}</strong>
                            <span>{[line.site_name, line.media_unit_label].filter(Boolean).join(" / ")}</span>
                          </div>
                        </td>
                        <td>{formatDate(line.booking_start_date)} - {formatDate(line.booking_end_date)}</td>
                        <td>{formatCurrency(line.unit_price)}</td>
                        <td>{formatCurrency(line.line_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="module-card">
              <div className="module-head">
                <h2>Record payment</h2>
                <span>Collections</span>
              </div>
              <div className="campaign-form-grid">
                <div className="field">
                  <label htmlFor="detail-payment-amount">Amount</label>
                  <input id="detail-payment-amount" type="number" min="0" max={invoice.balance_due} step="0.01" value={paymentForm.amount} onChange={(event) => updatePaymentForm("amount", event.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="detail-payment-date">Payment date</label>
                  <input id="detail-payment-date" type="date" value={paymentForm.payment_date} onChange={(event) => updatePaymentForm("payment_date", event.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="detail-payment-mode">Payment mode</label>
                  <select id="detail-payment-mode" value={paymentForm.payment_mode} onChange={(event) => updatePaymentForm("payment_mode", event.target.value)}>
                    {PAYMENT_MODE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="detail-payment-reference">Reference</label>
                  <input id="detail-payment-reference" value={paymentForm.reference_number} onChange={(event) => updatePaymentForm("reference_number", event.target.value)} />
                </div>
                <div className="field field-full">
                  <label htmlFor="detail-payment-notes">Notes</label>
                  <textarea id="detail-payment-notes" rows={3} value={paymentForm.notes} onChange={(event) => updatePaymentForm("notes", event.target.value)} />
                </div>
                <div className="form-actions field-full">
                  <button className="submit" type="button" disabled={!isInvoicePayable || isSavingPayment} onClick={() => void handleRecordPayment()}>
                    {isSavingPayment ? "Saving..." : "Record Payment"}
                  </button>
                </div>
              </div>
            </article>
          </section>

          <section className="module-grid">
            <article className="module-card">
              <div className="module-head">
                <h2>Payments</h2>
                <span>{invoice.payments.length}</span>
              </div>
              <div className="asset-list">
                {invoice.payments.map((payment) => (
                  <article className="asset-card" key={payment.id}>
                    <div className="asset-head">
                      <div>
                        <p className="site-code">{formatDate(payment.payment_date)}</p>
                        <h3>{formatCurrency(payment.amount)}</h3>
                      </div>
                      <span className="status-pill status-paid">{payment.method.replaceAll("_", " ")}</span>
                    </div>
                    <p className="site-copy">{payment.reference_number || "No reference recorded."}</p>
                    <p className="site-copy">{payment.recorded_by_name || "Recorded by system"}</p>
                    <p className="site-copy">{payment.notes || "No notes."}</p>
                  </article>
                ))}
                {invoice.payments.length === 0 ? <p className="empty-state">No payments recorded yet.</p> : null}
              </div>
            </article>

            <article className="module-card">
              <div className="module-head">
                <h2>Void / credit control</h2>
                <span>Audit-safe</span>
              </div>
              <div className="campaign-form-grid">
                <div className="field field-full">
                  <label htmlFor="void-reason">Void reason</label>
                  <textarea id="void-reason" rows={3} value={voidForm.reason} onChange={(event) => updateVoidForm("reason", event.target.value)} />
                </div>
                {parseMoney(invoice.amount_paid) > 0 ? (
                  <>
                    <div className="field">
                      <label htmlFor="credit-amount">Credit/refund amount</label>
                      <input id="credit-amount" type="number" min="0" max={invoice.amount_paid} step="0.01" value={voidForm.credit_amount} onChange={(event) => updateVoidForm("credit_amount", event.target.value)} />
                    </div>
                    <div className="field">
                      <label htmlFor="credit-date">Credit/refund date</label>
                      <input id="credit-date" type="date" value={voidForm.credit_date} onChange={(event) => updateVoidForm("credit_date", event.target.value)} />
                    </div>
                    <div className="field">
                      <label htmlFor="credit-method">Method</label>
                      <select id="credit-method" value={voidForm.credit_method} onChange={(event) => updateVoidForm("credit_method", event.target.value)}>
                        {PAYMENT_MODE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                        <option value="adjustment">Ledger adjustment</option>
                      </select>
                    </div>
                    <div className="field">
                      <label htmlFor="credit-reference">Reference</label>
                      <input id="credit-reference" value={voidForm.credit_reference_number} onChange={(event) => updateVoidForm("credit_reference_number", event.target.value)} />
                    </div>
                    <div className="field field-full">
                      <label htmlFor="credit-notes">Credit/refund notes</label>
                      <textarea id="credit-notes" rows={3} value={voidForm.credit_notes} onChange={(event) => updateVoidForm("credit_notes", event.target.value)} />
                    </div>
                  </>
                ) : null}
                <div className="form-actions field-full">
                  <button className="ghost" type="button" disabled={!canManageBilling || invoice.status === "cancelled" || isVoiding} onClick={() => void handleVoidInvoice()}>
                    {isVoiding ? "Voiding..." : "Void invoice"}
                  </button>
                </div>
              </div>
              {invoice.credit_notes.length > 0 ? (
                <div className="asset-list">
                  {invoice.credit_notes.map((creditNote) => (
                    <article className="asset-card" key={creditNote.id}>
                      <div className="asset-head">
                        <div>
                          <p className="site-code">{formatDate(creditNote.credit_date)}</p>
                          <h3>{formatCurrency(creditNote.amount)}</h3>
                        </div>
                        <span className="status-pill status-cancelled">{creditNote.method.replaceAll("_", " ")}</span>
                      </div>
                      <p className="site-copy">{creditNote.reason}</p>
                      <p className="site-copy">{creditNote.reference_number || "No reference recorded."}</p>
                    </article>
                  ))}
                </div>
              ) : null}
            </article>

            <article className="module-card module-card-wide">
              <div className="module-head">
                <h2>Audit trail</h2>
                <span>{filteredEvents.length} event(s)</span>
              </div>
              <div className="campaign-form-grid">
                <div className="field">
                  <label htmlFor="audit-type">Event type</label>
                  <select id="audit-type" value={auditFilter} onChange={(event) => setAuditFilter(event.target.value)}>
                    <option value="">All events</option>
                    {[...new Set((invoice.events ?? []).map((event) => event.event_type))].map((eventType) => (
                      <option key={eventType} value={eventType}>{eventType.replaceAll("_", " ")}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="audit-search">Search</label>
                  <input id="audit-search" value={auditSearch} onChange={(event) => setAuditSearch(event.target.value)} placeholder="User, status, message" />
                </div>
              </div>
              <div className="asset-list">
                {filteredEvents.map((event) => (
                  <article className="asset-card" key={event.id}>
                    <div className="asset-head">
                      <div>
                        <p className="site-code">{event.event_type.replaceAll("_", " ")}</p>
                        <h3>{formatDateTime(event.created_at)}</h3>
                      </div>
                      <span className={`status-pill status-${event.to_status || invoice.status}`}>{event.to_status || invoice.status}</span>
                    </div>
                    <p className="site-copy">{event.message || "Invoice event recorded."}</p>
                    <p className="site-copy">{event.actor_name ? `By ${event.actor_name}` : "System event"}</p>
                  </article>
                ))}
                {filteredEvents.length === 0 ? <p className="empty-state">No audit events match the current filters.</p> : null}
              </div>
            </article>
          </section>
        </>
      )}
    </AppShell>
  );
}
