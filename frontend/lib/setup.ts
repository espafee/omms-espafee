import { apiFetch, apiUpload } from "@/lib/auth";

export type CompanyProfile = {
  id: number;
  company_name: string;
  legal_name: string;
  logo: string | null;
  logo_url: string | null;
  communication_email: string;
  phone: string;
  address: string;
  gstin: string;
  state_code: string;
  invoice_prefix: string;
  bank_details: string;
  authorised_signatory: string;
  branding_name: string;
  created_at: string;
  updated_at: string;
};

export type OrganizationEmailSettings = {
  id: number;
  from_email: string;
  reply_to_email: string;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  has_smtp_password: boolean;
  use_tls: boolean;
  use_ssl: boolean;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
};

export type TestEmailResponse = {
  status: string;
  recipient_email: string;
};

export async function fetchCompanyProfile() {
  return apiFetch<CompanyProfile>("setup/company-profile/");
}

export async function updateCompanyProfile(formData: FormData) {
  return apiUpload<CompanyProfile>("setup/company-profile/", formData, { method: "PATCH" });
}

export async function fetchOrganizationEmailSettings() {
  return apiFetch<OrganizationEmailSettings>("setup/email-settings/");
}

export async function updateOrganizationEmailSettings(payload: Record<string, unknown>) {
  return apiFetch<OrganizationEmailSettings>("setup/email-settings/", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function sendOrganizationTestEmail(recipient_email?: string) {
  return apiFetch<TestEmailResponse>("setup/email-settings/test/", {
    method: "POST",
    body: JSON.stringify(recipient_email ? { recipient_email } : {}),
  });
}
