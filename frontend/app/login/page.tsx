"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  consumeSkipSessionRestore,
  consumeSessionMessage,
  getAccessToken,
  loginWithEmailPassword,
  restoreAuthSession,
  storeAuthSession,
} from "@/lib/auth";

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
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function getLoginErrorMessage() {
    return "Invalid email or password. Please try again.";
  }

  useEffect(() => {
    let isMounted = true;
    const message = consumeSessionMessage();
    const skipRestore = consumeSkipSessionRestore();
    if (message) {
      setError(message);
    }
    async function restore() {
      if (skipRestore) {
        setIsCheckingSession(false);
        return;
      }
      try {
        if (getAccessToken() || (await restoreAuthSession())) {
          notifyPortalLogin();
          router.replace("/dashboard");
          return;
        }
        const restoreMessage = consumeSessionMessage();
        if (restoreMessage && isMounted) {
          setError(restoreMessage);
        }
      } catch (restoreError) {
        if (restoreError instanceof ApiError && restoreError.code === "network_error" && isMounted) {
          setError("We couldn't reach the server. Check your connection and try again.");
        }
      } finally {
        if (isMounted) {
          setIsCheckingSession(false);
        }
      }
    }
    void restore();
    return () => {
      isMounted = false;
    };
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
    } catch {
      setError(getLoginErrorMessage());
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

          {isCheckingSession ? (
            <p className="section-copy" role="status">Checking your session...</p>
          ) : (
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
          )}
        </div>
      </section>
    </main>
  );
}
