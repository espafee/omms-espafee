"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  cancelInvoice,
  createInvoicePayment,
  createCampaignEstimate,
  createCampaignEstimateLine,
  downloadInvoicePdf,
  fetchBillingData,
  fetchCampaignInvoicePreview,
  fetchClientStatement,
  generateCampaignInvoice,
  getInvoiceActionError,
  shareCampaignEstimate,
  type BillingPayload,
  type CampaignEstimate,
  type CampaignInvoicePreview,
  type ClientStatement,
  type Invoice,
  type InvoicePaymentCreateInput,
} from "@/lib/billing";
import { type Campaign } from "@/lib/campaigns";
import { formatCurrency } from "@/lib/dashboard";
import { fetchInventoryData, type InventoryUnit } from "@/lib/inventory";
import { fetchClients, type ClientOption } from "@/lib/users";

type StoredUser = {
  email?: string;
  role?: string;
};

type EstimateLineDraft = {
  localId: number;
  media_unit: number | null;
  description: string;
  start_date: string;
  end_date: string;
  quantity: string;
  unit_rate: string;
  tax_rate: string;
};

type EstimateFormState = {
  client: number;
  campaign: number | null;
  title: string;
  start_date: string;
  end_date: string;
  notes: string;
  lines: EstimateLineDraft[];
};

const WRITE_ROLES = new Set(["admin", "finance"]);
const PAYMENT_MODE_OPTIONS = [
  { value: "bank_transfer", label: "Bank transfer" },
  { value: "cash", label: "Cash" },
  { value: "card", label: "Card" },
  { value: "cheque", label: "Cheque" },
];

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

function getTodayLocalIsoDate() {
  const now = new Date();
  const timezoneOffsetMs = now.getTimezoneOffset() * 60 * 1000;
  return new Date(now.getTime() - timezoneOffsetMs).toISOString().slice(0, 10);
}

