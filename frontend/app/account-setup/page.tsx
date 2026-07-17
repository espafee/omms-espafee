"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { ApiError } from "@/lib/auth";
import { completeAccountSetup } from "@/lib/team";

export default function AccountSetupPage() {
  const [uid, setUid] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setUid(params.get("uid") ?? "");
    setToken(params.get("token") ?? "");
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!uid || !token) {
      setError("This account setup link is incomplete. Ask your administrator to send a new one.");
      return;
    }
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await completeAccountSetup({ uid, token, password });
      setSuccess(response.detail);
      setPassword("");
      setConfirmation("");
    } catch (setupError) {
      setError(setupError instanceof ApiError ? setupError.message : "Unable to complete account setup.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="shell account-setup-shell">
      <section className="panel account-setup-panel">
        <div className="account-setup-intro">
          <span className="eyebrow">OMMS secure access</span>
          <h1>Set up your account</h1>
          <p>Create a strong password for your company workspace. Your role and data access are controlled by your company administrator.</p>
        </div>
        {success ? (
          <div className="account-setup-success"><h2>Account ready</h2><p>{success}</p><Link className="submit account-setup-link" href="/login">Continue to sign in</Link></div>
        ) : (
          <form className="form account-setup-form" onSubmit={handleSubmit}>
            <div className="field"><label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" minLength={10} value={password} onChange={(event) => setPassword(event.target.value)} required /><small>Use at least 10 characters and avoid common passwords.</small></div>
            <div className="field"><label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type="password" autoComplete="new-password" minLength={10} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required /></div>
            {error ? <p className="error">{error}</p> : null}
            <button className="submit" type="submit" disabled={isSubmitting}>{isSubmitting ? "Setting password..." : "Set password"}</button>
          </form>
        )}
      </section>
    </main>
  );
}
