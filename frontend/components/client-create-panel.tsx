"use client";

import { useMemo, useState } from "react";

import { ApiError } from "@/lib/auth";
import { createClient, type ClientCreateInput, type ClientOption } from "@/lib/users";

type ClientCreatePanelProps = {
  onCreated: (client: ClientOption) => Promise<void> | void;
};

const INITIAL_FORM: ClientCreateInput = {
  email: "",
  username: "",
  first_name: "",
  last_name: "",
  phone_number: "",
  organization_name: "",
  password: "",
  is_active: true,
};

export function ClientCreatePanel({ onCreated }: ClientCreatePanelProps) {
  const [form, setForm] = useState<ClientCreateInput>(INITIAL_FORM);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const contactPreview = useMemo(() => {
    const name = [form.first_name, form.last_name].filter(Boolean).join(" ").trim();
    return name || form.email || "Client contact";
  }, [form.email, form.first_name, form.last_name]);

  function updateField<K extends keyof ClientCreateInput>(field: K, value: ClientCreateInput[K]) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function getFieldError(field: keyof ClientCreateInput) {
    return fieldErrors[field]?.[0] ?? "";
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setError("");
    setSuccess("");
    setFieldErrors({});
    setIsSubmitting(true);

    try {
      const client = await createClient(form);
      await onCreated(client);
      setSuccess("Client created and added to the dropdown.");
      setForm({
        ...INITIAL_FORM,
        is_active: form.is_active ?? true,
      });
    } catch (submitError) {
      if (submitError instanceof ApiError) {
        setFieldErrors(submitError.fieldErrors);
        setError(submitError.message || "Unable to create client.");
      } else {
        setError(submitError instanceof Error ? submitError.message : "Unable to create client.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="module-card creation-panel">
      <div className="module-head">
        <h2>Add client</h2>
        <span>Admin only</span>
      </div>
      <p className="section-copy creation-copy">
        Clients are stored as user accounts with the <strong>client</strong> role. Create one here and it will appear in the campaign dropdown immediately.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {success ? <p className="success">{success}</p> : null}
      <form className="client-form-grid" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="client-organization-name">Client name</label>
          <input
            id="client-organization-name"
            value={form.organization_name}
            onChange={(event) => updateField("organization_name", event.target.value)}
            placeholder="Skyline Retail Pvt Ltd"
            required
          />
          {getFieldError("organization_name") ? (
            <p className="field-help field-help-error">{getFieldError("organization_name")}</p>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor="client-email">Email</label>
          <input
            id="client-email"
            type="email"
            value={form.email}
            onChange={(event) => updateField("email", event.target.value)}
            placeholder="contact@skylineads.com"
            required
          />
          {getFieldError("email") ? <p className="field-help field-help-error">{getFieldError("email")}</p> : null}
        </div>
        <div className="field">
          <label htmlFor="client-first-name">Contact first name</label>
          <input
            id="client-first-name"
            value={form.first_name}
            onChange={(event) => updateField("first_name", event.target.value)}
            placeholder="Nadia"
          />
          {getFieldError("first_name") ? (
            <p className="field-help field-help-error">{getFieldError("first_name")}</p>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor="client-last-name">Contact last name</label>
          <input
            id="client-last-name"
            value={form.last_name}
            onChange={(event) => updateField("last_name", event.target.value)}
            placeholder="Shah"
          />
          {getFieldError("last_name") ? (
            <p className="field-help field-help-error">{getFieldError("last_name")}</p>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor="client-username">Username</label>
          <input
            id="client-username"
            value={form.username}
            onChange={(event) => updateField("username", event.target.value)}
            placeholder="nadia_skyline"
            required
          />
          {getFieldError("username") ? (
            <p className="field-help field-help-error">{getFieldError("username")}</p>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor="client-phone-number">Phone number</label>
          <input
            id="client-phone-number"
            value={form.phone_number}
            onChange={(event) => updateField("phone_number", event.target.value)}
            placeholder="+91 98765 43210"
          />
          {getFieldError("phone_number") ? (
            <p className="field-help field-help-error">{getFieldError("phone_number")}</p>
          ) : null}
        </div>
        <div className="field field-full">
          <label htmlFor="client-password">Temporary password</label>
          <input
            id="client-password"
            type="password"
            value={form.password}
            onChange={(event) => updateField("password", event.target.value)}
            placeholder="Minimum 8 characters"
            required
          />
          {getFieldError("password") ? (
            <p className="field-help field-help-error">{getFieldError("password")}</p>
          ) : (
            <p className="field-help">
              This creates the client login account. Internal teams can share or rotate it later.
            </p>
          )}
        </div>
        <div className="field field-full client-panel-preview">
          <span className="site-code">New dropdown entry preview</span>
          <strong>{form.organization_name || contactPreview}</strong>
          <p className="site-copy">{form.email || "Client email will appear here once entered."}</p>
        </div>
        <div className="form-actions field-full">
          <button className="submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating client..." : "Create client"}
          </button>
        </div>
      </form>
    </section>
  );
}
