"use client";
import { useState } from "react";
import type { DoctorPage } from "@/lib/types";
import { CardView } from "./CardView";
import { Icon } from "./Icon";

const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

// What one doctor sees: the documented facts (the same read-only card), the family's approved questions, and a reply box.
export function DoctorView({ token, initial }: { token: string; initial: DoctorPage }) {
  const [page, setPage] = useState(initial);
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function send() {
    if (!text.trim()) return;
    setState("sending");
    try {
      const res = await fetch(`/api/v1/d/${encodeURIComponent(token)}/reply`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ body: text.trim() }) });
      if (!res.ok) { setState("error"); return; }
      const fresh = await fetch(`/api/v1/d/${encodeURIComponent(token)}`, { cache: "no-store" });
      if (fresh.ok) setPage(await fresh.json());
      setText(""); setState("sent");
    } catch { setState("error"); }
  }

  return (
    <div className="wrap doc-page">
      <header>
        <p className="eyebrow">Shared with {page.doctor_name} · expires {when(page.expires_at)}</p>
        <h1 style={{ fontSize: "clamp(28px, 4vw, 44px)", margin: "6px 0" }}>Care plan, as the family’s documents say it</h1>
        <p style={{ color: "var(--ink-2)", maxWidth: "70ch" }}>{page.note}</p>
      </header>

      <section aria-label="Messages" className="card card-pad stack">
        <h2 style={{ fontSize: 20, margin: 0 }}>From the family</h2>
        {page.thread.length === 0 && <p style={{ color: "var(--ink-2)" }}>No questions have been sent yet.</p>}
        {page.thread.map((m) => (
          <div key={m.id} className={`msg ${m.direction}`}><small>{m.direction === "to_doctor" ? "Family" : "Your reply"} · {when(m.at)}</small>{m.body}</div>
        ))}
        {page.can_reply ? (
          <div className="stack">
            <label htmlFor="reply" className="eyebrow">Your reply (saved exactly as you write it)</label>
            <textarea id="reply" className="input" rows={4} maxLength={4000} value={text} onChange={(e) => { setText(e.target.value); setState("idle"); }} />
            <div className="item-foot">
              <button className="btn btn-primary" onClick={send} disabled={state === "sending" || !text.trim()}><Icon name="check" /> Send reply</button>
              {state === "sent" && <span role="status" style={{ color: "var(--signal)" }}>Sent. The family can see it.</span>}
              {state === "error" && <span role="alert" style={{ color: "var(--coral)" }}>Could not send. The link may have expired.</span>}
            </div>
            <p style={{ color: "var(--ink-3)", fontSize: 14 }}>Your reply does not change the family’s plan by itself. They review it and confirm any change.</p>
          </div>
        ) : <p style={{ color: "var(--ink-3)" }}>You can reply once the family has sent a question.</p>}
      </section>

      <CardView c={page.card} />
    </div>
  );
}
