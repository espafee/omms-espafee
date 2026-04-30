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

      <section className="summary-row" aria-label="Setup readiness">
        <article className="summary-card">
          <p className="stat-label">Brand fallback</p>
          <p className="summary-value">{brandingName}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Company setup</p>
          <p className="summary-value">{isLoading ? "..." : companyProfile?.company_name || "OMMS default"}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">SMTP verification</p>
          <p className="summary-value">
            {isLoading ? "..." : emailSettings?.email_verified ? "Verified" : "Pending verification"}
          </p>
        </article>
      </section>

      <section className="module-grid setup-grid">
        <article className="module-card module-card-wide">
          <div className="module-head">
            <h2>Step 1. Company profile</h2>
            <span>{brandingName}</span>
          </div>
          <p className="helper">
            OMMS will keep using the fallback branding until you complete the seller identity fields below.
          </p>
          {companyError ? <p className="error">{companyError}</p> : null}
          {companySuccess ? <p className="success">{companySuccess}</p> : null}

          <div className="setup-brand-preview">
            <div className="setup-brand-mark">
              {companyProfile?.logo_url ? (
                <img src={companyProfile.logo_url} alt={`${brandingName} logo`} />
              ) : (
                <span>{brandingName.slice(0, 2).toUpperCase()}</span>
              )}
            </div>
            <div>
              <p className="stat-label">Active branding</p>
              <p className="setup-brand-name">{brandingName}</p>
              <p className="helper">Fallback remains OMMS until you save your final legal and communication details.</p>
            </div>
          </div>

          <form className="form" onSubmit={handleCompanySubmit}>
            <div className="setup-form-grid">
              <div className="field">
                <label htmlFor="company_name">Company name</label>
                <input id="company_name" name="company_name" value={companyForm.company_name} onChange={handleCompanyChange} />
              </div>
              <div className="field">
                <label htmlFor="legal_name">Legal name</label>
                <input id="legal_name" name="legal_name" value={companyForm.legal_name} onChange={handleCompanyChange} />
              </div>
              <div className="field">
                <label htmlFor="communication_email">Communication email</label>
                <input id="communication_email" name="communication_email" type="email" value={companyForm.communication_email} onChange={handleCompanyChange} />
              </div>
              <div className="field">
                <label htmlFor="phone">Phone</label>
                <input id="phone" name="phone" value={companyForm.phone} onChange={handleCompanyChange} />
              </div>
              <div className="field">
                <label htmlFor="gstin">GSTIN</label>
                <input id="gstin" name="gstin" value={companyForm.gstin} onChange={handleCompanyChange} />
              </div>
              <div className="field">
                <label htmlFor="state_code">State code</label>
                <input id="state_code" name="state_code" value={companyForm.state_code} onChange={handleCompanyChange} />
              </div>
              <div className="field">
                <label htmlFor="invoice_prefix">Invoice prefix</label>
                <input id="invoice_prefix" name="invoice_prefix" value={companyForm.invoice_prefix} onChange={handleCompanyChange} />
              </div>
              <div className="field">
                <label htmlFor="authorised_signatory">Authorised signatory</label>
                <input id="authorised_signatory" name="authorised_signatory" value={companyForm.authorised_signatory} onChange={handleCompanyChange} />
              </div>
            </div>

            <div className="field">
              <label htmlFor="address">Address</label>
              <textarea id="address" name="address" value={companyForm.address} onChange={handleCompanyChange} />
            </div>
            <div className="field">
              <label htmlFor="bank_details">Bank details</label>
              <textarea id="bank_details" name="bank_details" value={companyForm.bank_details} onChange={handleCompanyChange} />
            </div>
            <div className="field">
              <label htmlFor="logo">Logo</label>
              <input
                id="logo"
                name="logo"
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                onChange={(event) => setLogoFile(event.target.files?.[0] ?? null)}
              />
              <p className="field-help">Upload a brand mark for future invoices, emails, and client-facing pages.</p>
            </div>

            <div className="form-actions">
              <button className="submit" type="submit" disabled={isSavingCompany}>
                {isSavingCompany ? "Saving profile..." : "Save company profile"}
              </button>
            </div>
          </form>
        </article>

        <article className="module-card module-card-wide">
          <div className="module-head">
            <h2>Step 2. Email settings</h2>
            <span>{emailSettings?.email_verified ? "Verified" : "Verification pending"}</span>
          </div>
          <p className="helper">
            SMTP credentials stay encrypted in the database and are never returned through the API.
          </p>
          {emailError ? <p className="error">{emailError}</p> : null}
          {emailSuccess ? <p className="success">{emailSuccess}</p> : null}
          {testEmailSuccess ? <p className="success">{testEmailSuccess}</p> : null}

          <form className="form" onSubmit={handleEmailSubmit}>
            <div className="setup-form-grid">
              <div className="field">
                <label htmlFor="from_email">From email</label>
                <input id="from_email" name="from_email" type="email" value={emailForm.from_email} onChange={handleEmailChange} />
              </div>
              <div className="field">
                <label htmlFor="reply_to_email">Reply-to email</label>
                <input id="reply_to_email" name="reply_to_email" type="email" value={emailForm.reply_to_email} onChange={handleEmailChange} />
              </div>
              <div className="field">
                <label htmlFor="smtp_host">SMTP host</label>
                <input id="smtp_host" name="smtp_host" value={emailForm.smtp_host} onChange={handleEmailChange} />
              </div>
              <div className="field">
                <label htmlFor="smtp_port">SMTP port</label>
                <input id="smtp_port" name="smtp_port" type="number" min="1" value={emailForm.smtp_port} onChange={handleEmailChange} />
              </div>
              <div className="field">
                <label htmlFor="smtp_username">SMTP username</label>
                <input id="smtp_username" name="smtp_username" value={emailForm.smtp_username} onChange={handleEmailChange} />
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

            <div className="form-actions">
              <button className="submit" type="submit" disabled={isSavingEmail}>
                {isSavingEmail ? "Saving email settings..." : "Save email settings"}
              </button>
            </div>
          </form>

          <div className="setup-test-card">
            <div>
              <p className="stat-label">SMTP verification</p>
              <p className="helper">Send a plain-text test email before enabling any future workflow notifications.</p>
            </div>
            <div className="setup-test-actions">
              <input
                className="setup-inline-input"
                type="email"
                value={testRecipientEmail}
                onChange={(event) => setTestRecipientEmail(event.target.value)}
                placeholder="recipient@example.com"
              />
              <button className="ghost" type="button" onClick={handleSendTestEmail} disabled={isSendingTest}>
                {isSendingTest ? "Sending..." : "Send test email"}
              </button>
            </div>
          </div>
        </article>
      </section>
    </AppShell>
  );
}
