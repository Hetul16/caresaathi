"use client";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { MedicineTimeline as TL, TimelineRow } from "@/lib/types";
import { Icon } from "../Icon";
import { SourceChip } from "../Source";

const DAY = 86400000;
const t = (iso: string) => new Date(iso + "T00:00:00").getTime();
const short = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

// Every current medicine on one calendar. Dates are the ones printed on the documents, added up by code; a medicine with no printed date is listed, not drawn.
// Where two medicines share an ingredient and both are running, that stretch is striped. An open allergy flag is marked on the bar. Nothing here says what to do.
export function MedicineTimeline({ patientId, toast }: { patientId: string; toast: (m: string) => void }) {
  const [tl, setTl] = useState<TL | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  useEffect(() => {
    api<TL>(`/patients/${patientId}/medicine-timeline`).then(setTl).catch((e) => toast(e instanceof ApiError ? e.detail || e.title : "Could not load the timeline"));
  }, [patientId, toast]);

  const view = useMemo(() => {
    if (!tl) return null;
    const lo = t(tl.window.start), hi = t(tl.window.end), span = Math.max(hi - lo, DAY);
    const pct = (iso: string) => ((t(iso) - lo) / span) * 100;
    const step = span / DAY <= 40 ? 7 : span / DAY <= 120 ? 14 : 30;
    const ticks: string[] = [];
    for (let d = lo; d <= hi; d += step * DAY) { const iso = new Date(d).toISOString().slice(0, 10); if (((d - lo) / span) * 100 > 4) ticks.push(iso); }
    // rows that share an ingredient sit next to each other, so the striped stretch can be read across them
    const drawn = tl.rows.filter((r) => r.start);
    const order: TimelineRow[] = [];
    const seen = new Set<string>();
    for (const r of drawn) {
      if (seen.has(r.item_key)) continue;
      const g = tl.overlaps.find((o) => o.keys.includes(r.item_key));
      for (const k of g ? g.keys : [r.item_key]) { const x = drawn.find((y) => y.item_key === k); if (x && !seen.has(k)) { seen.add(k); order.push(x); } }
    }
    return { pct, ticks, order, undrawn: tl.rows.filter((r) => !r.start), today: pct(tl.today) };
  }, [tl]);

  if (!tl || !view) return <div className="skeleton" style={{ height: 260 }} aria-busy="true" />;
  const sel = tl.rows.find((r) => r.item_key === picked) ?? null;
  const spotsFor = (key: string) => tl.overlaps.flatMap((o) => o.spots.filter((s) => s.a === key || s.b === key).map((s) => ({ ...s, ingredient: o.ingredient })));
  const copy = async (q: string) => { try { await navigator.clipboard.writeText(q); toast("Question copied. Take it to the doctor or pharmacist."); } catch { toast("Could not copy."); } };

  return (
    <div className="stack">
      <div className="section-title"><h2>Medicine timeline</h2><span className="pill">{tl.rows.length} medicine{tl.rows.length === 1 ? "" : "s"} · dates as printed</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        Every medicine from every doctor on one calendar. Each bar starts on the date printed on its document and runs for the days printed on its line. A striped stretch is where two
        medicines with the same ingredient are both running. A red mark is an open allergy flag. Tap a bar to see the sum and the page it came from.
      </p>

      {view.order.length === 0 ? <p className="card card-pad">No medicine has a printed date yet, so nothing can be drawn. Upload a prescription that shows its date.</p> : (
        <div className="card card-pad tl-scroll">
          <div className="tl" role="group" aria-label="Medicine timeline">
            <div className="tl-axis" aria-hidden>
              {view.ticks.map((d) => <span key={d} style={{ left: `${view.pct(d)}%` }}>{short(d)}</span>)}
            </div>
            {view.order.map((r) => {
              const left = view.pct(r.start!);
              const right = r.end ? view.pct(r.end) + 100 / ((t(tl.window.end) - t(tl.window.start)) / DAY) : 100;
              const flagged = !!r.allergy;
              const width = Math.max(right - left, 1.5);
              const narrow = width < 22 && right < 78;           // too short to hold its dates: they sit to the right of the bar
              const text = r.end ? `${short(r.start!)} – ${short(r.end)}` : `from ${short(r.start!)}, no end given`;
              return (
                <div key={r.item_key} className="tl-row">
                  <div className="tl-name"><b>{r.title}</b><small>{r.prescriber}</small></div>
                  <div className="tl-track">
                    {view.ticks.map((d) => <i key={d} className="tl-grid" style={{ left: `${view.pct(d)}%` }} />)}
                    <button className={`tl-bar${r.confirmed ? " on" : ""}${flagged ? " flag" : ""}${r.open_end ? " open" : ""}${picked === r.item_key ? " picked" : ""}`}
                      style={{ left: `${left}%`, width: `${width}%` }} onClick={() => setPicked(picked === r.item_key ? null : r.item_key)}
                      aria-pressed={picked === r.item_key}
                      aria-label={`${r.title}, ${short(r.start!)} to ${r.end ? short(r.end) : "no end date given"}${flagged ? ", open allergy flag" : ""}${r.confirmed ? "" : ", not confirmed yet"}`}>
                      {flagged && <span className="tl-warn" aria-hidden>!</span>}
                      {!narrow && <span className="tl-label">{text}</span>}
                    </button>
                    {narrow && <span className="tl-label out" style={{ left: `calc(${left + width}% + 8px)` }} aria-hidden>{text}</span>}
                    {spotsFor(r.item_key).map((s, i) => {
                      const a = view.pct(s.start), b = s.end ? view.pct(s.end) + 100 / ((t(tl.window.end) - t(tl.window.start)) / DAY) : 100;
                      return <span key={i} className="tl-overlap" title={`${s.ingredient} on both`} style={{ left: `${a}%`, width: `${Math.max(b - a, 1.5)}%` }} aria-hidden />;
                    })}
                  </div>
                </div>
              );
            })}
            <div className="tl-today" style={{ left: `calc(var(--tl-name) + (100% - var(--tl-name)) * ${view.today / 100})` }} aria-hidden><span>Today</span></div>
          </div>
          <div className="tl-key" aria-hidden>
            <span><i className="k on" /> confirmed</span><span><i className="k" /> not confirmed yet</span><span><i className="k open" /> no end date printed</span>
            <span><i className="k stripe" /> same ingredient, both running</span><span><i className="k flag" /> open allergy flag</span>
          </div>
        </div>
      )}

      {sel && (
        <article className="card item" aria-live="polite">
          <div className="item-top"><div><p className="eyebrow">{sel.prescriber}</p><h3 style={{ marginTop: 4 }}>{sel.title}{sel.detail ? `, ${sel.detail}` : ""}</h3></div>
            <span className={sel.confirmed ? "pill pill-leaf" : "pill pill-amber"}>{sel.confirmed ? "Confirmed" : "Not confirmed yet"}</span></div>
          <p style={{ color: "var(--ink-2)" }}>{sel.how}</p>
          {sel.allergy && <div className="question-box fail-box" role="alert">{sel.allergy.flag}</div>}
          <div className="item-foot"><SourceChip source={sel.source} /></div>
        </article>
      )}

      {tl.overlaps.map((o) => (
        <article key={o.ingredient} className="card item">
          <div className="item-top"><h3>Same ingredient: {o.ingredient}</h3><span className={o.dated ? "pill pill-amber" : "pill"}>{o.dated ? "running together" : "dates not known"}</span></div>
          <p>{o.medicines.join(" and ")}.{" "}
            {o.dated ? o.spots.map((s) => `Both running ${short(s.start)}${s.end ? ` to ${short(s.end)}` : ", with no end date printed"}.`).join(" ")
              : "At least one has no printed date, so the overlap cannot be drawn."}</p>
          <div className="question-box">{o.question}
            <div className="item-foot" style={{ marginTop: 8 }}><button className="btn btn-quiet btn-sm" onClick={() => copy(o.question)}><Icon name="copy" /> Copy the question</button></div>
          </div>
        </article>
      ))}

      {view.undrawn.length > 0 && (
        <article className="card item">
          <div className="item-top"><h3>Not drawn: no date printed</h3><span className="pill">{view.undrawn.length}</span></div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>{view.undrawn.map((r) => <li key={r.item_key}><b>{r.title}</b> <small style={{ color: "var(--ink-3)" }}>{r.prescriber}</small> <SourceChip source={r.source} short /></li>)}</ul>
          <p style={{ color: "var(--ink-3)", fontSize: 14 }}>A date is never guessed. Ask for a dated prescription, or add the date when you confirm the item.</p>
        </article>
      )}
      <p style={{ color: "var(--ink-3)", fontSize: 14 }}>{tl.note}</p>
    </div>
  );
}
