"use client";

import { ChangeEvent, FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  fetchCompanyProfile,
  fetchOrganizationEmailSettings,
  sendOrganizationTestEmail,
  updateCompanyProfile,
  updateOrganizationEmailSettings,
  type CompanyProfile,
  type OrganizationEmailSettings,
} from "@/lib/setup";

type CompanyProfileForm = {
  company_name: string;
  legal_name: string;
  communication_email: string;
  phone: string;
  address: string;
  gstin: string;
  state_code: string;
  invoice_prefix: string;
  bank_details: string;
  authorised_signatory: string;
};

type EmailSettingsForm = {
  from_email: string;
  reply_to_email: string;
  smtp_host: string;
  smtp_port: string;
  smtp_username: string;
  smtp_password: string;
  use_tls: boolean;
  use_ssl: boolean;
};

type StoredUser = {
  email?: string;
  role?: string;
};

const emptyCompanyForm: CompanyProfileForm = {
  company_name: "",
  legal_name: "",
  communication_email: "",
  phone: "",
  address: "",
  gstin: "",
  state_code: "",
  invoice_prefix: "INV",
  bank_details: "",
  authorised_signatory: "",
};

const emptyEmailForm: EmailSettingsForm = {
  from_email: "",
  reply_to_email: "",
  smtp_host: "",
  smtp_port: "587",
  smtp_username: "",
  smtp_password: "",
  use_tls: true,
  use_ssl: false,
};

function readCompanyForm(profile: CompanyProfile): CompanyProfileForm {
  return {
    company_name: profile.company_name ?? "",
    legal_name: profile.legal_name ?? "",
    communication_email: profile.communication_email ?? "",
    phone: profile.phone ?? "",
    address: profile.address ?? "",
    gstin: profile.gstin ?? "",
    state_code: profile.state_code ?? "",
    invoice_prefix: profile.invoice_prefix ?? "INV",
    bank_details: profile.bank_details ?? "",
    authorised_signatory: profile.authorised_signatory ?? "",
  };
}

function readEmailForm(settings: OrganizationEmailSettings): EmailSettingsForm {
  return {
    from_email: settings.from_email ?? "",
    reply_to_email: settings.reply_to_email ?? "",
    smtp_host: settings.smtp_host ?? "",
    smtp_port: String(settings.smtp_port ?? 587),
    smtp_username: settings.smtp_username ?? "",
    smtp_password: "",
    use_tls: settings.use_tls ?? true,
    use_ssl: settings.use_ssl ?? false,
  };
}

