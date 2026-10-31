"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LiveCase, LiveData, LiveReport } from "@/lib/types";

const ORDER = ["documents", "allergy_card", "labels", "visits", "judge_catches", "judge_plain"];
const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });

function detail(c: LiveCase): string {
  if (c.error) return `error: ${c.error}`;
  if (c.text) return `${c.text.slice(0, 110)}${c.text.length > 110 ? "…" : ""} → ${c.result}`;
  const exp = c.expected?.join(", ") ?? "";
  const got = c.got?.join(", ") ?? "";
  if (c.amlodipine_change !== undefined) return `dose change ${c.amlodipine_change ? "found" : "MISSED"}, chest-pain warning ${c.chest_pain_warning ? "found" : "MISSED"}, follow-up ${c.follow_up ? "found" : "MISSED"}`;
  return `wanted: ${exp || "nothing"} · got: ${got || "nothing"}`;
}

// The live measurements, read from a committed report. Opening this page makes no model call and costs nothing.
export function LiveResults() {
  const [r, setR] = useState<LiveData | null | undefined>(undefined);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { api<LiveReport>("/trust/live").then((d) => setR(d.available ? d : null)).catch(() => setR(null)); }, []);

  if (r === undefined) return <div className="skeleton" style={{ height: 160 }} aria-busy="true" />;
  if (r === null) return null;
  const keys = ORDER.filter((k) => r.sections[k]);
  const total = keys.reduce((n, k) => n + r.sections[k].total, 0);
  const passed = keys.reduce((n, k) => n + r.sections[k].passed, 0);

  return (
    <section aria-labelledby="live-h" className="stack" style={{ marginBottom: 34 }}>
      <div className="section-title"><h2 id="live-h">Measured on the live Meta model</h2><span className="pill pill-blue">{r.reader_model}</span></div>
      <p style={{ color: "var(--ink-2)", maxWidth: "75ch" }}>
        Real calls to Meta’s model on fictional documents, labels and a scripted visit: <b>{passed} of {total}</b> cases passed in the latest run ({when(r.generated_at)}, {r.minutes} min, ${r.cost_usd.toFixed(3)}).
        This page shows a saved report, so opening it never calls the model. Results vary a little between runs; earlier runs are listed below.
      </p>
      <div className="stats" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }}>
        {keys.map((k) => {
          const s = r.sections[k];
          const all = s.passed === s.total;
          return (
            <button key={k} className="stat" style={{ textAlign: "left", cursor: "pointer", font: "inherit", color: "inherit", background: "transparent", border: 0 }} aria-expanded={open === k} onClick={() => setOpen(open === k ? null : k)}>
              <p className="stat-n" style={{ color: all ? undefined : "var(--gold)", fontSize: "clamp(34px, 4vw, 54px)", whiteSpace: "nowrap" }}>{s.passed}<small style={{ fontSize: "0.5em", color: "var(--ink-3)" }}> / {s.total}</small></p>
              <p>{s.title}</p>
              <small style={{ color: "var(--ink-3)" }}>{all ? "Show the cases" : `${s.total - s.passed} did not pass. Show them`}</small>
            </button>
          );
        })}
      </div>

      {open && r.sections[open] && (
        <article className="card item">
          <div className="item-top"><div><h3>{r.sections[open].title}</h3><p className="detail" style={{ marginTop: 4 }}>{r.sections[open].what}</p></div>
            <span className={r.sections[open].passed === r.sections[open].total ? "pill pill-leaf" : "pill pill-amber"}>{r.sections[open].passed} / {r.sections[open].total}</span></div>
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 8 }}>
            {[...r.sections[open].cases].sort((a, b) => Number(a.ok) - Number(b.ok)).map((c, i) => (
              <li key={`${c.id ?? c.text}-${i}`} style={{ fontFamily: "var(--font-mono)", fontSize: 13, padding: "10px 12px", borderRadius: 12,
                  border: `1px solid ${c.ok ? "var(--line-soft)" : "var(--gold)"}`, background: c.ok ? "rgba(255,255,255,.04)" : "rgba(255,185,56,.10)" }}>
                <b style={{ color: c.ok ? "var(--signal)" : "var(--gold)" }}>{c.ok ? "pass" : "FAIL"}</b> {c.id ? `${c.id} · ` : ""}{detail(c)}{c.note ? <div style={{ fontFamily: "var(--font-body)", marginTop: 6 }}>{c.note}</div> : null}
              </li>
            ))}
          </ul>
        </article>
      )}

      {r.speech && (
        <article className="card item" aria-labelledby="speech-h">
          <div className="item-top"><div><h3 id="speech-h">Hearing Hindi and Marathi voices</h3>
            <p className="detail" style={{ marginTop: 4 }}>{r.speech.what} {r.speech.dataset}. Word error rate: lower is better.</p></div>
            <span className="pill pill-blue">{r.speech.model}</span></div>
          <div className="stats" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))" }}>
            {Object.entries(r.speech.languages).map(([k, l]) => {
              const a = l.without_language_hint.wer, b = l.with_language_hint.wer;
              const pct = (x: number | null) => (x === null ? "n/a" : `${Math.round(x * 100)}%`);
              return (
                <div key={k} className="stat">
                  <p className="stat-n" style={{ fontSize: "clamp(34px, 4vw, 54px)", whiteSpace: "nowrap", color: (b ?? 1) > 0.2 ? "var(--gold)" : undefined }}>{pct(b)}</p>
                  <p>{l.language}, with the language told to the model</p>
                  <small style={{ color: "var(--ink-3)" }}>{pct(a)} when the language is not told · {l.clips} clips, characters wrong: {pct(l.with_language_hint.cer)}</small>
                </div>
              );
            })}
          </div>
          <p style={{ color: "var(--ink-2)" }}>The app sends the visit’s language, which the family chooses before recording. Marathi is clearly weaker than Hindi: about one word in four is still wrong, so treat Marathi speech as experimental.</p>
          <details>
            <summary style={{ cursor: "pointer", fontWeight: 700 }}>Show examples (Marathi)</summary>
            <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
              {(r.speech.languages["mr_in"]?.cases ?? []).slice(0, 4).map((c) => (
                <div key={c.id} style={{ fontSize: 14, padding: "10px 12px", borderRadius: 12, border: "1px solid var(--line-soft)", background: "rgba(255,255,255,.04)" }}>
                  <div><b>Said</b> {c.reference}</div><div><b>Heard</b> {c.hint?.heard} <span style={{ color: "var(--ink-3)" }}>({c.hint?.word_errors} of {c.hint?.words} words wrong)</span></div>
                </div>))}
            </div>
          </details>
        </article>
      )}

      {r.history.length > 0 && (
        <details className="card card-pad">
          <summary style={{ cursor: "pointer", fontWeight: 700 }}>Earlier runs ({r.history.length})</summary>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", marginTop: 10, fontSize: 14 }}>
              <thead><tr><th style={{ textAlign: "left", padding: "4px 12px 4px 0" }}>Run</th>{keys.map((k) => <th key={k} style={{ textAlign: "left", padding: "4px 12px" }}>{r.sections[k].title.split(" ").slice(0, 3).join(" ")}</th>)}</tr></thead>
              <tbody>{r.history.map((h) => (
                <tr key={h.generated_at}><td style={{ padding: "4px 12px 4px 0" }}>{when(h.generated_at)}</td>{keys.map((k) => <td key={k} style={{ padding: "4px 12px" }}>{h.sections[k] ? `${h.sections[k][0]} / ${h.sections[k][1]}` : "n/a"}</td>)}</tr>))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      <div className="card card-pad" style={{ borderColor: "var(--gold)" }}>
        <p className="eyebrow">Not measured yet</p>
        <ul style={{ margin: "8px 0 0", paddingLeft: 20, display: "grid", gap: 4 }}>{r.not_measured.map((x) => <li key={x}>{x}</li>)}</ul>
      </div>
    </section>
  );
}
