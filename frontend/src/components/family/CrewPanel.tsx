"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { CrewRun, CrewStep } from "@/lib/types";
import { Icon } from "../Icon";
import { SourceChip } from "../Source";
import { afterCommit } from "@/lib/defer";

const TOOL: Record<string, string> = {
  read_care_plan: "Read the care plan", list_open_flags: "Collect open questions", list_pending: "Find what awaits confirmation",
  check_supply: "Check refill dates", prepare_visit_summary: "Build the visit brief", message_doctor_draft: "Draft a message to the doctor",
};
const GOALS = ["Prepare us for the next doctor visit", "Get a visit brief and send the questions to the doctor"];
const when = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", second: "2-digit" });

function StepCard({ s, canApprove, onDecide }: { s: CrewStep; canApprove: boolean; onDecide: (id: string, d: "approve" | "refuse") => void }) {
  const waiting = s.status === "awaiting_approval" && s.action_status === "awaiting_approval";
  return (
    <li className={`tstep ${s.status}`} data-n={s.seq}>
      <div className="item-top">
        <div><span className="tool">{s.tool}</span><h3 style={{ margin: "2px 0 0", fontSize: 17 }}>{TOOL[s.tool] ?? s.tool}</h3></div>
        <span className="item-foot" style={{ gap: 6 }}>
          {s.permission && <span className={s.permission === "ask_first" ? "pill pill-marigold" : "pill"}>{s.permission === "ask_first" ? "Asks first" : "Automatic"}</span>}
          {s.status === "ran" && <span className="pill pill-leaf">Done</span>}
          {s.status === "refused" && <span className="pill pill-rose">Refused by the system</span>}
          {s.status === "failed" && <span className="pill pill-rose">Could not finish</span>}
          {s.status === "awaiting_approval" && (s.action_status === "done" || s.action_status === "approved"
            ? <span className="pill pill-leaf">Approved by {s.approved_by ?? "a family member"}</span>
            : s.action_status === "refused" ? <span className="pill pill-rose">Declined</span> : <span className="pill pill-marigold">Waiting for approval</span>)}
        </span>
      </div>
      {s.why && <p className="why">{s.why}</p>}
      {s.summary && <p className="res">{s.summary}</p>}
      {s.reason && <p className="res" style={{ color: "var(--coral)" }}>{s.reason}</p>}
      {waiting && (
        <div className="item-foot">
          {canApprove
            ? <><button className="btn btn-leaf btn-sm" onClick={() => s.action_id && onDecide(s.action_id, "approve")}><Icon name="check" /> Approve and send to the doctor</button>
                <button className="btn btn-quiet btn-sm" onClick={() => s.action_id && onDecide(s.action_id, "refuse")}><Icon name="x" /> Decline</button></>
            : <span style={{ color: "var(--ink-3)" }}>A family member with approval rights must decide this.</span>}
        </div>
      )}
    </li>
  );
}

// The care crew: a goal goes in, a bounded list of registered tools runs one by one, and every step stays on screen.
export function CrewPanel({ patientId, canApprove, toast, onChange }: { patientId: string; canApprove: boolean; toast: (m: string) => void; onChange: () => void }) {
  const [runs, setRuns] = useState<CrewRun[] | null>(null);
  const [goal, setGoal] = useState(GOALS[0]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setRuns((await api<{ runs: CrewRun[] }>(`/patients/${patientId}/agent/runs`)).runs); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not load the care crew"); }
  }, [patientId, toast]);
  useEffect(() => { afterCommit(load); }, [load]);
  const running = runs?.some((r) => r.status === "running");
  useEffect(() => { if (!running) return; const t = setInterval(load, 1200); return () => clearInterval(t); }, [running, load]);

  async function start() {
    setBusy(true);
    try { await api(`/patients/${patientId}/agent/runs`, { method: "POST", json: { goal } }); await load(); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not start"); }
    finally { setBusy(false); }
  }
  async function decide(id: string, d: "approve" | "refuse") {
    try { await api(`/actions/${id}/${d}`, { method: "POST", json: {} }); toast(d === "approve" ? "Approved by you. The doctor can now see the questions." : "Declined. Nothing was sent."); await load(); onChange(); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not record that"); }
  }

  const latest = runs?.[0];
  return (
    <div className="stack">
      <div className="section-title"><h2>Care crew</h2><span className="pill">Bounded · every step recorded</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        Give it a goal. It uses a short list of registered tools, one at a time, and shows each step here. It reads and drafts only:
        it cannot change a medicine or a dose, and anything that reaches another person waits for a named family member to approve.
      </p>
      <div className="card card-pad stack">
        <label htmlFor="crew-goal" className="eyebrow">What should the crew do?</label>
        <textarea id="crew-goal" className="input" rows={2} maxLength={300} value={goal} onChange={(e) => setGoal(e.target.value)} />
        <div className="item-foot">
          <button className="btn btn-primary" disabled={busy || running || !goal.trim()} onClick={start}><Icon name="sparkle" /> {running ? "Working…" : "Run the care crew"}</button>
          {GOALS.map((g) => <button key={g} className="btn btn-quiet btn-sm" onClick={() => setGoal(g)}>{g}</button>)}
        </div>
      </div>

      {runs === null && <div className="skeleton" style={{ height: 120 }} aria-busy="true" />}
      {latest && (
        <section aria-label="Latest run" className="stack">
          <div className="section-title">
            <h2 style={{ fontSize: 20 }}>“{latest.goal}”</h2>
            {latest.status === "running" ? <span className="tlive"><i /> Working</span>
              : latest.status === "done" ? <span className="pill pill-leaf">Finished {latest.finished_at ? when(latest.finished_at) : ""}</span>
              : <span className="pill pill-rose">Did not run</span>}
          </div>
          {latest.error && <p className="card card-pad" style={{ borderColor: "var(--coral)" }}>{latest.error}</p>}
          {latest.steps.length > 0 && (
            <ol className="trace" aria-live="polite">
              {latest.steps.map((s) => <StepCard key={s.seq} s={s} canApprove={canApprove} onDecide={decide} />)}
            </ol>
          )}
          {latest.brief && (
            <article className="brief" aria-label="Visit brief">
              <h3>{latest.brief.title}</h3>
              {latest.brief.sections.map((sec) => (
                <div key={sec.heading}>
                  <h4>{sec.heading}</h4>
                  <ul>{sec.lines.map((l, i) => <li key={i}>{l.text} {l.source && <span className="src"><SourceChip source={l.source} short /></span>}</li>)}</ul>
                </div>
              ))}
              {latest.brief.questions.length > 0 && (
                <div className="qs">
                  <h4>Questions for the doctor or pharmacist</h4>
                  <ol>{latest.brief.questions.map((q) => <li key={q}>{q}</li>)}</ol>
                </div>
              )}
              <p className="src">{latest.brief.note}</p>
              <div className="item-foot no-print"><button className="btn btn-quiet btn-sm" onClick={() => window.print()}><Icon name="file" /> Print the brief</button></div>
            </article>
          )}
        </section>
      )}
      {runs && runs.length > 1 && <p style={{ color: "var(--ink-3)" }}>{runs.length - 1} earlier run{runs.length === 2 ? "" : "s"} are kept in the history.</p>}
    </div>
  );
}
