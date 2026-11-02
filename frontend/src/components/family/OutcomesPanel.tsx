"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { OutcomeItem, OutcomesBoard } from "@/lib/types";
import { Icon } from "../Icon";
import { afterCommit } from "@/lib/defer";

const STATUS: Record<OutcomeItem["status"], { label: string; cls: string }> = {
  open: { label: "Waiting for an answer", cls: "pill pill-amber" },
  seen: { label: "Seen, still waiting", cls: "pill pill-amber" },
  asked: { label: "Asked, waiting", cls: "pill pill-amber" },
  answered: { label: "Answered", cls: "pill pill-leaf" },
  closed_without_answer: { label: "Closed, no answer on record", cls: "pill pill-rose" },
};
const ago = (d: number) => (d === 0 ? "today" : d === 1 ? "1 day" : `${d} days`);
const when = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

function Stat({ n, label, hint }: { n: string | number; label: string; hint?: string }) {
  return <div className="stat"><p className="stat-n">{n}</p><p>{label}{hint ? <><br /><small style={{ color: "var(--ink-3)" }}>{hint}</small></> : null}</p></div>;
}

// Outcomes board: own the outcome, not the engagement. Every flag stays a question until a named person records the answer.
export function OutcomesPanel({ patientId, canApprove, toast, onChange }: { patientId: string; canApprove: boolean; toast: (m: string) => void; onChange: () => void }) {
  const [b, setB] = useState<OutcomesBoard | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [reply, setReply] = useState<string>("");
  const [text, setText] = useState("");
  const [by, setBy] = useState("");

  const load = useCallback(async () => {
    try { setB(await api<OutcomesBoard>(`/patients/${patientId}/outcomes`)); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not load the outcomes board"); }
  }, [patientId, toast]);
  useEffect(() => { afterCommit(load); }, [load]);

  function start(id: string) { setOpen(id); setReply(""); setText(""); setBy(""); }
  async function save(it: OutcomeItem) {
    try {
      await api(`/patients/${patientId}/outcomes/answers`, { method: "POST", json: { subject_kind: it.kind, subject_id: it.id, ...(reply ? { doctor_message_id: reply } : { answer_text: text.trim(), answered_by: by.trim() }) } });
      setOpen(null); toast("Answer recorded with your name."); await load(); onChange();
    } catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not record the answer"); }
  }

  if (!b) return <div className="skeleton" style={{ height: 220 }} aria-busy="true" />;
  const s = b.summary;
  return (
    <div className="stack">
      <div className="section-title"><h2>Outcomes</h2><span className="pill">Questions, not clicks</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        Every flag CareSaathi raises is a question for the doctor or pharmacist. It stays here until a person records the answer and who gave it.
        This board counts what got answered. It does not judge the answers.
      </p>

      <div className="stats" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))" }}>
        <Stat n={s.raised} label="questions raised" />
        <Stat n={s.answered} label="answered" hint={s.average_days_to_answer != null ? `on average after ${s.average_days_to_answer} days` : undefined} />
        <Stat n={s.waiting} label="waiting" hint={s.oldest_waiting_days != null ? `oldest: ${ago(s.oldest_waiting_days)}` : undefined} />
        <Stat n={s.closed_without_answer} label="closed with no answer on record" />
      </div>
      <p style={{ color: "var(--ink-2)" }}>
        Sent to doctors: <b>{b.doctor_thread.questions_sent}</b> · replies: <b>{b.doctor_thread.replies_received}</b> · replies not yet used: <b>{b.doctor_thread.replies_not_yet_used}</b> ·
        Follow-ups: <b>{b.follow_ups.done}</b> done, <b>{b.follow_ups.confirmed}</b> confirmed, <b>{b.follow_ups.waiting_for_confirmation}</b> waiting for confirmation
      </p>

      {b.items.length === 0 && <p className="card card-pad">No flags have been raised yet. When a document or a new prescription needs a question, it will appear here.</p>}
      {b.items.map((it) => (
        <article key={`${it.kind}-${it.id}`} className="card item">
          <div className="item-top">
            <div><p className="eyebrow">{it.label} · raised {when(it.raised_at)}</p><h3 style={{ marginTop: 4 }}>{it.title}</h3></div>
            <span className="item-foot" style={{ gap: 6 }}>
              <span className={STATUS[it.status].cls}>{STATUS[it.status].label}</span>
              {it.status !== "answered" && it.status !== "closed_without_answer" && <span className="pill">{ago(it.days_open)} open</span>}
            </span>
          </div>
          <div className="question-box">{it.question}</div>
          {it.answer && (
            <div className="msg from_doctor" style={{ justifySelf: "stretch", maxWidth: "100%" }}>
              <small>{it.answer.source_kind === "doctor_message" ? `${it.answer.answered_by}'s exact words, from the doctor link` : `Told by ${it.answer.answered_by}, typed by ${it.answer.recorded_by}`} · {when(it.answer.recorded_at)}</small>
              {it.answer.text}
            </div>
          )}
          {it.status === "closed_without_answer" && <p style={{ color: "var(--ink-2)" }}>This question was closed without an answer being written down.</p>}
          {it.status !== "answered" && canApprove && open !== it.id && (
            <div className="item-foot"><button className="btn btn-quiet btn-sm" onClick={() => start(it.id)}><Icon name="check" /> Record the answer</button></div>
          )}
          {open === it.id && (
            <div className="stack">
              {b.usable_replies.length > 0 && (
                <fieldset style={{ border: "1px solid var(--line)", borderRadius: 14, padding: 12 }}>
                  <legend className="eyebrow">Use a doctor’s reply as the answer</legend>
                  {b.usable_replies.map((r) => (
                    <label key={r.id} style={{ display: "flex", gap: 8, alignItems: "start", margin: "6px 0" }}>
                      <input type="radio" name={`reply-${it.id}`} checked={reply === r.id} onChange={() => setReply(r.id)} />
                      <span><b>{r.doctor_name}</b> · {when(r.at)}<br />{r.body}</span>
                    </label>
                  ))}
                  <label style={{ display: "flex", gap: 8, margin: "6px 0" }}><input type="radio" name={`reply-${it.id}`} checked={reply === ""} onChange={() => setReply("")} /> Or type what you were told</label>
                </fieldset>
              )}
              {reply === "" && (
                <>
                  <label htmlFor={`ans-${it.id}`} className="eyebrow">What the doctor or pharmacist said</label>
                  <textarea id={`ans-${it.id}`} className="input" rows={3} maxLength={1500} value={text} onChange={(e) => setText(e.target.value)} />
                  <label htmlFor={`by-${it.id}`} className="eyebrow">Who said it</label>
                  <input id={`by-${it.id}`} className="input" maxLength={80} value={by} onChange={(e) => setBy(e.target.value)} placeholder="Dr. Joshi, or the pharmacist" />
                </>
              )}
              <div className="item-foot">
                <button className="btn btn-primary btn-sm" disabled={reply === "" && (!text.trim() || !by.trim())} onClick={() => save(it)}>Record with my name</button>
                <button className="btn btn-quiet btn-sm" onClick={() => setOpen(null)}>Cancel</button>
              </div>
            </div>
          )}
        </article>
      ))}
      <p style={{ color: "var(--ink-3)", fontSize: 14 }}>{b.note}</p>
    </div>
  );
}