function parseMoney(value: string | number | null | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMoneyInput(value: string | number | null | undefined) {
  return Math.max(parseMoney(value), 0).toFixed(2);
}

function createEmptyLine(localId: number): EstimateLineDraft {
  return {
    localId,
    media_unit: null,
    description: "",
    start_date: "",
    end_date: "",
    quantity: "1.00",
    unit_rate: "",
    tax_rate: "18.00",
  };
}

export default function BillingPage() {
  const router = useRouter();
  const paymentPanelRef = useRef<HTMLElement | null>(null);
  const paymentAmountInputRef = useRef<HTMLInputElement | null>(null);
  const [user, setUser] = useState<StoredUser | null>(null);
  const [billingData, setBillingData] = useState<BillingPayload | null>(null);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [inventoryUnits, setInventoryUnits] = useState<InventoryUnit[]>([]);
  const [error, setError] = useState("");
  const [invoiceMessage, setInvoiceMessage] = useState("");
  const [invoiceError, setInvoiceError] = useState("");
  const [estimateMessage, setEstimateMessage] = useState("");
  const [estimateError, setEstimateError] = useState("");
  const [paymentMessage, setPaymentMessage] = useState("");
  const [paymentError, setPaymentError] = useState("");
  const [statementMessage, setStatementMessage] = useState("");
  const [statementError, setStatementError] = useState("");
  const [selectedCampaignId, setSelectedCampaignId] = useState<number>(0);
  const [invoicePreview, setInvoicePreview] = useState<CampaignInvoicePreview | null>(null);
  const [estimateActionId, setEstimateActionId] = useState<number | null>(null);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<number>(0);
  const [selectedStatementClientId, setSelectedStatementClientId] = useState<number>(0);
  const [clientStatement, setClientStatement] = useState<ClientStatement | null>(null);
  const [estimateForm, setEstimateForm] = useState<EstimateFormState>({
    client: 0,
    campaign: null,
    title: "",
    start_date: "",
    end_date: "",
    notes: "",
    lines: [createEmptyLine(1)],
  });
  const [paymentForm, setPaymentForm] = useState<InvoicePaymentCreateInput>({
    amount: "",
    payment_date: "",
    payment_mode: "bank_transfer",
    reference_number: "",
    notes: "",
  });
  const [nextEstimateLineId, setNextEstimateLineId] = useState(2);
  const [isLoading, setIsLoading] = useState(true);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isGeneratingInvoice, setIsGeneratingInvoice] = useState(false);
  const [isSavingEstimate, setIsSavingEstimate] = useState(false);
  const [isSavingPayment, setIsSavingPayment] = useState(false);
  const [isLoadingStatement, setIsLoadingStatement] = useState(false);
  const [invoicePdfActionId, setInvoicePdfActionId] = useState<number | null>(null);
  const [invoiceCancelActionId, setInvoiceCancelActionId] = useState<number | null>(null);

  const canManageBilling = WRITE_ROLES.has(user?.role ?? "");

  const loadBilling = useCallback(async () => {
    setIsLoading(true);
    setError("");

    try {
      const profile = await fetchCurrentUser();
      if (profile) {
        setUser(profile);
      }

      const [payload, clientDirectory, inventoryPayload] = await Promise.all([
        fetchBillingData(),
        WRITE_ROLES.has(profile?.role ?? "") ? fetchClients() : Promise.resolve([]),
        WRITE_ROLES.has(profile?.role ?? "") ? fetchInventoryData() : Promise.resolve({ sites: [], units: [] }),
      ]);

      setBillingData(payload);
      setClients(clientDirectory);
      setInventoryUnits(inventoryPayload.units);
      setSelectedCampaignId((current) => current || payload.campaigns[0]?.id || 0);
      setSelectedInvoiceId((current) => current || payload.invoices[0]?.id || 0);
      setSelectedStatementClientId((current) => current || clientDirectory[0]?.id || 0);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load billing data.";
      setError(message);
      if (message.includes("sign in again")) {
        router.replace("/login");
      }
    } finally {
      setIsLoading(false);
    }
  }, [router]);

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

    void loadBilling();
  }, [loadBilling, router]);

  const campaignMap = useMemo(() => {
    const map = new Map<number, Campaign>();
    for (const campaign of billingData?.campaigns ?? []) {
      map.set(campaign.id, campaign);
    }
    return map;
  }, [billingData]);

  const approvedEstimateCampaignIds = useMemo(() => {
    return new Set(
      (billingData?.estimates ?? [])
        .filter((estimate) => estimate.status === "approved" && estimate.campaign)
        .map((estimate) => estimate.campaign as number),
    );
  }, [billingData]);

  const invoiceCampaigns = useMemo(() => {
    const today = getTodayLocalIsoDate();
    return [...(billingData?.campaigns ?? [])]
      .filter((campaign) => {
        if (approvedEstimateCampaignIds.has(campaign.id)) {
          return true;
        }

        const hasStarted = Boolean(campaign.start_date) && campaign.start_date <= today;
        const isInvoiceLifecycleStatus = ["active", "paused", "completed"].includes(campaign.status);
        return hasStarted && isInvoiceLifecycleStatus;
      })
      .sort((left, right) => {
        const leftApproved = approvedEstimateCampaignIds.has(left.id) ? 1 : 0;
        const rightApproved = approvedEstimateCampaignIds.has(right.id) ? 1 : 0;

        if (leftApproved !== rightApproved) {
          return rightApproved - leftApproved;
        }

        return left.start_date.localeCompare(right.start_date);
      });
  }, [approvedEstimateCampaignIds, billingData]);

  const campaignsForSelectedClient = useMemo(() => {
    if (!estimateForm.client) {
      return billingData?.campaigns ?? [];
    }
    return (billingData?.campaigns ?? []).filter((campaign) => campaign.client === estimateForm.client);
  }, [billingData, estimateForm.client]);

  const inventoryUnitMap = useMemo(() => {
    const map = new Map<number, InventoryUnit>();
    for (const unit of inventoryUnits) {
      map.set(unit.id, unit);
    }
    return map;
  }, [inventoryUnits]);

  useEffect(() => {
    if (!canManageBilling || clients.length === 0) {
      return;
    }

    setEstimateForm((current) => {
      const nextClient = current.client || clients[0]?.id || 0;
      const matchingCampaign =
        (current.campaign ? campaignMap.get(current.campaign) : null) ??
        (billingData?.campaigns ?? []).find((campaign) => campaign.client === nextClient) ??
        null;

      if (!matchingCampaign && current.client === nextClient) {
        return {
          ...current,
          client: nextClient,
        };
      }

      return {
        ...current,
        client: nextClient,
        campaign: matchingCampaign?.id ?? current.campaign,
        title: current.title || (matchingCampaign ? `${matchingCampaign.name} Campaign Estimate` : ""),
        start_date: current.start_date || matchingCampaign?.start_date || "",
        end_date: current.end_date || matchingCampaign?.end_date || "",
        lines: current.lines.map((line) => ({
          ...line,
          start_date: line.start_date || matchingCampaign?.start_date || "",
          end_date: line.end_date || matchingCampaign?.end_date || "",
        })),
      };
    });
  }, [billingData, campaignMap, canManageBilling, clients]);

  useEffect(() => {
    if (selectedCampaignId && invoiceCampaigns.some((campaign) => campaign.id === selectedCampaignId)) {
      return;
    }
    setSelectedCampaignId(invoiceCampaigns[0]?.id || 0);
  }, [invoiceCampaigns, selectedCampaignId]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  function getClientLabel(clientId: number) {
    const client = clients.find((entry) => entry.id === clientId);
    return client?.organization_name || client?.email || `Client #${clientId}`;
  }

  function getMediaUnitLabel(unitId: number | null) {
    if (!unitId) {
      return "Select site / media unit";
    }
    const unit = inventoryUnitMap.get(unitId);
    if (!unit) {
      return `Media unit #${unitId}`;
    }
    return `${unit.unit_code} • Site ${unit.site}`;
  }

  function updateEstimateForm<K extends keyof EstimateFormState>(field: K, value: EstimateFormState[K]) {
    setEstimateError("");
    setEstimateMessage("");

    if (field === "client") {
      const nextClientId = Number(value);
      const nextCampaign = (billingData?.campaigns ?? []).find((campaign) => campaign.client === nextClientId) ?? null;
      setEstimateForm((current) => ({
        ...current,
        client: nextClientId,
        campaign: nextCampaign?.id ?? null,
        title: nextCampaign ? `${nextCampaign.name} Campaign Estimate` : current.title,
        start_date: nextCampaign?.start_date ?? current.start_date,
        end_date: nextCampaign?.end_date ?? current.end_date,
        lines: current.lines.map((line) => ({
          ...line,
          start_date: line.start_date || nextCampaign?.start_date || "",
          end_date: line.end_date || nextCampaign?.end_date || "",
        })),
      }));
      return;
    }

    if (field === "campaign") {
      const nextCampaignId = value ? Number(value) : null;
      const nextCampaign = nextCampaignId ? campaignMap.get(nextCampaignId) ?? null : null;
      setEstimateForm((current) => ({
        ...current,
        campaign: nextCampaignId,
        client: nextCampaign?.client ?? current.client,
        title: nextCampaign ? `${nextCampaign.name} Campaign Estimate` : current.title,
        start_date: nextCampaign?.start_date ?? current.start_date,
        end_date: nextCampaign?.end_date ?? current.end_date,
        lines: current.lines.map((line) => ({
          ...line,
          start_date: line.start_date || nextCampaign?.start_date || "",
          end_date: line.end_date || nextCampaign?.end_date || "",
        })),
      }));
      return;
    }

    setEstimateForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateEstimateLine(localId: number, field: keyof EstimateLineDraft, value: string | number | null) {
    setEstimateError("");
    setEstimateMessage("");

    setEstimateForm((current) => ({
      ...current,
      lines: current.lines.map((line) => {
        if (line.localId !== localId) {
          return line;
        }

        if (field === "media_unit") {
          const unitId = value ? Number(value) : null;
          const unit = unitId ? inventoryUnitMap.get(unitId) : null;
          return {
            ...line,
            media_unit: unitId,
            description: unit ? `Outdoor media display - ${unit.unit_code}` : line.description,
            unit_rate: unit ? unit.monthly_rate : line.unit_rate,
            start_date: line.start_date || estimateForm.start_date,
            end_date: line.end_date || estimateForm.end_date,
          };
        }

        return {
          ...line,
          [field]: String(value),
        };
      }),
    }));
  }

  function addEstimateLine() {
    setEstimateForm((current) => ({
      ...current,
      lines: [
        ...current.lines,
        {
          ...createEmptyLine(nextEstimateLineId),
          start_date: current.start_date,
          end_date: current.end_date,
        },
      ],
    }));
    setNextEstimateLineId((current) => current + 1);
  }

  function removeEstimateLine(localId: number) {
    setEstimateForm((current) => ({
      ...current,
      lines: current.lines.length > 1 ? current.lines.filter((line) => line.localId !== localId) : current.lines,
    }));
  }

  async function submitEstimateFlow(mode: "draft" | "share") {
    if (isSavingEstimate) {
      return;
    }

    if (!estimateForm.client || !estimateForm.title || !estimateForm.start_date || !estimateForm.end_date) {
      setEstimateError("Select client, campaign details, and estimate dates before saving.");
      return;
    }

    const incompleteLine = estimateForm.lines.find(
      (line) => !line.description || !line.start_date || !line.end_date || !line.quantity || !line.unit_rate || !line.tax_rate,
    );
    if (incompleteLine) {
      setEstimateError("Each proposed media line needs description, dates, rate, quantity, and tax.");
      return;
    }

    setEstimateError("");
    setEstimateMessage("");
    setIsSavingEstimate(true);

    try {
      const createdEstimate = await createCampaignEstimate({
        client: estimateForm.client,
        campaign: estimateForm.campaign,
        title: estimateForm.title,
        start_date: estimateForm.start_date,
        end_date: estimateForm.end_date,
        notes: estimateForm.notes,
      });

      for (const line of estimateForm.lines) {
        await createCampaignEstimateLine({
          estimate: createdEstimate.id,
          media_unit: line.media_unit,
          description: line.description,
          start_date: line.start_date,
          end_date: line.end_date,
          quantity: Number(line.quantity).toFixed(2),
          unit_rate: Number(line.unit_rate).toFixed(2),
          tax_rate: Number(line.tax_rate).toFixed(2),
        });
      }

      if (mode === "share") {
        await shareCampaignEstimate(createdEstimate.id);
      }

      setEstimateMessage(
        mode === "share"
          ? "Campaign Estimate saved and shared for client approval."
          : "Campaign Estimate saved as a draft.",
      );
      setEstimateForm({
        client: estimateForm.client,
        campaign: estimateForm.campaign,
        title: "",
        start_date: estimateForm.start_date,
        end_date: estimateForm.end_date,
        notes: "",
        lines: [createEmptyLine(nextEstimateLineId)],
      });
      setNextEstimateLineId((current) => current + 1);
      await loadBilling();
    } catch (saveError) {
      setEstimateError(getInvoiceActionError(saveError));
    } finally {
      setIsSavingEstimate(false);
    }
  }

  async function handleEstimateLifecycleAction(estimate: CampaignEstimate) {
    if (estimateActionId) {
      return;
    }

    setEstimateError("");
    setEstimateMessage("");
    setEstimateActionId(estimate.id);

    try {
      await shareCampaignEstimate(estimate.id);
      setEstimateMessage(
        estimate.public_path
          ? "Campaign Estimate link refreshed and sent for client approval."
          : "Campaign Estimate sent for client approval.",
      );
      await loadBilling();
    } catch (actionError) {
      setEstimateError(getInvoiceActionError(actionError));
    } finally {
      setEstimateActionId(null);
    }
  }

  async function handleCopyEstimateLink(publicPath: string | null | undefined) {
    if (!publicPath) {
      setEstimateError("No public approval link is available for this estimate yet.");
      return;
    }

    try {
      await navigator.clipboard.writeText(`${window.location.origin}${publicPath}`);
      setEstimateError("");
      setEstimateMessage("Estimate approval link copied.");
    } catch {
      setEstimateError("Unable to copy the estimate approval link automatically.");
    }
  }

  async function handlePreviewInvoice() {
    if (!selectedCampaignId || isPreviewLoading) {
      return;
    }

    setInvoiceError("");
    setInvoiceMessage("");
    setInvoicePreview(null);
    setIsPreviewLoading(true);

    try {
      const preview = await fetchCampaignInvoicePreview(selectedCampaignId);
      setInvoicePreview(preview);
      setInvoiceMessage(preview.message || "Invoice preview is ready for review.");
    } catch (previewError) {
      setInvoiceError(getInvoiceActionError(previewError));
    } finally {
      setIsPreviewLoading(false);
    }
  }

  async function handleGenerateInvoice() {
    if (!selectedCampaignId || isGeneratingInvoice) {
      return;
    }

    setInvoiceError("");
    setInvoiceMessage("");
    setIsGeneratingInvoice(true);

    try {
      const invoice = await generateCampaignInvoice(selectedCampaignId);
      setInvoiceMessage(`Invoice created${invoice.invoice_number ? `: ${invoice.invoice_number}` : " as a draft"}.`);
      const refreshedPreview = await fetchCampaignInvoicePreview(selectedCampaignId);
      setInvoicePreview(refreshedPreview);
      await loadBilling();
    } catch (generateError) {
      setInvoiceError(getInvoiceActionError(generateError));
    } finally {
      setIsGeneratingInvoice(false);
    }
  }

  const quickStats = useMemo(() => {
    if (!billingData) {
      return [];
    }

    return [
      { label: "Total estimated", value: formatCurrency(billingData.summary.total_estimated) },
      { label: "Total approved estimates", value: formatCurrency(billingData.summary.total_approved_estimates) },
      { label: "Total invoiced", value: formatCurrency(billingData.summary.total_invoiced) },
      { label: "Total collected", value: formatCurrency(billingData.summary.total_collected) },
      { label: "Outstanding balance", value: formatCurrency(billingData.summary.outstanding_balance) },
      { label: "Overdue amount", value: formatCurrency(billingData.summary.overdue_amount) },
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

  const selectedInvoice = useMemo(() => {
    return (billingData?.invoices ?? []).find((invoice) => invoice.id === selectedInvoiceId) ?? null;
  }, [billingData, selectedInvoiceId]);

  function updatePaymentForm<K extends keyof InvoicePaymentCreateInput>(field: K, value: InvoicePaymentCreateInput[K]) {
    setPaymentError("");
    setPaymentMessage("");
    setPaymentForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function isInvoicePayable(invoice: Invoice) {
    return canManageBilling && !["draft", "cancelled", "paid"].includes(invoice.payment_status) && parseMoney(invoice.balance_due) > 0;
  }

  function handleSelectInvoiceForPayment(invoice: Invoice) {
    setSelectedInvoiceId(invoice.id);
    setPaymentMessage("");
    if (!canManageBilling) {
      setPaymentError("You do not have permission to record invoice payments.");
      return;
    }

    if (!isInvoicePayable(invoice)) {
      setPaymentError("This invoice is not payable. Issue it first, or select an invoice with a balance due.");
      return;
    }

    setPaymentError("");
    setPaymentForm((current) => ({
      ...current,
      amount: formatMoneyInput(invoice.balance_due),
      payment_date: current.payment_date || getTodayLocalIsoDate(),
    }));

    window.requestAnimationFrame(() => {
      paymentPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      paymentAmountInputRef.current?.focus({ preventScroll: true });
    });
  }

  async function handleRecordPayment() {
    if (!selectedInvoiceId || isSavingPayment) {
      return;
    }

    if (!selectedInvoice) {
      setPaymentError("Select an invoice before recording payment.");
      return;
    }

    if (!isInvoicePayable(selectedInvoice)) {
      setPaymentError("This invoice is not payable. Issue it first, or select an invoice with a balance due.");
      return;
    }

    if (!paymentForm.amount || !paymentForm.payment_date) {
      setPaymentError("Enter the payment amount and payment date before recording payment.");
      return;
    }

    const paymentAmount = parseMoney(paymentForm.amount);
    const balanceDue = parseMoney(selectedInvoice.balance_due);
    if (paymentAmount <= 0) {
      setPaymentError("Payment amount must be greater than zero.");
      return;
    }
    if (paymentAmount > balanceDue) {
      setPaymentError(`Payment cannot exceed the current balance due of ${formatCurrency(selectedInvoice.balance_due)}.`);
      return;
    }

    setPaymentError("");
    setPaymentMessage("");
    setIsSavingPayment(true);

    try {
      await createInvoicePayment(selectedInvoiceId, {
        ...paymentForm,
        amount: paymentAmount.toFixed(2),
      });
      setPaymentMessage("Payment recorded successfully.");
      setPaymentForm({
        amount: "",
        payment_date: "",
        payment_mode: "bank_transfer",
        reference_number: "",
        notes: "",
      });
      await loadBilling();
      if (selectedStatementClientId) {
        void handleLoadClientStatement(selectedStatementClientId);
      }
    } catch (saveError) {
      setPaymentError(getInvoiceActionError(saveError));
    } finally {
      setIsSavingPayment(false);
    }
  }

  async function handleCancelInvoice(invoice: Invoice) {
    if (invoiceCancelActionId || !canManageBilling) {
      return;
    }
    const reason = window.prompt("Enter the cancellation/void reason for this invoice:");
    if (!reason?.trim()) {
      setInvoiceError("Cancellation reason is required.");
      return;
    }

    setInvoiceError("");
    setInvoiceMessage("");
    setInvoiceCancelActionId(invoice.id);
    try {
      await cancelInvoice(invoice.id, reason.trim());
      setInvoiceMessage("Invoice cancelled/voided successfully.");
      await loadBilling();
      if (selectedStatementClientId) {
        void handleLoadClientStatement(selectedStatementClientId);
      }
    } catch (cancelError) {
      setInvoiceError(getInvoiceActionError(cancelError));
    } finally {
      setInvoiceCancelActionId(null);
    }
  }

  async function handleLoadClientStatement(clientId = selectedStatementClientId) {
    if (!clientId || isLoadingStatement) {
      return;
    }
    setStatementError("");
    setStatementMessage("");
    setIsLoadingStatement(true);
    try {
      const statement = await fetchClientStatement(clientId);
      setClientStatement(statement);
      setStatementMessage(`Statement loaded for ${statement.client_name}.`);
    } catch (statementLoadError) {
      setClientStatement(null);
      setStatementError(getInvoiceActionError(statementLoadError));
    } finally {
      setIsLoadingStatement(false);
    }
  }

  async function handleDownloadInvoice(invoice: Invoice) {
    setInvoiceError("");
    setInvoiceMessage("");
    setInvoicePdfActionId(invoice.id);

    try {
      const { blob, filename } = await downloadInvoicePdf(invoice.id);
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.style.display = "none";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 60_000);

      setInvoiceMessage(`Invoice PDF ready for ${invoice.invoice_number ?? `draft #${invoice.id}`}.`);
      await loadBilling();
    } catch (downloadError) {
      setInvoiceError(getInvoiceActionError(downloadError));
    } finally {
      setInvoicePdfActionId(null);
    }
  }

  return (
    <AppShell
      active="billing"
      roleLabel={user?.role ?? "Team member"}
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
              Campaign Estimate is shared before booking. Invoice is generated after campaign starts.
            </p>
          </div>
          <span>Lifecycle</span>
        </div>
        <p className="section-copy">
          Create a Campaign Estimate before booking inventory, send it for client approval, then generate Invoice from confirmed bookings only when the campaign start date is today or in the past.
        </p>
      </section>

      <section className="billing-layout">
        <article className="module-card module-card-wide">
          <div className="module-head">
            <div>
              <h2>Campaign Estimate</h2>
              <p className="section-copy">Select client, proposed campaign, sites, media units, dates, rates, and taxes before sharing for approval.</p>
            </div>
            <span>Pre-booking</span>
          </div>
          {estimateError ? <p className="error">{estimateError}</p> : null}
          {estimateMessage ? <p className="success">{estimateMessage}</p> : null}
          {canManageBilling ? (
            <div className="campaign-creation-stack">
              <div className="campaign-form-grid">
                <div className="field">
                  <label htmlFor="estimate-client">Client</label>
                  <select
                    id="estimate-client"
                    value={estimateForm.client || ""}
                    onChange={(event) => updateEstimateForm("client", Number(event.target.value))}
                  >
                    <option value="" disabled>
                      Select client
                    </option>
                    {clients.map((client) => (
                      <option key={client.id} value={client.id}>
                        {client.organization_name || client.email}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="estimate-campaign">Proposed campaign</label>
                  <select
                    id="estimate-campaign"
                    value={estimateForm.campaign ?? ""}
                    onChange={(event) => updateEstimateForm("campaign", event.target.value ? Number(event.target.value) : null)}
                  >
                    <option value="">Select campaign</option>
                    {campaignsForSelectedClient.map((campaign) => (
                      <option key={campaign.id} value={campaign.id}>
                        {campaign.name} ({campaign.code})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field field-span-2">
                  <label htmlFor="estimate-title">Estimate title</label>
                  <input
                    id="estimate-title"
                    value={estimateForm.title}
                    onChange={(event) => updateEstimateForm("title", event.target.value)}
                    placeholder="Airport Corridor Campaign Estimate"
                  />
                </div>
                <div className="field">
                  <label htmlFor="estimate-start-date">Start date</label>
                  <input
                    id="estimate-start-date"
                    type="date"
                    value={estimateForm.start_date}
                    onChange={(event) => updateEstimateForm("start_date", event.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="estimate-end-date">End date</label>
                  <input
                    id="estimate-end-date"
                    type="date"
                    value={estimateForm.end_date}
                    onChange={(event) => updateEstimateForm("end_date", event.target.value)}
                  />
                </div>
                <div className="field field-full">
                  <label htmlFor="estimate-notes">Notes</label>
                  <textarea
                    id="estimate-notes"
                    rows={3}
                    value={estimateForm.notes}
                    onChange={(event) => updateEstimateForm("notes", event.target.value)}
                    placeholder="Share placement assumptions, tax notes, and approval context."
                  />
                </div>
              </div>

              <div className="module-head">
                <h2>Proposed media lines</h2>
                <button className="ghost" type="button" onClick={addEstimateLine}>
                  Add proposed site / unit
                </button>
              </div>

              {estimateForm.lines.map((line, index) => (
                <div className="campaign-form-grid" key={line.localId}>
                  <div className="field field-span-2">
                    <label htmlFor={`estimate-line-unit-${line.localId}`}>Site / media unit {index + 1}</label>
                    <select
                      id={`estimate-line-unit-${line.localId}`}
                      value={line.media_unit ?? ""}
                      onChange={(event) => updateEstimateLine(line.localId, "media_unit", event.target.value ? Number(event.target.value) : null)}
                    >
                      <option value="">{getMediaUnitLabel(null)}</option>
                      {inventoryUnits.map((unit) => (
                        <option key={unit.id} value={unit.id}>
                          {getMediaUnitLabel(unit.id)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field field-full">
                    <label htmlFor={`estimate-line-description-${line.localId}`}>Description</label>
                    <input
                      id={`estimate-line-description-${line.localId}`}
                      value={line.description}
                      onChange={(event) => updateEstimateLine(line.localId, "description", event.target.value)}
                      placeholder="Outdoor media display - Site / Unit"
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`estimate-line-start-${line.localId}`}>Line start</label>
                    <input
                      id={`estimate-line-start-${line.localId}`}
                      type="date"
                      value={line.start_date}
                      onChange={(event) => updateEstimateLine(line.localId, "start_date", event.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`estimate-line-end-${line.localId}`}>Line end</label>
                    <input
                      id={`estimate-line-end-${line.localId}`}
                      type="date"
                      value={line.end_date}
                      onChange={(event) => updateEstimateLine(line.localId, "end_date", event.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`estimate-line-quantity-${line.localId}`}>Quantity</label>
                    <input
                      id={`estimate-line-quantity-${line.localId}`}
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.quantity}
                      onChange={(event) => updateEstimateLine(line.localId, "quantity", event.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`estimate-line-rate-${line.localId}`}>Rate</label>
                    <input
                      id={`estimate-line-rate-${line.localId}`}
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.unit_rate}
                      onChange={(event) => updateEstimateLine(line.localId, "unit_rate", event.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`estimate-line-tax-${line.localId}`}>Tax %</label>
                    <input
                      id={`estimate-line-tax-${line.localId}`}
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.tax_rate}
                      onChange={(event) => updateEstimateLine(line.localId, "tax_rate", event.target.value)}
                    />
                  </div>
                  <div className="field form-actions">
                    <button
                      className="ghost"
                      type="button"
                      disabled={estimateForm.lines.length === 1}
                      onClick={() => removeEstimateLine(line.localId)}
                    >
                      Remove line
                    </button>
                  </div>
                </div>
              ))}

              <div className="form-actions">
                <button className="submit" type="button" disabled={isSavingEstimate} onClick={() => void submitEstimateFlow("draft")}>
                  {isSavingEstimate ? "Saving..." : "Create Campaign Estimate"}
                </button>
                <button className="ghost" type="button" disabled={isSavingEstimate} onClick={() => void submitEstimateFlow("share")}>
                  {isSavingEstimate ? "Saving..." : "Save & Share Estimate"}
                </button>
              </div>
            </div>
          ) : (
            <p className="empty-state">You currently have read-only access to Campaign Estimate workflows.</p>
          )}
        </article>

        <article className="module-card">
          <div className="module-head">
            <div>
              <h2>Invoice</h2>
              <p className="section-copy">Select a running or completed campaign for invoice review. Approved estimates are prioritised, and invoice generation still depends on confirmed bookings and the campaign start date.</p>
            </div>
            <span>Post-start</span>
          </div>
          {invoiceError ? <p className="error">{invoiceError}</p> : null}
          {invoiceMessage ? <p className={invoiceMessage.includes("ready") || invoiceMessage.includes("created") ? "success" : "info"}>{invoiceMessage}</p> : null}
          <div className="campaign-share-actions">
            <select
              className="table-select billing-campaign-select"
              value={selectedCampaignId || ""}
              onChange={(event) => {
                setSelectedCampaignId(Number(event.target.value));
                setInvoicePreview(null);
                setInvoiceError("");
                setInvoiceMessage("");
              }}
              aria-label="Select campaign for invoice generation"
            >
              <option value="" disabled>
                Select campaign for invoice
              </option>
              {invoiceCampaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name} ({campaign.code}){approvedEstimateCampaignIds.has(campaign.id) ? " • estimate approved" : ""}
                </option>
              ))}
            </select>
            <button className="ghost" type="button" disabled={!selectedCampaignId || isPreviewLoading} onClick={() => void handlePreviewInvoice()}>
              {isPreviewLoading ? "Preparing preview..." : "Preview Invoice"}
            </button>
            <button
              className="submit"
              type="button"
              disabled={!invoicePreview?.can_generate || isGeneratingInvoice}
              onClick={() => void handleGenerateInvoice()}
            >
              {isGeneratingInvoice ? "Generating invoice..." : "Generate Invoice"}
            </button>
          </div>
          {invoiceCampaigns.length === 0 ? (
            <p className="empty-state">No running campaigns are ready for invoice review yet. Campaigns appear here after the start date, and preview will confirm confirmed bookings before Invoice can be generated.</p>
          ) : null}
          {invoicePreview ? (
            <div className="campaign-detail-panel">
              <div className="campaign-detail-head">
                <div>
                  <p className="site-code">Invoice preview</p>
                  <h3>{invoicePreview.campaign_name}</h3>
                  <p className="section-copy">
                    {invoicePreview.confirmed_booking_count} confirmed booking(s) for {invoicePreview.client_name}
                  </p>
                </div>
                <div className="table-primary">
                  <strong>{formatCurrency(invoicePreview.total_amount)}</strong>
                  <span>Campaign total</span>
                </div>
              </div>
              <div className="inventory-table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Site / unit</th>
                      <th>Dates</th>
                      <th>Media</th>
                      <th>Flex / printing</th>
                      <th>Installation</th>
                      <th>Other</th>
                      <th>Line total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoicePreview.lines.map((line) => (
                      <tr key={line.booking_id}>
                        <td>
                          <div className="table-primary">
                            <strong>{line.site_name}</strong>
                            <span>{line.media_unit_label}</span>
                          </div>
                        </td>
                        <td>{formatDate(line.start_date)} - {formatDate(line.end_date)}</td>
                        <td>{formatCurrency(line.media_cost)}</td>
                        <td>{formatCurrency(line.flex_cost)}</td>
                        <td>{formatCurrency(line.installation_cost)}</td>
                        <td>{formatCurrency(line.other_cost)}</td>
                        <td>{formatCurrency(line.line_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {invoicePreview.lines.length === 0 ? (
                <p className="empty-state">No confirmed bookings found for this campaign. Confirm bookings before generating an Invoice.</p>
              ) : null}
            </div>
          ) : null}
        </article>
      </section>

      <section className="summary-row" aria-label="Billing stats">
        {quickStats.map((item) => (
          <article className="summary-card" key={item.label}>
            <p className="stat-label">{item.label}</p>
            <p className="summary-value">{isLoading ? "..." : item.value}</p>
          </article>
        ))}
      </section>

      {canManageBilling ? (
        <section className="module-card module-card-wide">
          <div className="module-head">
            <div>
              <h2>Client statement</h2>
              <p className="section-copy">Finance follow-up view for billed, collected, outstanding, unpaid invoices, and payment history.</p>
            </div>
            <span>Statement</span>
          </div>
          {statementError ? <p className="error">{statementError}</p> : null}
          {statementMessage ? <p className="success">{statementMessage}</p> : null}
          <div className="campaign-share-actions">
            <select
              className="table-select billing-campaign-select"
              value={selectedStatementClientId || ""}
              onChange={(event) => {
                const clientId = Number(event.target.value);
                setSelectedStatementClientId(clientId);
                setClientStatement(null);
                setStatementMessage("");
                setStatementError("");
              }}
            >
              <option value="" disabled>
                Select client
              </option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.organization_name || client.email}
                </option>
              ))}
            </select>
            <button className="ghost" type="button" disabled={!selectedStatementClientId || isLoadingStatement} onClick={() => void handleLoadClientStatement()}>
              {isLoadingStatement ? "Loading statement..." : "Load statement"}
            </button>
          </div>
          {clientStatement ? (
            <>
              <div className="module-stats">
                <div className="module-stat">
                  <p className="stat-label">Total billed</p>
                  <p className="field-summary-value">{formatCurrency(clientStatement.total_billed)}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Total paid</p>
                  <p className="field-summary-value">{formatCurrency(clientStatement.total_paid)}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Outstanding</p>
                  <p className="field-summary-value">{formatCurrency(clientStatement.outstanding_balance)}</p>
                </div>
              </div>
              <div className="inventory-table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Unpaid invoice</th>
                      <th>Due date</th>
                      <th>Status</th>
                      <th>Total</th>
                      <th>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clientStatement.unpaid_invoices.map((invoice) => (
                      <tr key={invoice.id}>
                        <td>{invoice.invoice_number ?? `Draft #${invoice.id}`}</td>
                        <td>{invoice.due_date ? formatDate(invoice.due_date) : "Not set"}</td>
                        <td><span className={`status-pill status-${invoice.payment_status}`}>{invoice.payment_status.replaceAll("_", " ")}</span></td>
                        <td>{formatCurrency(invoice.invoice_total)}</td>
                        <td>{formatCurrency(invoice.balance_due)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {clientStatement.unpaid_invoices.length === 0 ? <p className="empty-state">No unpaid invoices for this client.</p> : null}
              <div className="module-head">
                <h2>Statement payment history</h2>
                <span>{clientStatement.payments.length} payment(s)</span>
              </div>
              <div className="asset-list">
                {clientStatement.payments.slice(0, 8).map((payment) => (
                  <article className="asset-card" key={payment.id}>
                    <div className="asset-head">
                      <div>
                        <p className="site-code">{formatDate(payment.payment_date)}</p>
                        <h3>{formatCurrency(payment.amount)}</h3>
                      </div>
                      <span className="status-pill status-paid">{payment.method.replaceAll("_", " ")}</span>
                    </div>
                    <p className="site-copy">{payment.reference_number || "No reference recorded."}</p>
                    <p className="site-copy">{payment.recorded_by_name ? `Recorded by ${payment.recorded_by_name}` : "Recorded by system"}</p>
                  </article>
                ))}
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Campaign Estimate status</h2>
            <span>Pre-booking</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Draft</p>
              <p className="stat-value">
                {isLoading ? "..." : (billingData?.estimates ?? []).filter((estimate) => estimate.status === "draft").length}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Sent</p>
              <p className="stat-value">
                {isLoading ? "..." : (billingData?.estimates ?? []).filter((estimate) => estimate.status === "sent").length}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Approved</p>
              <p className="stat-value">{isLoading ? "..." : (billingData?.estimates ?? []).filter((estimate) => estimate.status === "approved").length}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Rejected</p>
              <p className="stat-value">{isLoading ? "..." : (billingData?.estimates ?? []).filter((estimate) => estimate.status === "rejected").length}</p>
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
              <p className="stat-label">Partial</p>
              <p className="stat-value">{isLoading ? "..." : billingData?.summary.partially_paid_invoices ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Paid</p>
              <p className="stat-value">{isLoading ? "..." : billingData?.summary.paid_invoices ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Overdue</p>
              <p className="stat-value">{isLoading ? "..." : billingData?.summary.overdue_invoices ?? 0}</p>
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
                <th>Actions</th>
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
                  <td>{estimate.client_name || getClientLabel(estimate.client)}</td>
                  <td>{formatDate(estimate.start_date)} - {formatDate(estimate.end_date)}</td>
                  <td>
                    <span className={`status-pill status-${estimate.status}`}>{estimate.status}</span>
                  </td>
                  <td>{formatCurrency(estimate.total_amount)}</td>
                  <td>{estimate.lines.length} proposed item(s)</td>
                  <td>
                    <div className="campaign-share-actions">
                      {estimate.status === "draft" || estimate.status === "rejected" ? (
                        <button
                          className="ghost table-action"
                          type="button"
                          disabled={estimateActionId === estimate.id}
                          onClick={() => void handleEstimateLifecycleAction(estimate)}
                        >
                          {estimate.status === "rejected" ? "Resend" : "Send"}
                        </button>
                      ) : null}
                      {estimate.public_path ? (
                        <button
                          className="ghost table-action"
                          type="button"
                          onClick={() => void handleCopyEstimateLink(estimate.public_path)}
                        >
                          Copy link
                        </button>
                      ) : null}
                      {estimate.public_path ? (
                        <a className="asset-link" href={estimate.public_path} target="_blank" rel="noreferrer">
                          Open link
                        </a>
                      ) : null}
                    </div>
                  </td>
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
                  <th>Payment status</th>
                  <th>Invoice total</th>
                  <th>Amount paid</th>
                  <th>Balance due</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {(billingData?.invoices ?? []).map((invoice) => {
                  const campaign = campaignMap.get(invoice.campaign);

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
                        <span className={`status-pill status-${invoice.payment_status}`}>{invoice.payment_status.replaceAll("_", " ")}</span>
                      </td>
                      <td>{formatCurrency(invoice.invoice_total)}</td>
                      <td>{formatCurrency(invoice.amount_paid)}</td>
                      <td>{formatCurrency(invoice.balance_due)}</td>
                      <td>
                        <div className="form-actions">
                          <button
                            className="ghost table-action"
                            type="button"
                            disabled={!isInvoicePayable(invoice)}
                            title={
                              canManageBilling
                                ? isInvoicePayable(invoice)
                                  ? "Record a partial or full payment for this invoice."
                                  : "Issue the invoice first, or select an invoice with a balance due."
                                : "You do not have permission to record payments."
                            }
                            onClick={() => handleSelectInvoiceForPayment(invoice)}
                          >
                            Record Payment
                          </button>
                          <button
                            className="ghost table-action"
                            type="button"
                            disabled={invoicePdfActionId === invoice.id}
                            onClick={() => void handleDownloadInvoice(invoice)}
                          >
                            {invoicePdfActionId === invoice.id
                              ? "Preparing PDF..."
                              : invoice.status === "draft"
                                ? "Issue & Download PDF"
                                : "Download PDF"}
                          </button>
                          <button
                            className="ghost table-action"
                            type="button"
                            disabled={
                              !canManageBilling ||
                              invoiceCancelActionId === invoice.id ||
                              invoice.status === "cancelled" ||
                              invoice.payment_status === "paid" ||
                              parseMoney(invoice.amount_paid) > 0
                            }
                            title="Void/cancel invoices before payments are recorded."
                            onClick={() => void handleCancelInvoice(invoice)}
                          >
                            {invoiceCancelActionId === invoice.id ? "Voiding..." : "Void"}
                          </button>
                        </div>
                      </td>
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

        <article className="module-card" ref={paymentPanelRef}>
          <div className="module-head">
            <h2>Record payment</h2>
            <span>Collections</span>
          </div>
          {paymentError ? <p className="error">{paymentError}</p> : null}
          {paymentMessage ? <p className="success">{paymentMessage}</p> : null}
          {selectedInvoice ? (
            <>
              <div className="module-stats">
                <div className="module-stat">
                  <p className="stat-label">Selected invoice</p>
                  <p className="field-summary-value">{selectedInvoice.invoice_number ?? `Draft #${selectedInvoice.id}`}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Invoice total</p>
                  <p className="field-summary-value">{formatCurrency(selectedInvoice.invoice_total)}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Amount paid</p>
                  <p className="field-summary-value">{formatCurrency(selectedInvoice.amount_paid)}</p>
                </div>
                <div className="module-stat">
                  <p className="stat-label">Balance due</p>
                  <p className="field-summary-value">{formatCurrency(selectedInvoice.balance_due)}</p>
                </div>
              </div>
              <div className="form-actions">
                <button
                  className="ghost"
                  type="button"
                  disabled={invoicePdfActionId === selectedInvoice.id}
                  onClick={() => void handleDownloadInvoice(selectedInvoice)}
                >
                  {invoicePdfActionId === selectedInvoice.id
                    ? "Preparing PDF..."
                    : selectedInvoice.status === "draft"
                      ? "Issue & Download Invoice PDF"
                      : "Download Invoice PDF"}
                </button>
              </div>
              <div className="campaign-form-grid">
                <div className="field">
                  <label htmlFor="payment-amount">Amount</label>
                  <input
                    id="payment-amount"
                    ref={paymentAmountInputRef}
                    type="number"
                    min="0"
                    max={selectedInvoice.balance_due}
                    step="0.01"
                    value={paymentForm.amount}
                    onChange={(event) => updatePaymentForm("amount", event.target.value)}
                  />
                  <p className="field-help">Maximum available balance: {formatCurrency(selectedInvoice.balance_due)}</p>
                </div>
                <div className="field">
                  <label htmlFor="payment-date">Payment date</label>
                  <input
                    id="payment-date"
                    type="date"
                    value={paymentForm.payment_date}
                    onChange={(event) => updatePaymentForm("payment_date", event.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="payment-mode">Payment mode</label>
                  <select
                    id="payment-mode"
                    value={paymentForm.payment_mode}
                    onChange={(event) => updatePaymentForm("payment_mode", event.target.value)}
                  >
                    {PAYMENT_MODE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="payment-reference">Reference number</label>
                  <input
                    id="payment-reference"
                    value={paymentForm.reference_number}
                    onChange={(event) => updatePaymentForm("reference_number", event.target.value)}
                  />
                </div>
                <div className="field field-full">
                  <label htmlFor="payment-notes">Notes</label>
                  <textarea
                    id="payment-notes"
                    rows={3}
                    value={paymentForm.notes}
                    onChange={(event) => updatePaymentForm("notes", event.target.value)}
                    placeholder="Add bank details, cheque remarks, or receipt notes."
                  />
                </div>
                <div className="form-actions field-full">
                  <button
                    className="submit"
                    type="button"
                    disabled={isSavingPayment || !isInvoicePayable(selectedInvoice)}
                    onClick={() => void handleRecordPayment()}
                  >
                    {isSavingPayment ? "Saving..." : "Record Payment"}
                  </button>
                </div>
              </div>
              <div className="module-head">
                <h2>Payment history</h2>
                <span>{selectedInvoice.payments.length} payment(s)</span>
              </div>
              <div className="inventory-table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Amount</th>
                      <th>Method</th>
                      <th>Reference</th>
                      <th>Recorded by</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedInvoice.payments.map((payment) => (
                      <tr key={payment.id}>
                        <td>{formatDate(payment.payment_date)}</td>
                        <td>{formatCurrency(payment.amount)}</td>
                        <td>{payment.method.replaceAll("_", " ")}</td>
                        <td>{payment.reference_number || "No reference"}</td>
                        <td>{payment.recorded_by_name || "System"}</td>
                        <td className="table-wrap">{payment.notes || "No notes"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selectedInvoice.payments.length === 0 ? (
                <p className="empty-state">No payments recorded for this invoice yet. Partial payments will appear here.</p>
              ) : null}
              <div className="module-head">
                <h2>Invoice audit trail</h2>
                <span>{selectedInvoice.events?.length ?? 0} event(s)</span>
              </div>
              <div className="asset-list">
                {(selectedInvoice.events ?? []).slice(0, 8).map((event) => (
                  <article className="asset-card" key={event.id}>
                    <div className="asset-head">
                      <div>
                        <p className="site-code">{event.event_type.replaceAll("_", " ")}</p>
                        <h3>{formatDateTime(event.created_at)}</h3>
                      </div>
                      <span className={`status-pill status-${event.to_status || selectedInvoice.status}`}>
                        {event.to_status || selectedInvoice.status}
                      </span>
                    </div>
                    <p className="site-copy">{event.message || "Invoice event recorded."}</p>
                    <p className="site-copy">{event.actor_name ? `By ${event.actor_name}` : "System event"}</p>
                  </article>
                ))}
                {!isLoading && (selectedInvoice.events?.length ?? 0) === 0 ? (
                  <p className="empty-state">No invoice audit events have been recorded yet.</p>
                ) : null}
              </div>
            </>
          ) : (
            <p className="empty-state">Select an invoice from the roster to record a payment.</p>
          )}

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
