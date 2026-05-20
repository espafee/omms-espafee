"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { PoeFieldCaptureForm, type PoeCaptureFormState } from "@/components/poe-field-capture-form";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { createPoeWorkflow, fetchPoeData, getPoeCreateError, type PoePayload } from "@/lib/poe";

type StoredUser = {
  id?: number;
  email?: string;
  role?: string;
};

const WRITE_ROLES = new Set(["admin", "operations"]);

const INITIAL_FORM: PoeCaptureFormState = {
  booking: 0,
  executed_on: "",
  notes: "",
  media_type: "image",
};

export default function PoeCapturePage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [poeData, setPoeData] = useState<PoePayload | null>(null);
  const [form, setForm] = useState<PoeCaptureFormState>(INITIAL_FORM);
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([]);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canManagePoe = WRITE_ROLES.has(user?.role ?? "");

  const loadCaptureData = useCallback(async (profileHint?: StoredUser | null) => {
    setIsLoading(true);
    setError("");

    try {
      const profile = profileHint ?? (await fetchCurrentUser());
      if (profile) {
        setUser(profile);
      }

      const payload = await fetchPoeData();
      setPoeData(payload);

      const bookingParam = Number(new URLSearchParams(window.location.search).get("booking") ?? 0);
      const preferredBooking =
        payload.bookings.find((booking) => booking.id === bookingParam) ??
        payload.bookings[0] ??
        null;

      setForm((current) => ({
        ...current,
        booking: current.booking || preferredBooking?.id || 0,
        executed_on: current.executed_on || new Date().toISOString().slice(0, 10),
      }));
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load field capture.";
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

    void loadCaptureData(storedUser);
  }, [loadCaptureData, router]);

  function updateForm<K extends keyof PoeCaptureFormState>(field: K, value: PoeCaptureFormState[K]) {
    setFormError("");
    setFormSuccess("");
    setFieldErrors({});
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting || !canManagePoe) {
      return;
    }

    setFormError("");
    setFormSuccess("");
    setFieldErrors({});
    setIsSubmitting(true);

    try {
      const capturedAt = new Date().toISOString();
      const result = await createPoeWorkflow({
        record: {
          booking: form.booking,
          executed_on: form.executed_on,
          verification_status: "pending",
          notes: form.notes,
          checked_by: null,
        },
        evidence: evidenceFiles.map((file) => ({
          image: file,
          media_type: form.media_type,
          captured_at: capturedAt,
        })),
      });

      setFormSuccess(`Proof submitted successfully with ${result.evidence.length} evidence item(s).`);
      setEvidenceFiles([]);
      setForm((current) => ({
        ...INITIAL_FORM,
        booking: current.booking,
        executed_on: new Date().toISOString().slice(0, 10),
      }));
      await loadCaptureData(user);
    } catch (submitError) {
      const normalized = getPoeCreateError(submitError);
      setFormError(normalized.message);
      setFieldErrors(normalized.fieldErrors);
      if (normalized.partialSuccess) {
        await loadCaptureData(user);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  if (!canManagePoe && !isLoading && user) {
    return (
      <main className="field-shell">
        <section className="field-panel">
          <div className="field-topbar">
            <div>
              <span className="eyebrow dashboard-eyebrow">Field capture</span>
              <h1 className="workspace-title">Proof capture unavailable</h1>
              <p className="workspace-copy">
                Your current role does not have permission to create proof-of-execution uploads.
              </p>
            </div>
          </div>
          <p className="error">Only operations and admin users can submit field proof.</p>
          <div className="field-actions">
            <Link className="ghost" href="/poe">
              Back to POE
            </Link>
            <button className="ghost" type="button" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="field-shell">
      <section className="field-panel">
        <div className="field-topbar">
          <div>
            <span className="eyebrow dashboard-eyebrow">Field capture</span>
            <h1 className="workspace-title">Installation proof upload</h1>
            <p className="workspace-copy">
              Fast mobile-first capture flow for field teams. Choose the booking, attach photos from the device, and submit the proof back to OMMS.
            </p>
          </div>
          <div className="field-actions">
            <Link className="ghost" href="/poe">
              Back to POE
            </Link>
            <button className="ghost" type="button" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </div>

        {error ? <p className="error">{error}</p> : null}

        <PoeFieldCaptureForm
          bookings={poeData?.bookings ?? []}
          campaigns={poeData?.campaigns ?? []}
          units={poeData?.units ?? []}
          sites={poeData?.sites ?? []}
          form={form}
          evidenceFiles={evidenceFiles}
          fieldErrors={fieldErrors}
          formError={formError}
          formSuccess={formSuccess}
          isLoading={isLoading}
          isSubmitting={isSubmitting}
          submitLabel="Submit field proof"
          headerTitle="Capture executed installation"
          headerCopy="Keep this simple in the field: select the booked location, take the photo, add any note, and submit."
          onSubmit={handleSubmit}
          onChange={updateForm}
          onFilesChange={setEvidenceFiles}
        />
      </section>
    </main>
  );
}
