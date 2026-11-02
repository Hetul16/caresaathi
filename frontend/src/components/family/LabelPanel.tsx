"use client";
import { useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { LabelResult } from "@/lib/types";
import { Icon } from "../Icon";
import { SourceChip } from "../Source";

const VERDICT: Record<string, { label: string; cls: string }> = {
  matches: { label: "Found in your documents", cls: "pill pill-leaf" },
  different_strength: { label: "Strength differs from the documents", cls: "pill pill-amber" },
  not_in_plan: { label: "Not in your documents", cls: "pill pill-amber" },
  could_not_read: { label: "Could not read", cls: "pill pill-rose" },
};

// Label check: a photo of PRINTED packaging. It reads text and compares it with the documents; it cannot tell what a loose pill is.
export function LabelPanel({ patientId, toast }: { patientId: string; toast: (m: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<LabelResult | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  async function pick(file: File | undefined) {
    if (!file) return;
    setBusy(true); setRes(null);
    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    try {
      const fd = new FormData(); fd.append("file", file);
      setRes(await api<LabelResult>(`/patients/${patientId}/label-check`, { method: "POST", body: fd }));
    } catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not read that photo"); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  }
  async function copy(q: string) { try { await navigator.clipboard.writeText(q); toast("Question copied. Take it to the pharmacist."); } catch { toast("Could not copy."); } }

  return (
    <div className="stack">
      <div className="section-title"><h2>Label check</h2><span className="pill">Reads printed text only</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        Hold a strip, box, bottle or tube up to the camera. CareSaathi reads the words printed on it and compares them with your documents and the allergies on file.
        It cannot tell what a loose pill or an unmarked tube is from how it looks, and it never says whether a medicine is right or safe.
      </p>
      <div className="card card-pad stack">
        <input ref={input} id="label-file" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden onChange={(e) => pick(e.target.files?.[0])} />
        <div className="item-foot">
          <button className="btn btn-primary" disabled={busy} onClick={() => input.current?.click()}><Icon name="pill" /> {busy ? "Reading the label…" : "Take or choose a photo"}</button>
          <span style={{ color: "var(--ink-3)" }}>The photo is read once and not stored.</span>
        </div>
        {preview && (
          // A data: URL straight from the camera, shown once and never stored: next/image has nothing to optimise here.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="The photo you chose" style={{ maxWidth: 360, width: "100%", borderRadius: 14, border: "1px solid var(--line)" }} />
        )}
      </div>

      {res?.products.map((p, i) => {
        const v = VERDICT[p.verdict] ?? VERDICT.could_not_read;
        return (
          <article key={i} className="card item" aria-live="polite">
            <div className="item-top">
              <div>
                <p className="eyebrow">{[p.brand, ...p.ingredients.map((x) => `${x.name}${x.strength ? ` ${x.strength}` : ""}`)].filter(Boolean).join(" · ") || "On the label"}</p>
                <h3 style={{ marginTop: 4 }}>{p.text}</h3>
              </div>
              <span className={v.cls}>{v.label}</span>
            </div>
            {(p.expiry || p.batch) && <p style={{ color: "var(--ink-2)" }}>Printed: {[p.batch && `batch ${p.batch}`, p.expiry && `expiry ${p.expiry}`].filter(Boolean).join(", ")}. CareSaathi does not judge dates.</p>}
            {p.plan_item && <p>In your documents: <b>{p.plan_item.title}</b>{p.plan_item.detail ? `, ${p.plan_item.detail}` : ""} <SourceChip source={p.plan_item.source} short /></p>}
            {p.allergy.map((a, j) => (
              <div key={j} className="question-box fail-box" role="alert">
                {a.text}{a.source && <> <SourceChip source={a.source} short /></>}
              </div>
            ))}
            {p.question && (
              <div className="question-box">{p.question}
                <div className="item-foot" style={{ marginTop: 8 }}><button className="btn btn-quiet btn-sm" onClick={() => copy(p.question!)}><Icon name="copy" /> Copy the question</button></div>
              </div>
            )}
          </article>
        );
      })}
      {res && <p style={{ color: "var(--ink-3)", fontSize: 14 }}>{res.note}{res.dropped_unprinted > 0 ? ` ${res.dropped_unprinted} detail${res.dropped_unprinted === 1 ? " was" : "s were"} left out because it was not printed on the label.` : ""}</p>}
    </div>
  );
}
