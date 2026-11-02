"use client";
import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { Icon } from "../Icon";
import { afterCommit } from "@/lib/defer";

interface Doc { id: string; doc_type: string; status: string; original_filename: string | null; page_count: number | null; created_at: string }

const STATUS: Record<string, { label: string; cls: string }> = {
  uploaded: { label: "Waiting to be read", cls: "pill" },
  processing: { label: "Reading…", cls: "pill pill-blue" },
  extracted: { label: "Added to the plan", cls: "pill pill-leaf" },
  needs_review: { label: "Some lines need a check", cls: "pill pill-amber" },
  failed: { label: "Could not be read", cls: "pill pill-rose" },
};
const TYPES = [["other", "Not sure"], ["prescription", "Prescription"], ["discharge_summary", "Discharge summary"], ["lab_report", "Lab report"], ["specialist_letter", "Specialist letter"], ["imaging_report", "Imaging report"]];

export function UploadPanel({ patientId, onProcessed }: { patientId: string; onProcessed: () => void }) {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [type, setType] = useState("other");
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const prevBusy = useRef(false);

  const load = useCallback(async () => {
    try { setDocs(await api<Doc[]>(`/patients/${patientId}/documents`)); } catch { /* shown by empty state */ }
  }, [patientId]);

  useEffect(() => { afterCommit(load); }, [load]);

  // Poll while anything is still being read, then refresh the care plan once it settles.
  const inFlight = docs?.some((d) => d.status === "uploaded" || d.status === "processing") ?? false;
  useEffect(() => {
    if (!inFlight) { if (prevBusy.current) onProcessed(); prevBusy.current = false; return; }
    prevBusy.current = true;
    const id = setInterval(load, 1800);
    return () => clearInterval(id);
  }, [inFlight, load, onProcessed]);

  async function send(files: FileList | File[]) {
    setError("");
    setBusy(true);
    try {
      for (const f of Array.from(files)) {
        const fd = new FormData();
        fd.append("file", f);
        fd.append("doc_type", type);
        await api(`/patients/${patientId}/documents`, { method: "POST", body: fd });
      }
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.title}${e.detail ? `. ${e.detail}` : ""}` : "Upload failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) send(e.dataTransfer.files); };

  return (
    <div className="stack">
      <div className="section-title"><h2>Documents</h2></div>
      <div
        className={`drop ${over ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <span className="empty-ic"><Icon name="file" /></span>
        <h3>Drop a prescription, report or discharge summary</h3>
        <p>JPEG, PNG or PDF. Every line CareSaathi adds will point back to its exact text.</p>
        <div className="drop-row">
          <label className="select">
            <span className="sr-only">Document type</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          <button className="btn btn-primary" onClick={() => input.current?.click()} disabled={busy}>{busy ? "Uploading…" : "Choose files"}</button>
          <input ref={input} type="file" hidden multiple accept="image/jpeg,image/png,application/pdf" onChange={(e) => e.target.files && send(e.target.files)} />
        </div>
      </div>
      {error && <div className="form-error" role="alert"><Icon name="alert" /> {error}</div>}

      {docs === null && <div className="card card-pad skeleton" aria-busy="true" aria-label="Loading documents" style={{ height: 76 }} />}
      {docs?.length === 0 && <p className="card card-pad">No documents yet.</p>}
      {docs?.map((d) => {
        const st = STATUS[d.status] ?? STATUS.uploaded;
        return (
          <article key={d.id} className="card item">
            <div className="item-top">
              <div style={{ display: "flex", gap: 12 }}>
                <span className="kind-ic"><Icon name="file" /></span>
                <div>
                  <h3>{d.original_filename || "Document"}</h3>
                  <p className="detail">{d.doc_type.replace("_", " ")}{d.page_count ? ` · ${d.page_count} page${d.page_count > 1 ? "s" : ""}` : ""}</p>
                </div>
              </div>
              <span className={st.cls}>{st.label}</span>
            </div>
          </article>
        );
      })}
    </div>
  );
}