function SetupStatusBadge({
  tone,
  children,
}: {
  tone: "success" | "pending" | "neutral";
  children: ReactNode;
}) {
  const tones = {
    success: "border-[#DDE8E3] bg-white text-[#064E3B]",
    pending: "border-[#DDE8E3] bg-white text-[#064E3B]",
    neutral: "border-[#DDE8E3] bg-white text-[#4B635A]",
  } as const;

  return (
    <span
      className={`inline-flex min-h-8 items-center rounded-md border px-3 text-[11px] font-semibold uppercase tracking-[0.18em] ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function SetupHeaderBadge({
  tone,
  children,
}: {
  tone: "neutral" | "pending";
  children: ReactNode;
}) {
  const tones = {
    neutral: "border-[#DDE8E3] bg-white text-[#4B635A]",
    pending: "border-[#DDE8E3] bg-white text-[#064E3B]",
  } as const;

  return (
    <span
      className={`inline-flex min-h-9 items-center rounded-md border px-3 text-sm font-semibold ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function SetupCard({
  title,
  subtitle,
  headerAction,
  children,
}: {
  title: string;
  subtitle: string;
  headerAction?: ReactNode;
  children: ReactNode;
}) {
  return (
    <article className="min-w-0 overflow-hidden rounded-lg border border-[#DDE8E3] bg-white p-5 shadow-[0_10px_26px_rgba(15,23,42,0.05)] md:p-6">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-[24px] font-semibold tracking-[-0.03em] text-[#0F172A]">{title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#4B635A]">{subtitle}</p>
        </div>
        {headerAction ? <div className="flex flex-wrap gap-2 sm:justify-end">{headerAction}</div> : null}
      </div>
      {children}
    </article>
  );
}

function FormGroup({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-[#DDE8E3] bg-[#FAFCFB] p-5">
      <div className="mb-5">
        <h3 className="text-lg font-semibold tracking-[-0.02em] text-[#0F172A]">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-[#4B635A]">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function SetupStep({
  step,
  title,
  description,
  state,
  isLast,
}: {
  step: number;
  title: string;
  description: string;
  state: "active" | "pending" | "complete";
  isLast?: boolean;
}) {
  const circleClass =
    state === "active"
      ? "border-[#064E3B] bg-[#064E3B] text-white"
      : state === "complete"
        ? "border-[#DDE8E3] bg-white text-[#064E3B]"
        : "border-[#DDE8E3] bg-white text-[#4B635A]";
  const lineClass = state === "complete" ? "bg-[#DDE8E3]" : "bg-[#DDE8E3]";

  return (
    <div className="relative flex min-w-0 gap-4">
      <div className="relative flex flex-col items-center">
        <div
          className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-md border text-sm font-semibold ${circleClass}`}
        >
          {step}
        </div>
        {isLast ? null : <div className={`mt-2 h-full min-h-[44px] w-px ${lineClass}`} />}
      </div>
      <div className="min-w-0 pt-1">
        <p className="text-sm font-semibold text-[#0F172A]">{title}</p>
        <p className="mt-1 text-sm leading-6 text-[#4B635A]">{description}</p>
      </div>
    </div>
  );
}

function WorkspaceStatusRow({
  label,
  value,
  status,
  tone,
  icon,
}: {
  label: string;
  value: string;
  status: string;
  tone: "success" | "pending";
  icon: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-lg border border-[#DDE8E3] bg-white px-4 py-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-[#DDE8E3] bg-white text-sm font-semibold text-[#064E3B]">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[#0F172A]">{label}</p>
        <p className="mt-1 text-sm text-[#4B635A]">{value}</p>
      </div>
      <SetupStatusBadge tone={tone}>{status}</SetupStatusBadge>
    </div>
  );
}

export default function SetupPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [companyProfile, setCompanyProfile] = useState<CompanyProfile | null>(null);
  const [emailSettings, setEmailSettings] = useState<OrganizationEmailSettings | null>(null);
  const [companyForm, setCompanyForm] = useState<CompanyProfileForm>(emptyCompanyForm);
  const [emailForm, setEmailForm] = useState<EmailSettingsForm>(emptyEmailForm);
  const [testRecipientEmail, setTestRecipientEmail] = useState("");
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingCompany, setIsSavingCompany] = useState(false);
  const [isSavingEmail, setIsSavingEmail] = useState(false);
  const [isSendingTest, setIsSendingTest] = useState(false);
  const [pageError, setPageError] = useState("");
  const [companyError, setCompanyError] = useState("");
  const [companySuccess, setCompanySuccess] = useState("");
  const [emailError, setEmailError] = useState("");
  const [emailSuccess, setEmailSuccess] = useState("");
  const [testEmailSuccess, setTestEmailSuccess] = useState("");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
      if ((storedUser.role ?? "").toLowerCase() !== "admin") {
        router.replace("/dashboard");
        return;
      }
    }

    async function loadSetup() {
      setIsLoading(true);
      setPageError("");

      try {
        const profile = await fetchCurrentUser();
        if ((profile.role ?? "").toLowerCase() !== "admin") {
          router.replace("/dashboard");
          return;
        }
        setUser(profile);

        const [company, email] = await Promise.all([fetchCompanyProfile(), fetchOrganizationEmailSettings()]);
        setCompanyProfile(company);
        setEmailSettings(email);
        setCompanyForm(readCompanyForm(company));
        setEmailForm(readEmailForm(email));
        setTestRecipientEmail(company.communication_email || email.reply_to_email || email.from_email || "");
      } catch (loadError) {
        const message = loadError instanceof Error ? loadError.message : "Unable to load the organization setup.";
        setPageError(message);
        if (message.includes("sign in again")) {
          router.replace("/login");
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadSetup();
  }, [router]);

  const brandingName = useMemo(() => {
    return companyProfile?.branding_name || companyForm.company_name || companyForm.legal_name || "OMMS";
  }, [companyForm.company_name, companyForm.legal_name, companyProfile?.branding_name]);

  const companyChecklist = useMemo(
    () => [
      Boolean(companyForm.company_name || companyForm.legal_name),
      Boolean(companyForm.communication_email),
      Boolean(companyForm.gstin && companyForm.state_code),
      Boolean(companyForm.bank_details),
      Boolean(companyForm.authorised_signatory),
    ],
    [
      companyForm.authorised_signatory,
      companyForm.bank_details,
      companyForm.communication_email,
      companyForm.company_name,
      companyForm.gstin,
      companyForm.legal_name,
      companyForm.state_code,
    ],
  );

  const companyCompletion = `${companyChecklist.filter(Boolean).length}/${companyChecklist.length}`;
  const emailConfigured = Boolean(emailForm.from_email && emailForm.smtp_host && emailForm.smtp_port);
  const companyComplete = companyChecklist.every(Boolean);
  const smtpLabel = emailSettings?.email_verified ? "Verified" : emailConfigured ? "Configured" : "Pending";
  const companyStatusValue = companyComplete
    ? "Profile saved"
    : companyProfile?.company_name
      ? "Partially configured"
      : "Using fallback";
  const companyStatusBadge = companyComplete ? "Complete" : "Incomplete";
  const smtpStatusValue = emailConfigured
    ? emailSettings?.email_verified
      ? "Verified sender"
      : "Sender configured"
    : "Not configured";
  const smtpStatusBadge = emailConfigured ? "Configured" : "Pending";

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  function handleCompanyChange(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value } = event.target;
    setCompanyForm((current) => ({ ...current, [name]: value }));
  }

  function handleEmailChange(event: ChangeEvent<HTMLInputElement>) {
    const { name, type, checked, value } = event.target;
    setEmailForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function handleCompanySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingCompany(true);
    setCompanyError("");
    setCompanySuccess("");

    try {
      const formData = new FormData();
      Object.entries(companyForm).forEach(([key, value]) => {
        formData.append(key, value);
      });
      if (logoFile) {
        formData.append("logo", logoFile);
      }

      const updated = await updateCompanyProfile(formData);
      setCompanyProfile(updated);
      setCompanyForm(readCompanyForm(updated));
      setCompanySuccess("Company profile saved. OMMS will use this branding once setup is complete.");
      setLogoFile(null);
      if (!testRecipientEmail) {
        setTestRecipientEmail(updated.communication_email || "");
      }
    } catch (saveError) {
      setCompanyError(saveError instanceof Error ? saveError.message : "Unable to save the company profile.");
    } finally {
      setIsSavingCompany(false);
    }
  }

  async function handleEmailSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingEmail(true);
    setEmailError("");
    setEmailSuccess("");
    setTestEmailSuccess("");

    try {
      const payload: Record<string, unknown> = {
        from_email: emailForm.from_email,
        reply_to_email: emailForm.reply_to_email,
        smtp_host: emailForm.smtp_host,
        smtp_port: Number(emailForm.smtp_port || 587),
        smtp_username: emailForm.smtp_username,
        use_tls: emailForm.use_tls,
        use_ssl: emailForm.use_ssl,
      };
      if (emailForm.smtp_password) {
        payload.smtp_password = emailForm.smtp_password;
      }

      const updated = await updateOrganizationEmailSettings(payload);
      setEmailSettings(updated);
      setEmailForm(readEmailForm(updated));
      setEmailSuccess("Email settings saved. Run a test email to verify delivery.");
      if (!testRecipientEmail) {
        setTestRecipientEmail(companyForm.communication_email || updated.reply_to_email || updated.from_email || "");
      }
    } catch (saveError) {
      setEmailError(saveError instanceof Error ? saveError.message : "Unable to save email settings.");
    } finally {
      setIsSavingEmail(false);
    }
  }

  async function handleSendTestEmail() {
    setIsSendingTest(true);
    setEmailError("");
    setTestEmailSuccess("");

    try {
      const response = await sendOrganizationTestEmail(testRecipientEmail.trim() || undefined);
      setTestEmailSuccess(`Test email sent to ${response.recipient_email}.`);
      setEmailSettings((current) => (current ? { ...current, email_verified: true } : current));
    } catch (sendError) {
      setEmailError(sendError instanceof Error ? sendError.message : "Unable to send the test email.");
    } finally {
      setIsSendingTest(false);
    }
  }

  return (
    <AppShell
      active="setup"
      roleLabel={user?.role ?? "Admin"}
      userEmail={user?.email ?? "Loading user..."}
      title="Organization setup"
      eyebrow="Admin setup"
      description="Configure company profile and email settings for OMMS."
      hideWorkspaceHeader
      onLogout={handleLogout}
    >
      {pageError ? <p className="error dashboard-error">{pageError}</p> : null}
      <section className="flex w-full min-w-0 max-w-none flex-col gap-5 overflow-hidden">
        <header className="rounded-lg border border-[#DDE8E3] bg-white px-5 py-4 shadow-[0_10px_26px_rgba(15,23,42,0.05)] md:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-4">
              <button
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#DDE8E3] bg-white text-lg text-[#064E3B] transition hover:border-[#064E3B]"
                type="button"
                onClick={() => router.push("/dashboard")}
                aria-label="Back to dashboard"
              >
                ←
              </button>
              <div className="min-w-0">
                <h1 className="text-[28px] font-semibold tracking-[-0.03em] text-[#0F172A]">Organization setup</h1>
                <p className="mt-1 text-sm leading-6 text-[#4B635A]">
                  Configure company profile and email settings for OMMS.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3 lg:justify-end">
              <SetupHeaderBadge tone="neutral">{companyCompletion} completed</SetupHeaderBadge>
              <SetupHeaderBadge tone="pending">SMTP {smtpLabel.toLowerCase()}</SetupHeaderBadge>
            </div>
          </div>
        </header>

        <section className="grid min-w-0 gap-5 xl:grid-cols-[220px_minmax(0,1fr)] min-[1536px]:grid-cols-[240px_minmax(0,1fr)_320px]">
          <aside className="order-1 min-w-0">
            <article className="rounded-lg border border-[#DDE8E3] bg-white p-5 shadow-[0_10px_26px_rgba(15,23,42,0.05)] xl:sticky xl:top-6">
              <div className="space-y-8">
                <SetupStep
                  step={1}
                  title="Company Profile"
                  description="Branding, business and compliance"
                  state={companyComplete ? "complete" : "active"}
                />
                <SetupStep
                  step={2}
                  title="Email Settings"
                  description="SMTP configuration and sender identity"
                  state={emailConfigured ? "complete" : "pending"}
                  isLast
                />
              </div>
            </article>
          </aside>

          <aside className="order-2 min-w-0 xl:order-3 min-[1536px]:col-start-3">
            <article className="rounded-lg border border-[#DDE8E3] bg-white p-5 shadow-[0_10px_26px_rgba(15,23,42,0.05)] min-[1536px]:sticky min-[1536px]:top-6">
              <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-[#0F172A]">Workspace summary</h2>

              <div className="mt-5 flex flex-col items-center rounded-lg border border-[#DDE8E3] bg-[#FAFCFB] px-5 py-6 text-center">
                <div className="flex h-[72px] w-[72px] items-center justify-center overflow-hidden rounded-lg bg-[#064E3B] text-[28px] font-semibold text-white shadow-[0_10px_24px_rgba(6,78,59,0.16)]">
                  {companyProfile?.logo_url ? (
                    <img className="h-full w-full object-cover" src={companyProfile.logo_url} alt={`${brandingName} logo`} />
                  ) : (
                    <span>{brandingName.slice(0, 2).toUpperCase()}</span>
                  )}
                </div>
                <p className="mt-4 text-[26px] font-semibold tracking-[-0.03em] text-[#0F172A]">{brandingName}</p>
                <span className="mt-3 inline-flex min-h-8 items-center rounded-md border border-[#DDE8E3] bg-white px-3 text-xs font-semibold text-[#064E3B]">
                  Active workspace brand
                </span>
              </div>

              <div className="my-5 h-px bg-[#DDE8E3]" />

              <div className="space-y-3">
                <WorkspaceStatusRow
                  label="Company profile"
                  value={companyStatusValue}
                  status={companyStatusBadge}
                  tone={companyComplete ? "success" : "pending"}
                  icon="CP"
                />
                <WorkspaceStatusRow
                  label="SMTP status"
                  value={smtpStatusValue}
                  status={smtpStatusBadge}
                  tone={emailConfigured ? "success" : "pending"}
                  icon="SM"
                />
              </div>

              <p className="mt-5 text-center text-sm leading-6 text-[#4B635A]">
                Complete all steps to make OMMS your official brand.
              </p>
            </article>
          </aside>

          <div className="order-3 min-w-0 max-w-full space-y-5 overflow-hidden xl:order-2 xl:col-start-2 xl:row-span-2 min-[1536px]:row-span-1">
            <SetupCard
              title="Company Profile"
              subtitle="Set up your organization's identity and business details."
              headerAction={
                <SetupStatusBadge tone={companyComplete ? "success" : "pending"}>
                  {companyComplete ? "Complete" : "In progress"}
                </SetupStatusBadge>
              }
            >
              {companyError ? <p className="error">{companyError}</p> : null}
              {companySuccess ? <p className="success">{companySuccess}</p> : null}

              <form className="form mt-0 gap-5" onSubmit={handleCompanySubmit}>
                <FormGroup
                  title="Branding"
                  subtitle="This will be used across invoices, emails and client-facing experiences."
                >
                  <div className="grid min-w-0 gap-5 min-[1700px]:grid-cols-[minmax(620px,1fr)_240px]">
                    <div className="grid min-w-0 gap-4 md:grid-cols-2">
                      <div className="field">
                        <label htmlFor="company_name">Company Name</label>
                        <input
                          id="company_name"
                          name="company_name"
                          value={companyForm.company_name}
                          onChange={handleCompanyChange}
                          placeholder="Enter company name"
                        />
                      </div>
                      <div className="field">
                        <label htmlFor="legal_name">Legal Name</label>
                        <input
                          id="legal_name"
                          name="legal_name"
                          value={companyForm.legal_name}
                          onChange={handleCompanyChange}
                          placeholder="Enter legal name"
                        />
                      </div>
                      <div className="field">
                        <label htmlFor="communication_email">Communication Email</label>
                        <input
                          id="communication_email"
                          name="communication_email"
                          type="email"
                          value={companyForm.communication_email}
                          onChange={handleCompanyChange}
                          placeholder="team@company.com"
                        />
                      </div>
                      <div className="field">
                        <label htmlFor="phone">Phone</label>
                        <input
                          id="phone"
                          name="phone"
                          value={companyForm.phone}
                          onChange={handleCompanyChange}
                          placeholder="+91 98765 43210"
                        />
                      </div>
                      <div className="field md:col-span-2">
                        <label htmlFor="address">Address</label>
                        <textarea
                          id="address"
                          name="address"
                          value={companyForm.address}
                          onChange={handleCompanyChange}
                          placeholder="Enter registered office address"
                        />
                      </div>
                    </div>

                    <div className="field w-full max-w-[260px] min-[1700px]:justify-self-end">
                      <label htmlFor="logo">Brand Logo</label>
                      <label
                        htmlFor="logo"
                        className="flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-[#C8D8D0] bg-white px-5 py-6 text-center transition hover:border-[#064E3B] hover:bg-[#FAFCFB]"
                      >
                        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-md border border-[#DDE8E3] bg-white text-xl text-[#064E3B]">
                          ⤴
                        </div>
                        {companyProfile?.logo_url ? (
                          <div className="mb-3 overflow-hidden rounded-md border border-[#DDE8E3] bg-[#FAFCFB]">
                            <img
                              className="h-16 w-16 object-cover"
                              src={companyProfile.logo_url}
                              alt={`${brandingName} logo preview`}
                            />
                          </div>
                        ) : null}
                        <p className="max-w-full truncate text-sm font-semibold text-[#0F172A]">
                          {logoFile ? logoFile.name : "Upload logo"}
                        </p>
                        <p className="mt-1 text-xs text-[#4B635A]">PNG, JPG up to 2MB</p>
                      </label>
                      <input
                        id="logo"
                        name="logo"
                        className="sr-only"
                        type="file"
                        accept="image/png,image/jpeg,image/webp,image/svg+xml"
                        onChange={(event) => setLogoFile(event.target.files?.[0] ?? null)}
                      />
                    </div>
                  </div>
                </FormGroup>

                <FormGroup
                  title="Business Details"
                  subtitle="Legal and tax information for invoicing and compliance."
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="field">
                      <label htmlFor="gstin">GST Number</label>
                      <input
                        id="gstin"
                        name="gstin"
                        value={companyForm.gstin}
                        onChange={handleCompanyChange}
                        placeholder="Enter GST number"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="invoice_prefix">Invoice Prefix</label>
                      <input
                        id="invoice_prefix"
                        name="invoice_prefix"
                        value={companyForm.invoice_prefix}
                        onChange={handleCompanyChange}
                        placeholder="Enter invoice prefix"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="state_code">State Code</label>
                      <input
                        id="state_code"
                        name="state_code"
                        value={companyForm.state_code}
                        onChange={handleCompanyChange}
                        placeholder="Enter state code"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="authorised_signatory">Authorised Signatory</label>
                      <input
                        id="authorised_signatory"
                        name="authorised_signatory"
                        value={companyForm.authorised_signatory}
                        onChange={handleCompanyChange}
                        placeholder="Enter signatory name"
                      />
                    </div>
                    <div className="field md:col-span-2">
                      <label htmlFor="bank_details">Bank Details</label>
                      <textarea
                        id="bank_details"
                        name="bank_details"
                        value={companyForm.bank_details}
                        onChange={handleCompanyChange}
                        placeholder="Account holder, bank name, account number, branch, IFSC"
                      />
                    </div>
                  </div>
                </FormGroup>

                <div className="form-actions justify-end pt-1">
                  <button className="submit min-w-[190px]" type="submit" disabled={isSavingCompany}>
                    {isSavingCompany ? "Saving profile..." : "Save & Continue"}
                  </button>
                </div>
              </form>
            </SetupCard>

            <SetupCard
              title="Email Settings"
              subtitle="Configure sender identity and SMTP credentials."
              headerAction={
                <SetupStatusBadge tone={emailConfigured ? "success" : "pending"}>
                  {emailConfigured ? "Configured" : "Pending"}
                </SetupStatusBadge>
              }
            >
              {emailError ? <p className="error">{emailError}</p> : null}
              {emailSuccess ? <p className="success">{emailSuccess}</p> : null}
              {testEmailSuccess ? <p className="success">{testEmailSuccess}</p> : null}

              <form className="form mt-0 gap-5" onSubmit={handleEmailSubmit}>
                <FormGroup
                  title="Sender Identity"
                  subtitle="Choose the visible sender addresses OMMS will use for workflow emails."
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="field">
                      <label htmlFor="from_email">From Email</label>
                      <input
                        id="from_email"
                        name="from_email"
                        type="email"
                        value={emailForm.from_email}
                        onChange={handleEmailChange}
                        placeholder="no-reply@yourcompany.com"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="reply_to_email">Reply-to Email</label>
                      <input
                        id="reply_to_email"
                        name="reply_to_email"
                        type="email"
                        value={emailForm.reply_to_email}
                        onChange={handleEmailChange}
                        placeholder="support@yourcompany.com"
                      />
                    </div>
                  </div>
                </FormGroup>

                <FormGroup
                  title="SMTP Connection"
                  subtitle="Store the server credentials securely so OMMS can deliver notifications later."
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="field">
                      <label htmlFor="smtp_host">SMTP Host</label>
                      <input
                        id="smtp_host"
                        name="smtp_host"
                        value={emailForm.smtp_host}
                        onChange={handleEmailChange}
                        placeholder="smtp.provider.com"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="smtp_port">SMTP Port</label>
                      <input
                        id="smtp_port"
                        name="smtp_port"
                        type="number"
                        min="1"
                        value={emailForm.smtp_port}
                        onChange={handleEmailChange}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="smtp_username">SMTP Username</label>
                      <input
                        id="smtp_username"
                        name="smtp_username"
                        value={emailForm.smtp_username}
                        onChange={handleEmailChange}
                        placeholder="smtp-user"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="smtp_password">SMTP Password</label>
                      <input
                        id="smtp_password"
                        name="smtp_password"
                        type="password"
                        value={emailForm.smtp_password}
                        onChange={handleEmailChange}
                        placeholder={emailSettings?.has_smtp_password ? "Leave blank to keep current password" : "Enter SMTP password"}
                      />
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-3">
                    <label className="inline-flex items-center gap-2 rounded-md border border-[#DDE8E3] bg-white px-4 py-2 text-sm font-medium text-[#0F172A]">
                      <input type="checkbox" name="use_tls" checked={emailForm.use_tls} onChange={handleEmailChange} />
                      <span>Use TLS</span>
                    </label>
                    <label className="inline-flex items-center gap-2 rounded-md border border-[#DDE8E3] bg-white px-4 py-2 text-sm font-medium text-[#0F172A]">
                      <input type="checkbox" name="use_ssl" checked={emailForm.use_ssl} onChange={handleEmailChange} />
                      <span>Use SSL</span>
                    </label>
                  </div>
                </FormGroup>

                <FormGroup
                  title="Verification"
                  subtitle="Send a test email to confirm the connection works before live notifications depend on it."
                >
                  <div className="flex flex-col gap-3 lg:flex-row">
                    <input
                      className="min-h-[48px] flex-1 rounded-md border border-[#DDE8E3] bg-white px-4 text-sm shadow-sm focus:border-[#064E3B] focus:outline-none focus:ring-4 focus:ring-[rgba(6,78,59,0.10)]"
                      type="email"
                      value={testRecipientEmail}
                      onChange={(event) => setTestRecipientEmail(event.target.value)}
                      placeholder="recipient@example.com"
                    />
                    <button
                      className="ghost min-h-[54px] shrink-0 px-5"
                      type="button"
                      onClick={handleSendTestEmail}
                      disabled={isSendingTest}
                    >
                      {isSendingTest ? "Sending..." : "Send test email"}
                    </button>
                  </div>
                </FormGroup>

                <div className="form-actions justify-end pt-1">
                  <button className="submit min-w-[190px]" type="submit" disabled={isSavingEmail}>
                    {isSavingEmail ? "Saving email settings..." : "Save email settings"}
                  </button>
                </div>
              </form>
            </SetupCard>
          </div>
        </section>
      </section>
    </AppShell>
  );
}
