"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { FollowUp, MedicineHistory, SupplyRow } from "@/lib/types";
import { Icon } from "../Icon";
import { SourceChip } from "../Source";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const errText = (e: unknown) => (e instanceof ApiError ? e.detail || e.title : "Something went wrong. Please try again.");

// Follow-ups, refill estimates and medicine history. Every date and quantity below is computed by code from what the documents or the
// doctor said, and the inputs are shown beside it. A named person confirms each one. Nothing here says when to refill or review.
export function TrackerPanel({ patientId, canApprove, toast, onChange }: { patientId: string; canApprove: boolean; toast: (m: string) => void; onChange: () => void }) {
  const [fu, setFu] = useState<FollowUp[] | null>(null);
  const [supply, setSupply] = useState<SupplyRow[] | null>(null);
  const [hist, setHist] = useState<MedicineHistory[] | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, b, c] = await Promise.all([api<FollowUp[]>(`/patients/${patientId}/follow-ups`), api<SupplyRow[]>(`/patients/${patientId}/supply`), api<MedicineHistory[]>(`/patients/${patientId}/medicine-history`)]);
      setFu(a); setSupply(b); setHist(c);
    } catch (e) { toast(errText(e)); }
  }, [patientId, toast]);
  useEffect(() => { load(); }, [load]);

  async function decide(id: string, action: "confirm" | "done" | "dismiss") {
    try { await api(`/follow-ups/${id}/decision`, { method: "POST", json: { action } }); toast(action === "confirm" ? "Confirmed. A reminder was set for the morning of that day." : action === "done" ? "Marked done." : "Set aside."); load(); onChange(); }
    catch (e) { toast(errText(e)); }
  }
  async function confirmSupply(id: string) {
    try { await api(`/supply/${id}/confirm`, { method: "POST" }); toast("Confirmed by you."); load(); } catch (e) { toast(errText(e)); }
  }

  if (!fu || !supply || !hist) return <div className="skeleton" style={{ height: 220 }} aria-busy="true" />;
  return (
    <div className="stack">
      <div className="section-title"><h2>Follow-ups</h2><span className="pill">{fu.filter((f) => f.status === "pending").length} to confirm</span></div>
      <p style={{ color: "var(--ink-2)" }}>CareSaathi found these words in the documents and visits. The date is counted by code from the date shown, never guessed. Please check each one.</p>
      {fu.length === 0 && <p className="card card-pad">No follow-ups yet.</p>}
      {fu.map((f) => (
        <article key={f.id} className="card item" style={f.status === "done" ? { opacity: 0.6 } : undefined}>
          <div className="item-top">
            <div>
              <h3>{f.what}</h3>
              <p className="detail" style={{ fontSize: 26, fontFamily: "var(--font-display)", fontWeight: 700, marginTop: 4 }}>{f.due_date ? day(f.due_date) : "No date"}</p>
            </div>
            <span className={f.status === "pending" ? "pill pill-marigold" : f.status === "confirmed" ? "pill pill-leaf" : "pill"}>
              {f.status === "pending" ? "To confirm" : f.status === "confirmed" ? `Confirmed${f.acted_by ? ` by ${f.acted_by}` : ""}` : "Done"}
            </span>
          </div>
          <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}><Icon name="clock" /> {f.how}</p>
          <div className="item-foot">
            <SourceChip source={f.source} />
            {f.status === "pending" && canApprove && <button className="btn btn-leaf btn-sm" onClick={() => decide(f.id, "confirm")}><Icon name="check" /> Confirm</button>}
            {f.status === "confirmed" && <button className="btn btn-quiet btn-sm" onClick={() => decide(f.id, "done")}>Mark done</button>}
            {(f.status === "pending" || f.status === "confirmed") && <button className="btn btn-quiet btn-sm" onClick={() => decide(f.id, "dismiss")}>Set aside</button>}
          </div>
        </article>
      ))}

      <div className="section-title"><h2>When a supply may run out</h2><span className="pill">{supply.length}</span></div>
      <p style={{ color: "var(--ink-2)" }}>Only where a quantity is written. It is counted from the start date shown, using the written daily schedule, and it is an estimate to check against the real packet. CareSaathi does not say when to refill.</p>
      {supply.length === 0 && <p className="card card-pad">No quantities were written in the documents yet.</p>}
      {supply.map((r) => (
        <article key={r.id} className="card item">
          <div className="item-top"><div><h3>{r.medicine}</h3>
            <p className="detail" style={{ fontSize: 24, fontFamily: "var(--font-display)", fontWeight: 700, marginTop: 4 }}>{r.estimated_run_out ? `about ${day(r.estimated_run_out)}` : "No estimate"}</p></div>
            {r.confirmed_by ? <span className="pill pill-leaf">Checked by {r.confirmed_by}</span> : <span className="pill pill-marigold">Not checked yet</span>}</div>
          <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>{r.how}</p>
          <div className="item-foot">{r.source && <SourceChip source={r.source} />}
            {!r.confirmed_by && canApprove && <button className="btn btn-leaf btn-sm" onClick={() => confirmSupply(r.id)}><Icon name="check" /> This matches the packet</button>}</div>
        </article>
      ))}

      <div className="section-title"><h2>Medicine history</h2><span className="pill">{hist.length}</span></div>
      <p style={{ color: "var(--ink-2)" }}>Every version of every medicine, with the line or the words it came from. Nothing is overwritten.</p>
      {hist.length === 0 && <p className="card card-pad">No medicines yet.</p>}
      {hist.map((m) => (
        <article key={m.item_key} className="card item">
          <button className="item-top" style={{ background: "none", border: 0, padding: 0, cursor: "pointer", textAlign: "left", color: "inherit" }}
            aria-expanded={openKey === m.item_key} onClick={() => setOpenKey(openKey === m.item_key ? null : m.item_key)}>
            <h3>{m.title}</h3><span className="pill">{m.versions.length} version{m.versions.length === 1 ? "" : "s"} {openKey === m.item_key ? "▴" : "▾"}</span>
          </button>
          {openKey === m.item_key && (
            <ol className="timeline" style={{ listStyle: "none", margin: "8px 0 0", paddingLeft: 26 }}>
              {[...m.versions].reverse().map((v) => (
                <li key={v.version} className={`tl ${v.current ? "" : "visit"}`}>
                  <time dateTime={v.at}>Version {v.version} · {new Date(v.at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}{v.current ? " · current" : ""}</time>
                  <p><strong>{v.title}</strong>{v.detail ? `, ${v.detail}` : ""}{v.status === "stopped" ? " (stopped)" : ""}</p>
                  <div className="item-foot" style={{ marginTop: 6 }}><SourceChip source={v.source} />{v.confirmed_by && <span style={{ color: "var(--ink-3)", fontSize: 14 }}>Confirmed by {v.confirmed_by}</span>}</div>
                </li>
              ))}
            </ol>
          )}
        </article>
      ))}
    </div>
  );
}
