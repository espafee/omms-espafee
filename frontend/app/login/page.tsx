"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getAccessToken, loginWithEmailPassword, storeAuthSession } from "@/lib/auth";

const portalParentOrigins = [
  "https://www.vistaaitech.com",
  "http://localhost:3000",
  "http://localhost:3001",
  "http://localhost:3010",
];

function notifyPortalLogin() {
  if (typeof window === "undefined" || window.parent === window) {
    return;
  }

  for (const origin of portalParentOrigins) {
    window.parent.postMessage({ type: "omms:auth:success" }, origin);
  }
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function getLoginErrorMessage(errorValue: unknown) {
    if (errorValue instanceof Error) {
      console.error("Login failed:", errorValue.message);
    }
    return "Invalid email or password. Please try again.";
  }

  useEffect(() => {
    if (getAccessToken()) {
      notifyPortalLogin();
      router.replace("/dashboard");
    }
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const payload = await loginWithEmailPassword(email, password);
      storeAuthSession(payload);
      notifyPortalLogin();
      router.push("/dashboard");
    } catch (submitError) {
      setError(getLoginErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="shell">
      <section className="panel card-grid">
        <div className="hero">
          <span className="eyebrow">Outdoor Media Management</span>
          <h1>Operate inventory, campaigns, and billing from one place.</h1>
          <p>
            Sign in to manage billboard inventory, coordinate live bookings, verify proof of execution,
            and track receivables without switching systems.
          </p>
          <ul className="feature-list">
            <li>Centralized campaign and booking visibility</li>
            <li>Secure access for role-based teams</li>
            <li>Clean handoff from sales to operations and finance</li>
          </ul>
        </div>

        <div className="form-wrap">
          <h2 className="section-title">Welcome back</h2>
          <p className="section-copy">
            Use your email and password to access the dashboard.
          </p>

          <form className="form" onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="name@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            {error ? <p className="error">{error}</p> : null}

            <button className="submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
