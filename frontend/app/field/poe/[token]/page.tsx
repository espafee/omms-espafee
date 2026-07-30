"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";

const API_ROOT = (process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

type AssignmentPayload = {
  assignment_id: number;
  status: string;
  submitted: boolean;
  campaign: { id: number; name: string; code: string };
  booking: { id: number; start_date: string; end_date: string };
  unit: { id: number; code: string; dimensions?: string };
  site: { id: number; name: string; address: string; city: string; latitude?: string | null; longitude?: string | null };
  field_executive: string;
};

type SubmitReceipt = { poe_id: number; reference: string; status: string };

export default function PublicFieldPoePage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";
  const endpoint = useMemo(() => `${API_ROOT}/poe/field-upload/${encodeURIComponent(token)}/`, [token]);
  const [assignment, setAssignment] = useState<AssignmentPayload | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [notes, setNotes] = useState("");
  const [latitude, setLatitude] = useState<string>("");
  const [longitude, setLongitude] = useState<string>("");
  const [gpsStatus, setGpsStatus] = useState("Location not captured");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<SubmitReceipt | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await fetch(endpoint, { cache: "no-store" });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail ?? "Unable to open this upload link.");
        if (!cancelled) setAssignment(payload);
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : "Unable to open this upload link.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    if (token) void load();
    return () => { cancelled = true; };
  }, [endpoint, token]);

  function captureLocation() {
    setGpsStatus("Capturing location…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(String(position.coords.latitude));
        setLongitude(String(position.coords.longitude));
        setGpsStatus(`Location captured · accuracy ${Math.round(position.coords.accuracy)} m`);
      },
      () => setGpsStatus("Location permission denied or unavailable"),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!files.length || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const body = new FormData();
      files.forEach((file) => body.append("images", file));
      body.append("executed_on", new Date().toISOString().slice(0, 10));
      body.append("notes", notes);
      if (latitude && longitude) {
        body.append("latitude", latitude);
        body.append("longitude", longitude);
      }
      const response = await fetch(endpoint, { method: "POST", body });
      const payload = await response.json();
      if (!response.ok) {
        const message = payload.detail ?? payload.images?.[0] ?? "Unable to submit POE.";
        throw new Error(message);
      }
      setReceipt(payload);
      setFiles([]);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to submit POE.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <main style={styles.shell}><section style={styles.card}>Loading execution…</section></main>;
  if (error && !assignment) return <main style={styles.shell}><section style={styles.card}><h1>Upload link unavailable</h1><p style={styles.error}>{error}</p></section></main>;
  if (!assignment) return null;
  if (assignment.submitted || receipt) {
    return <main style={styles.shell}><section style={styles.card}><div style={styles.successMark}>✓</div><h1>POE submitted successfully</h1><p>{receipt?.reference ?? "This upload has already been completed."}</p><p style={styles.muted}>The operations team can now review the execution proof.</p></section></main>;
  }

  const mapsUrl = assignment.site.latitude && assignment.site.longitude
    ? `https://www.google.com/maps?q=${assignment.site.latitude},${assignment.site.longitude}`
    : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${assignment.site.name} ${assignment.site.address} ${assignment.site.city}`)}`;

  return (
    <main style={styles.shell}>
      <section style={styles.card}>
        <div style={styles.brand}>OMMS · FIELD EXECUTION</div>
        <h1 style={styles.title}>Upload installation proof</h1>
        <p style={styles.muted}>No login required. This secure link is valid only for this assigned execution.</p>

        <div style={styles.details}>
          <strong>{assignment.campaign.name}</strong>
          <span>{assignment.campaign.code}</span>
          <span>{assignment.site.name}</span>
          <span>{assignment.unit.code}</span>
          <span>{assignment.site.address}, {assignment.site.city}</span>
          <a href={mapsUrl} target="_blank" rel="noreferrer" style={styles.mapButton}>Open in Maps</a>
        </div>

        <form onSubmit={submit} style={styles.form}>
          <label style={styles.label}>Execution photographs *</label>
          <input
            type="file"
            accept="image/*"
            capture="environment"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            style={styles.input}
          />
          <div style={styles.muted}>{files.length ? `${files.length} photo(s) selected` : "Take or select at least one clear photo."}</div>

          <button type="button" onClick={captureLocation} style={styles.secondaryButton}>Capture current location</button>
          <div style={styles.muted}>{gpsStatus}</div>

          <label style={styles.label}>Remarks</label>
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} placeholder="Optional execution note" style={styles.textarea} />

          {error ? <p style={styles.error}>{error}</p> : null}
          <button type="submit" disabled={!files.length || submitting} style={{...styles.primaryButton, opacity: !files.length || submitting ? 0.55 : 1}}>
            {submitting ? "Uploading…" : "Submit POE"}
          </button>
        </form>
      </section>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: { minHeight: "100vh", background: "#f3f7f5", padding: "20px", display: "grid", placeItems: "center", fontFamily: "Arial, sans-serif" },
  card: { width: "100%", maxWidth: 560, background: "white", borderRadius: 24, padding: 24, boxShadow: "0 18px 50px rgba(0,0,0,.08)", color: "#10231d" },
  brand: { fontSize: 12, fontWeight: 800, letterSpacing: 2, color: "#0b6b4f" },
  title: { fontSize: 30, margin: "12px 0 6px" },
  muted: { color: "#60726b", fontSize: 14, lineHeight: 1.5 },
  details: { display: "grid", gap: 8, background: "#f5f9f7", border: "1px solid #dce8e3", borderRadius: 18, padding: 18, margin: "22px 0" },
  mapButton: { display: "inline-block", color: "#0b6b4f", fontWeight: 700, marginTop: 4 },
  form: { display: "grid", gap: 12 },
  label: { fontWeight: 700, marginTop: 6 },
  input: { padding: 14, border: "1px solid #cbdad4", borderRadius: 12, background: "white" },
  textarea: { padding: 14, border: "1px solid #cbdad4", borderRadius: 12, resize: "vertical" },
  primaryButton: { border: 0, borderRadius: 14, padding: "16px 20px", background: "#0b6b4f", color: "white", fontSize: 16, fontWeight: 800, cursor: "pointer" },
  secondaryButton: { border: "1px solid #0b6b4f", borderRadius: 14, padding: "13px 18px", background: "white", color: "#0b6b4f", fontWeight: 700, cursor: "pointer" },
  error: { color: "#a61b1b", background: "#fff0f0", padding: 12, borderRadius: 10 },
  successMark: { width: 64, height: 64, borderRadius: 32, background: "#0b6b4f", color: "white", display: "grid", placeItems: "center", fontSize: 34, marginBottom: 16 },
};
