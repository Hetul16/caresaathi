"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { CareTask, Member } from "@/lib/types";
import { Icon } from "../Icon";

const when = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

// Tasks: who is doing what for the patient. Coordination only (a refill to collect, a lift to physiotherapy), never a medical instruction.
export function TasksPanel({ patientId, toast }: { patientId: string; toast: (m: string) => void }) {
  const [tasks, setTasks] = useState<CareTask[] | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [title, setTitle] = useState("");
  const [who, setWho] = useState("");
  const [due, setDue] = useState("");
  const load = useCallback(async () => {
    try {
      setTasks((await api<{ tasks: CareTask[] }>(`/patients/${patientId}/tasks`)).tasks);
      setMembers(await api<Member[]>(`/patients/${patientId}/members`));
    } catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not load the tasks"); }
  }, [patientId, toast]);
  useEffect(() => { load(); }, [load]);

  async function add() {
    try { await api(`/patients/${patientId}/tasks`, { method: "POST", json: { title: title.trim(), ...(who ? { assigned_to: who } : {}), ...(due ? { due_date: due } : {}) } }); setTitle(""); setWho(""); setDue(""); toast("Task added."); await load(); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not add the task"); }
  }
  async function done(id: string) {
    try { await api(`/tasks/${id}/done`, { method: "POST" }); toast("Marked done, with your name."); await load(); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not update the task"); }
  }

  if (!tasks) return <div className="skeleton" style={{ height: 180 }} aria-busy="true" />;
  const open = tasks.filter((t) => t.status === "open");
  return (
    <div className="stack">
      <div className="section-title"><h2>Tasks</h2><span className="pill">{open.length} open</span></div>
      <p style={{ color: "var(--ink-2)" }}>Who is doing what, so two people do not do the same thing and nothing is left to “someone”. For example: collect the refill, go with her to physiotherapy, call the pharmacy.</p>

      <div className="card card-pad stack">
        <label htmlFor="task-title" className="eyebrow">What needs doing</label>
        <input id="task-title" className="input" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Collect the Pregabalin refill from the pharmacy" />
        <div className="item-foot">
          <label style={{ color: "var(--ink-2)" }}>Who{" "}
            <select value={who} onChange={(e) => setWho(e.target.value)} className="input" style={{ width: "auto", padding: "8px 12px" }}>
              <option value="">Anyone</option>
              {members.filter((m) => m.status === "active").map((m) => <option key={m.user_id} value={m.user_id}>{m.name}{m.relationship ? ` (${m.relationship})` : ""}</option>)}
            </select></label>
          <label style={{ color: "var(--ink-2)" }}>By{" "}<input type="date" className="input" style={{ width: "auto", padding: "8px 12px" }} value={due} onChange={(e) => setDue(e.target.value)} /></label>
          <button className="btn btn-primary" disabled={!title.trim()} onClick={add}><Icon name="check" /> Add task</button>
        </div>
      </div>

      {tasks.length === 0 && <p className="card card-pad">No tasks yet.</p>}
      {tasks.map((t) => (
        <article key={t.id} className="card item" style={t.status === "done" ? { opacity: 0.7 } : undefined}>
          <div className="item-top">
            <div>
              <h3 style={{ textDecoration: t.status === "done" ? "line-through" : undefined }}>{t.title}</h3>
              <p className="detail" style={{ marginTop: 4 }}>
                {t.assigned_to ? `For ${t.assigned_to}` : "For anyone"} · added by {t.created_by}{t.due_date ? ` · by ${when(t.due_date)}` : ""}
              </p>
            </div>
            <span className="item-foot" style={{ gap: 6 }}>
              {t.overdue && <span className="pill pill-rose">Overdue</span>}
              {t.status === "done" ? <span className="pill pill-leaf">Done by {t.done_by} · {t.done_at}</span> : <button className="btn btn-quiet btn-sm" onClick={() => done(t.id)}><Icon name="check" /> Mark done</button>}
            </span>
          </div>
        </article>
      ))}
    </div>
  );
}
