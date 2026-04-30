"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
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
      eyebrow="White-label foundation"
      description="Configure the single-tenant OMMS brand, GST details, and SMTP connection before layering invoice and notification workflows on top."
      onLogout={handleLogout}
    >
      {pageError ? <p className="error dashboard-error">{pageError}</p> : null}

      <section className="setup-page-head">
        <div className="setup-page-copy">
          <span className="setup-kicker">Admin onboarding</span>
          <h2>White-label OMMS before the rest of the workflows go live.</h2>
          <p>
            Set the company identity and sender configuration once, then let invoicing, email, and client-facing
            experiences inherit the same polished brand surface.
          </p>
        </div>
        <aside className="setup-command-card">
          <div className="setup-command-top">
            <div>
              <p className="stat-label">Active workspace brand</p>
              <p className="setup-command-name">{brandingName}</p>
            </div>
            <span className="setup-status-chip setup-status-chip-soft">{companyCompletion} complete</span>
          </div>
          <div className="setup-brand-preview setup-brand-preview-hero">
            <div className="setup-brand-mark">
              {companyProfile?.logo_url ? (
                <img src={companyProfile.logo_url} alt={`${brandingName} logo`} />
              ) : (
                <span>{brandingName.slice(0, 2).toUpperCase()}</span>
              )}
            </div>
            <div className="setup-brand-copy">
              <p className="stat-label">Active branding</p>
              <p className="setup-brand-name">{brandingName}</p>
              <p className="helper">
                {companyProfile?.company_name
                  ? "This name will flow into future invoices, emails, and branded client surfaces."
                  : "OMMS stays as the fallback until you save your company identity."}
              </p>
            </div>
          </div>
          <div className="setup-command-meta">
            <div className="setup-command-stat">
              <span>Company profile</span>
              <strong>{companyProfile?.company_name || "Using fallback"}</strong>
            </div>
            <div className="setup-command-stat">
              <span>SMTP status</span>
              <strong>{emailSettings?.email_verified ? "Verified" : emailConfigured ? "Configured" : "Pending"}</strong>
            </div>
          </div>
        </aside>
      </section>

      <section className="setup-stepper" aria-label="Setup flow">
        <article className="setup-step-item setup-step-item-active">
          <span className="setup-step-count">1</span>
          <div>
            <p className="setup-step-title">Company Profile</p>
            <p className="setup-step-copy">Brand, GST, invoice prefix, banking, and signatory defaults.</p>
          </div>
        </article>
        <article className={`setup-step-item ${emailConfigured ? "setup-step-item-active" : ""}`}>
          <span className="setup-step-count">2</span>
          <div>
            <p className="setup-step-title">Email Settings</p>
            <p className="setup-step-copy">Sender identity, SMTP credentials, and live verification.</p>
          </div>
        </article>
      </section>

      <section className="setup-stack">
        <article className="module-card module-card-wide setup-panel">
          <div className="setup-panel-head">
            <div>
              <span className="setup-section-tag">Step 1</span>
              <h2>Company Profile</h2>
              <p className="helper">
                Set the seller identity that OMMS will use for branding, GST-facing records, and invoice defaults.
              </p>
            </div>
            <div className="setup-panel-meta">
              <span className="setup-status-chip">Completion {companyCompletion}</span>
              <span className="setup-status-chip setup-status-chip-soft">{brandingName}</span>
            </div>
          </div>
          {companyError ? <p className="error">{companyError}</p> : null}
          {companySuccess ? <p className="success">{companySuccess}</p> : null}

          <form className="form" onSubmit={handleCompanySubmit}>
            <div className="setup-section-card">
              <div className="setup-section-header">
                <div>
                  <h3>Identity and communication</h3>
                  <p>Define the commercial brand and the main points of contact your team will use externally.</p>
                </div>
              </div>
              <div className="setup-form-grid">
                <div className="field">
                  <label htmlFor="company_name">Company name</label>
                  <input id="company_name" name="company_name" value={companyForm.company_name} onChange={handleCompanyChange} placeholder="OMMS Media" />
                </div>
                <div className="field">
                  <label htmlFor="legal_name">Legal name</label>
                  <input id="legal_name" name="legal_name" value={companyForm.legal_name} onChange={handleCompanyChange} placeholder="Outdoor Media Management Services Pvt. Ltd." />
                </div>
                <div className="field">
                  <label htmlFor="communication_email">Communication email</label>
                  <input id="communication_email" name="communication_email" type="email" value={companyForm.communication_email} onChange={handleCompanyChange} placeholder="hello@yourcompany.com" />
                </div>
                <div className="field">
                  <label htmlFor="phone">Phone</label>
                  <input id="phone" name="phone" value={companyForm.phone} onChange={handleCompanyChange} placeholder="+91 98765 43210" />
                </div>
                <div className="field field-span-2">
                  <label htmlFor="address">Address</label>
                  <textarea id="address" name="address" value={companyForm.address} onChange={handleCompanyChange} placeholder="Registered office address" />
                </div>
              </div>
            </div>

            <div className="setup-section-card">
              <div className="setup-section-header">
                <div>
                  <h3>Tax and billing defaults</h3>
                  <p>These values become the starting point for GST-ready billing and document generation.</p>
                </div>
              </div>
              <div className="setup-form-grid">
                <div className="field">
                  <label htmlFor="gstin">GSTIN</label>
                  <input id="gstin" name="gstin" value={companyForm.gstin} onChange={handleCompanyChange} placeholder="22AAAAA0000A1Z5" />
                </div>
                <div className="field">
                  <label htmlFor="state_code">State code</label>
                  <input id="state_code" name="state_code" value={companyForm.state_code} onChange={handleCompanyChange} placeholder="01" />
                </div>
                <div className="field">
                  <label htmlFor="invoice_prefix">Invoice prefix</label>
                  <input id="invoice_prefix" name="invoice_prefix" value={companyForm.invoice_prefix} onChange={handleCompanyChange} placeholder="INV" />
                </div>
                <div className="field">
                  <label htmlFor="authorised_signatory">Authorised signatory</label>
                  <input id="authorised_signatory" name="authorised_signatory" value={companyForm.authorised_signatory} onChange={handleCompanyChange} placeholder="Authorised signatory name" />
                </div>
                <div className="field field-span-2">
                  <label htmlFor="bank_details">Bank details</label>
                  <textarea id="bank_details" name="bank_details" value={companyForm.bank_details} onChange={handleCompanyChange} placeholder="Account holder, bank, branch, account number, IFSC" />
                </div>
              </div>
            </div>

            <div className="setup-section-card">
              <div className="setup-section-header">
                <div>
                  <h3>Brand asset</h3>
                  <p>Upload a clean logo now so future invoices and branded screens can pick it up automatically.</p>
                </div>
              </div>
              <div className="setup-upload-row">
                <div className="field">
                  <label htmlFor="logo">Logo</label>
                  <input
                    id="logo"
                    name="logo"
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/svg+xml"
                    onChange={(event) => setLogoFile(event.target.files?.[0] ?? null)}
                  />
                  <p className="field-help">PNG or JPEG works best for the current OMMS theme.</p>
                </div>
                <div className="setup-mini-preview">
                  <div className="setup-brand-mark setup-brand-mark-small">
                    {companyProfile?.logo_url ? (
                      <img src={companyProfile.logo_url} alt={`${brandingName} logo`} />
                    ) : (
                      <span>{brandingName.slice(0, 2).toUpperCase()}</span>
                    )}
                  </div>
                  <div>
                    <p className="stat-label">Preview</p>
                    <p className="setup-mini-preview-name">{brandingName}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="form-actions">
              <button className="submit" type="submit" disabled={isSavingCompany}>
                {isSavingCompany ? "Saving profile..." : "Save company profile"}
              </button>
            </div>
          </form>
        </article>

        <article className="module-card module-card-wide setup-panel">
          <div className="setup-panel-head">
            <div>
              <span className="setup-section-tag">Step 2</span>
              <h2>Email Settings</h2>
              <p className="helper">
                Configure a sender identity for future workflow emails. Credentials stay encrypted and private.
              </p>
            </div>
            <div className="setup-panel-meta">
              <span className={`setup-status-chip ${emailSettings?.email_verified ? "setup-status-chip-success" : ""}`}>
                {emailSettings?.email_verified ? "SMTP verified" : "Verification pending"}
              </span>
              <span className="setup-status-chip setup-status-chip-soft">
                {emailSettings?.has_smtp_password ? "Password stored" : "Password missing"}
              </span>
            </div>
          </div>
          {emailError ? <p className="error">{emailError}</p> : null}
          {emailSuccess ? <p className="success">{emailSuccess}</p> : null}
          {testEmailSuccess ? <p className="success">{testEmailSuccess}</p> : null}

          <form className="form" onSubmit={handleEmailSubmit}>
            <div className="setup-section-card">
              <div className="setup-section-header">
                <div>
                  <h3>Sender identity</h3>
                  <p>Choose the visible sender addresses clients will see when OMMS sends workflow emails later.</p>
                </div>
              </div>
              <div className="setup-form-grid">
                <div className="field">
                  <label htmlFor="from_email">From email</label>
                  <input id="from_email" name="from_email" type="email" value={emailForm.from_email} onChange={handleEmailChange} placeholder="no-reply@yourcompany.com" />
                </div>
                <div className="field">
                  <label htmlFor="reply_to_email">Reply-to email</label>
                  <input id="reply_to_email" name="reply_to_email" type="email" value={emailForm.reply_to_email} onChange={handleEmailChange} placeholder="support@yourcompany.com" />
                </div>
              </div>
            </div>

            <div className="setup-section-card">
              <div className="setup-section-header">
                <div>
                  <h3>SMTP connection</h3>
                  <p>Store the server credentials securely now, then verify with a live test send below.</p>
                </div>
              </div>
              <div className="setup-form-grid">
                <div className="field">
                  <label htmlFor="smtp_host">SMTP host</label>
                  <input id="smtp_host" name="smtp_host" value={emailForm.smtp_host} onChange={handleEmailChange} placeholder="smtp.provider.com" />
                </div>
                <div className="field">
                  <label htmlFor="smtp_port">SMTP port</label>
                  <input id="smtp_port" name="smtp_port" type="number" min="1" value={emailForm.smtp_port} onChange={handleEmailChange} />
                </div>
                <div className="field">
                  <label htmlFor="smtp_username">SMTP username</label>
                  <input id="smtp_username" name="smtp_username" value={emailForm.smtp_username} onChange={handleEmailChange} placeholder="smtp-user" />
                </div>
                <div className="field">
                  <label htmlFor="smtp_password">SMTP password</label>
                  <input
                    id="smtp_password"
                    name="smtp_password"
                    type="password"
                    value={emailForm.smtp_password}
                    onChange={handleEmailChange}
                    placeholder={emailSettings?.has_smtp_password ? "Leave blank to keep current password" : ""}
                  />
                </div>
              </div>

              <div className="setup-checkbox-row">
                <label className="setup-checkbox">
                  <input type="checkbox" name="use_tls" checked={emailForm.use_tls} onChange={handleEmailChange} />
                  <span>Use TLS</span>
                </label>
                <label className="setup-checkbox">
                  <input type="checkbox" name="use_ssl" checked={emailForm.use_ssl} onChange={handleEmailChange} />
                  <span>Use SSL</span>
                </label>
              </div>
            </div>

            <div className="form-actions">
              <button className="submit" type="submit" disabled={isSavingEmail}>
                {isSavingEmail ? "Saving email settings..." : "Save email settings"}
              </button>
            </div>
          </form>

          <div className="setup-test-card">
            <div className="setup-test-copy">
              <span className="setup-section-tag">Verification</span>
              <h3>Send a live SMTP check</h3>
              <p className="helper">
                Confirm the mailbox and server path work end to end before later notification flows depend on them.
              </p>
            </div>
            <div className="setup-test-actions">
              <input
                className="setup-inline-input"
                type="email"
                value={testRecipientEmail}
                onChange={(event) => setTestRecipientEmail(event.target.value)}
                placeholder="recipient@example.com"
              />
              <button className="ghost setup-secondary-action" type="button" onClick={handleSendTestEmail} disabled={isSendingTest}>
                {isSendingTest ? "Sending..." : "Send test email"}
              </button>
            </div>
          </div>
        </article>
      </section>
    </AppShell>
  );
}
