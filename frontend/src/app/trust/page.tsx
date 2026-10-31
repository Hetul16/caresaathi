"use client";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Icon } from "@/components/Icon";
import { LiveResults } from "@/components/LiveResults";
import type { TrustRun } from "@/lib/types";

const NICE: Record<string, string> = {
  guard_blocks_unsafe_output: "Unsafe wording is blocked", guard_passes_plain_output: "Plain read-backs are not blocked", guard_structure: "Unsourced or ungrounded drafts are blocked",
  permission_gate: "The permission gate", prompt_injection: "Prompt injection", chat_refusals: "Chat refusals", follow_up_dates: "Follow-up dates",
  omission_logic: "Omission logic", refill_math: "Refill arithmetic", guard_paraphrase_probe: "Paraphrase probe (tuned)", guard_paraphrase_holdout: "Paraphrase probe (held out)",
  extraction_offline: "Offline reader against ground truth",
};

// Public: anyone can see what was tested, what passed, and exactly what did not.
export default function Trust() {
  const { status } = useAuth();
  const [run, setRun] = useState<TrustRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => { api<TrustRun>("/trust/latest").then(setRun).catch(() => setError("Could not load the results.")); }, []);
  async function again() {
    setBusy(true);
    try { setRun(await api<TrustRun>("/trust/run", { method: "POST" })); } catch (e) { setError(e instanceof ApiError ? e.detail || e.title : "Could not run the checks."); } finally { setBusy(false); }
  }

  if (error && !run) return <div className="center-page"><p>{error}</p></div>;
  if (!run) return <div className="wrap" style={{ padding: "40px 0" }}><div className="skeleton" style={{ height: 300 }} aria-busy="true" /></div>;
  const failed = run.total - run.passed;
  return (
    <div className="wrap" style={{ padding: "40px 0 90px" }}>
      <p className="eyebrow">Trust panel</p>
      <h1 style={{ fontSize: "clamp(36px, 5.5vw, 68px)", margin: "10px 0 14px", maxWidth: "20ch" }}>What was tested, and what was not caught.</h1>
      <p style={{ color: "var(--ink-2)", maxWidth: "70ch", fontSize: 18 }}>{run.disclaimer}</p>

      <div className="stats" style={{ margin: "30px 0" }}>
        <div className="stat"><p className="stat-n grad">{run.passed}</p><p>of {run.total} cases passed</p></div>
        <div className="stat"><p className="stat-n" style={{ color: failed ? "var(--gold)" : undefined }}>{failed}</p><p>{failed === 1 ? "case" : "cases"} not caught or failed. Every one is listed below.</p></div>
        <div className="stat"><p className="stat-n">{run.categories.length}</p><p>areas, from the output guard to refill arithmetic. {run.stored ? `Run ${run.git_sha ? `on commit ${run.git_sha}` : ""} with ${run.model}.` : "Computed just now."}</p></div>
      </div>
      <div className="item-foot" style={{ marginBottom: 24 }}>
        {status === "authed" ? <button className="btn btn-primary" onClick={again} disabled={busy}><Icon name="sparkle" /> {busy ? "Running…" : "Run the checks again"}</button> : <span style={{ color: "var(--ink-3)" }}>Sign in to run the checks yourself.</span>}
        <span className="pill">{run.stored ? "Stored run" : "Not stored"}</span>
      </div>

      <LiveResults />

      <div className="section-title" style={{ margin: "10px 0 14px" }}><h2>The code around the model</h2><span className="pill">Runs offline, no model needed</span></div>
      <div className="stack">
        {run.categories.map((c) => {
          const pct = Math.round((c.passed / c.total) * 100);
          return (
            <article key={c.name} className="card item">
              <div className="item-top">
                <div><h3>{NICE[c.name] ?? c.name}</h3><p className="detail" style={{ marginTop: 4 }}>{c.description}</p></div>
                <span className={c.passed === c.total ? "pill pill-leaf" : "pill pill-amber"}>{c.passed} / {c.total}</span>
              </div>
              <div role="img" aria-label={`${pct} percent passed`} style={{ height: 8, borderRadius: 6, background: "rgba(255,255,255,.08)", overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: c.passed === c.total ? "var(--signal)" : "var(--gold)" }} />
              </div>
              {c.failures.length > 0 && (
                <>
                  <button className="btn btn-quiet btn-sm" style={{ justifySelf: "start" }} aria-expanded={open === c.name} onClick={() => setOpen(open === c.name ? null : c.name)}>
                    {open === c.name ? "Hide" : "Show"} the {c.failures.length} that did not pass
                  </button>
                  {open === c.name && (
                    <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 8 }}>
                      {c.failures.map((f) => (
                        <li key={f.id} className="question-box fail-box" style={{ fontFamily: "var(--font-mono)", fontSize: 13.5 }}>
                          <div><b>input</b> {f.input}</div><div><b>wanted</b> {f.expected}</div><div><b>got</b> {f.actual}</div>
                        </li>))}
                    </ul>
                  )}
                </>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
