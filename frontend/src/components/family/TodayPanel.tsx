"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { TodayView, WellbeingHistory } from "@/lib/types";
import { Icon } from "../Icon";

const STATUS: Record<string, { label: string; cls: string }> = {
  later: { label: "Later today", cls: "pill" }, due: { label: "Due now", cls: "pill pill-amber" }, not_marked: { label: "Not marked yet", cls: "pill pill-amber" },
  taken: { label: "Taken", cls: "pill pill-leaf" }, not_taken: { label: "Marked not taken", cls: "pill pill-rose" },
};
const day = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

// Today: what was marked as taken, and what the patient says about how they feel. Counts and entries only; nothing is interpreted.
export function TodayPanel({ patientId, toast, onChange }: { patientId: string; toast: (m: string) => void; onChange: () => void }) {
  const [v, setV] = useState<TodayView | null>(null);
  const [h, setH] = useState<WellbeingHistory | null>(null);
  const [pain, setPain] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const load = useCallback(async () => {
    try {
      setV(await api<TodayView>(`/patients/${patientId}/today`));
      setH(await api<WellbeingHistory>(`/patients/${patientId}/wellbeing?days=14`));
    } catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not load today"); }
  }, [patientId, toast]);
  useEffect(() => { load(); const id = setInterval(load, 30000); return () => clearInterval(id); }, [load]);

  async function mark(item_key: string, slot: string, status: "taken" | "not_taken") {
    try { await api(`/patients/${patientId}/doses`, { method: "POST", json: { item_key, slot, status } }); toast(status === "taken" ? "Marked as taken, with your name." : "Marked as not taken. Ask the doctor or pharmacist what to do."); await load(); onChange(); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not save"); }
  }
  async function saveWell() {
    try { await api(`/patients/${patientId}/wellbeing`, { method: "POST", json: { ...(pain !== null ? { pain } : {}), ...(note.trim() ? { note: note.trim() } : {}) } }); setPain(null); setNote(""); toast("Saved."); await load(); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not save"); }
  }

  if (!v) return <div className="skeleton" style={{ height: 220 }} aria-busy="true" />;
  const s = v.summary;
  const total = s.taken + s.not_taken + s.due + s.not_marked + s.later;
  return (
    <div className="stack">
      <div className="section-title"><h2>Today</h2><span className="pill">{v.date} · {v.now}</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        What was marked as taken today, from the confirmed plan. {v.last_activity ? <>Last marked: <b>{v.last_activity}</b>.</> : <>Nothing has been marked yet today.</>}
      </p>
      <div className="stats" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}>
        <div className="stat"><p className="stat-n">{s.taken}<small style={{ fontSize: "0.5em", color: "var(--ink-3)" }}> / {total}</small></p><p>marked as taken</p></div>
        <div className="stat"><p className="stat-n" style={{ color: s.not_marked ? "var(--gold)" : undefined }}>{s.not_marked + s.due}</p><p>not marked yet</p></div>
        <div className="stat"><p className="stat-n" style={{ color: s.not_taken ? "var(--coral)" : undefined }}>{s.not_taken}</p><p>marked not taken</p></div>
      </div>

      {v.slots.length === 0 && <p className="card card-pad">No confirmed medicine with a plain schedule is due today. Confirm the plan first (Care plan tab). Medicines held by an open allergy flag, and “if pain” medicines, are not shown.</p>}
      {v.slots.map((sl) => (
        <article key={sl.slot} className="card item">
          <div className="item-top"><h3>{sl.label} <small style={{ color: "var(--ink-3)" }}>{sl.time}</small></h3></div>
          {sl.items.map((it) => (
            <div key={it.item_key} className="item-foot" style={{ justifyContent: "space-between" }}>
              <span><b>{it.title}</b> × {it.units}<br /><small style={{ color: "var(--ink-3)" }}>{it.how}</small></span>
              <span className="item-foot" style={{ gap: 6 }}>
                <span className={STATUS[it.status].cls}>{STATUS[it.status].label}{it.marked_at ? ` ${it.marked_at}` : ""}{it.marked_by ? ` · ${it.marked_by}` : ""}</span>
                {it.status !== "taken" && <button className="btn btn-quiet btn-sm" onClick={() => mark(it.item_key, sl.slot, "taken")}><Icon name="check" /> Mark taken</button>}
                {it.status !== "not_taken" && it.status !== "taken" && <button className="btn btn-quiet btn-sm" onClick={() => mark(it.item_key, sl.slot, "not_taken")}>Not taken</button>}
              </span>
            </div>
          ))}
        </article>
      ))}
      <p style={{ color: "var(--ink-3)", fontSize: 14 }}>{v.note}</p>

      <div className="section-title"><h2>How they say they feel</h2><span className="pill">{h ? `${h.days_with_entry} of the last ${h.days} days` : ""}</span></div>
      <article className="card item">
        {h && h.entries.length === 0 && <p>No entries yet. The patient can tap a number in Elder mode, or you can add one after a phone call.</p>}
        {h && h.entries.length > 0 && (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {h.entries.map((e) => (
              <li key={e.date} style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
                <span style={{ minWidth: 64, color: "var(--ink-3)" }}>{day(e.date)}</span>
                {e.pain !== null && <span className="pill" style={{ fontSize: 16 }}>pain {e.pain} of 10</span>}
                {e.note && <span>“{e.note}”</span>}
                <small style={{ color: "var(--ink-3)" }}>{e.by}</small>
              </li>
            ))}
          </ul>
        )}
        {h && <p style={{ color: "var(--ink-3)", fontSize: 14 }}>{h.note}</p>}
        <div className="stack" style={{ borderTop: "1px solid var(--line-soft)", paddingTop: 12 }}>
          <p className="eyebrow">Add today’s entry, for example after a call</p>
          <div role="group" aria-label="Pain number" style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {Array.from({ length: 11 }, (_, n) => <button key={n} className={pain === n ? "btn btn-primary btn-sm" : "btn btn-quiet btn-sm"} aria-pressed={pain === n} onClick={() => setPain(pain === n ? null : n)}>{n}</button>)}
          </div>
          <label htmlFor="well-note" className="eyebrow">In their words (optional)</label>
          <input id="well-note" className="input" maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Slept badly, back felt stiff in the morning" />
          <div className="item-foot"><button className="btn btn-primary btn-sm" disabled={pain === null && !note.trim()} onClick={saveWell}>Save entry</button></div>
        </div>
      </article>
    </div>
  );
}
