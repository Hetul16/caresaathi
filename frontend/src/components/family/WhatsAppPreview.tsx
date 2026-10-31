"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ChatLine, ChatReply, LabelResult, SourceRef, TodayView } from "@/lib/types";
import { SourceChip } from "../Source";

interface Msg { id: number; who: "me" | "bot"; text?: string; image?: string; sources?: SourceRef[]; refused?: boolean; at: string; buttons?: { label: string; run: () => void }[] }

const clock = () => new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
const VERDICT: Record<string, string> = { matches: "Found in your documents", different_strength: "Strength differs from your documents", not_in_plan: "Not in your documents", could_not_read: "Could not read" };

// A chat that looks like WhatsApp and calls the same endpoints the website uses. It is a preview of what a WhatsApp channel would carry:
// it is NOT connected to WhatsApp. Nothing here gives medical advice; answers come from the confirmed plan, with sources.
export function WhatsAppPreview({ patientId, patientName }: { patientId: string; patientName: string }) {
  const { lang } = useI18n();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const seq = useRef(0);
  const end = useRef<HTMLDivElement>(null);
  const docInput = useRef<HTMLInputElement>(null);
  const labelInput = useRef<HTMLInputElement>(null);

  const push = useCallback((m: Omit<Msg, "id" | "at">) => setMsgs((l) => [...l, { ...m, id: ++seq.current, at: clock() }]), []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs.length]);

  const fail = useCallback((e: unknown, fallback: string) => push({ who: "bot", text: e instanceof ApiError ? e.detail || e.title : fallback, refused: true }), [push]);

  const todayMsg = useCallback(async () => {
    try {
      const v = await api<TodayView>(`/patients/${patientId}/today`);
      const open = v.slots.flatMap((s) => s.items.filter((i) => i.status !== "taken" && i.status !== "not_taken").map((i) => ({ ...i, slot: s.slot, label: s.label })));
      if (v.slots.length === 0) { push({ who: "bot", text: "No confirmed medicine with a plain schedule is due today. Confirm the plan on the website first." }); return; }
      if (open.length === 0) { push({ who: "bot", text: `All ${v.summary.taken} marked as taken today. ${v.note}` }); return; }
      push({
        who: "bot", text: `${v.date}\n${open.map((i) => `• ${i.label}: ${i.title} × ${i.units}`).join("\n")}\n\nTap one when it has been taken.`,
        buttons: open.slice(0, 3).map((i) => ({
          label: `Taken: ${i.title.split(" ")[0]}`,
          run: async () => {
            push({ who: "me", text: `Taken: ${i.title}` });
            try { await api(`/patients/${patientId}/doses`, { method: "POST", json: { item_key: i.item_key, slot: i.slot, status: "taken" } }); push({ who: "bot", text: `Marked ${i.title} (${i.label}) as taken, with your name.` }); }
            catch (e) { fail(e, "Could not save that."); }
          },
        })),
      });
    } catch (e) { fail(e, "Could not load today."); }
  }, [patientId, push, fail]);

  const ask = useCallback(async (message: string) => {
    const m = message.trim();
    if (!m || busy) return;
    setText(""); setBusy(true); push({ who: "me", text: m });
    try {
      const r = await api<ChatReply>(`/patients/${patientId}/chat`, { method: "POST", json: { message: m, language: lang } });
      push({ who: "bot", text: r.text, sources: r.sources, refused: r.kind === "refusal" });
    } catch (e) { fail(e, "Something went wrong."); }
    finally { setBusy(false); }
  }, [busy, lang, patientId, push, fail]);

  const sendDocument = useCallback(async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    push({ who: "me", image: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined, text: file.type.startsWith("image/") ? undefined : `📄 ${file.name}` });
    try {
      const fd = new FormData(); fd.append("file", file); fd.append("doc_type", "other");
      const doc = await api<{ id: string }>(`/patients/${patientId}/documents`, { method: "POST", body: fd });
      push({ who: "bot", text: "Got it. Reading it now…" });
      let status = "processing";
      for (let n = 0; n < 60 && (status === "uploaded" || status === "processing"); n++) {
        await new Promise((r) => setTimeout(r, 2000));
        status = (await api<{ status: string }>(`/documents/${doc.id}`)).status;
      }
      push({ who: "bot", text: status === "extracted" ? "Done. The lines are in the care plan, each with its place on the page. Open the Care plan tab to confirm them."
        : status === "needs_review" ? "Read. Some lines need a person to check them before they join the plan. Open the Care plan tab."
        : status === "failed" ? "I could not read that one. Try a clearer photo or a PDF." : "Still reading. Check the Documents tab in a moment." });
    } catch (e) { fail(e, "Could not upload that."); }
    finally { setBusy(false); if (docInput.current) docInput.current.value = ""; }
  }, [patientId, push, fail]);

  const sendLabel = useCallback(async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    push({ who: "me", image: URL.createObjectURL(file) });
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await api<LabelResult>(`/patients/${patientId}/label-check`, { method: "POST", body: fd });
      for (const p of r.products) {
        push({ who: "bot", text: `${p.text}\n\n${VERDICT[p.verdict] ?? ""}${p.allergy.length ? "\n\n⚠ " + p.allergy.map((a) => a.text).join("\n⚠ ") : ""}${p.question ? `\n\nQuestion for the pharmacist: ${p.question}` : ""}`,
          sources: p.plan_item ? [p.plan_item.source] : undefined, refused: p.allergy.length > 0 });
      }
      push({ who: "bot", text: r.note });
    } catch (e) { fail(e, "Could not read that photo."); }
    finally { setBusy(false); if (labelInput.current) labelInput.current.value = ""; }
  }, [patientId, push, fail]);

  // Earlier questions from the website chat, then a greeting.
  useEffect(() => {
    let live = true;
    api<ChatLine[]>(`/patients/${patientId}/chat`).catch(() => [] as ChatLine[]).then((h) => {
      if (!live) return;
      setMsgs([
        ...h.slice(-6).map((m, i) => ({ id: -100 + i, who: (m.direction === "inbound" ? "me" : "bot") as "me" | "bot", text: m.text, at: new Date(m.at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false }) })),
        { id: ++seq.current, who: "bot", at: clock(), text: `Hello. I am CareSaathi for ${patientName}. Send a photo of a prescription or a report, a photo of a medicine box, or ask about the care plan.\n\nI do not give medical advice. For that, ask the doctor or pharmacist.` },
      ]);
    });
    return () => { live = false; };
  }, [patientId, patientName]);

  const quick: [string, () => void][] = [["Today’s medicines", () => { push({ who: "me", text: "Today’s medicines" }); todayMsg(); }], ["My allergies", () => ask("Do I have any allergies?")], ["Next follow-up", () => ask("When is my next follow-up?")], ["Warning signs", () => ask("What are my warning signs?")]];

  return (
    <div className="stack">
      <div className="section-title"><h2>Chat</h2><span className="pill pill-amber">WhatsApp-style preview · not connected to WhatsApp</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        This is how the same flows would look inside WhatsApp, so a family member does not have to open the website: forward a photo, ask a question, tap “Taken”.
        It runs on the same checks as the website, so every answer carries its source and nothing here says whether a medicine is safe.
      </p>
      <div className="wa-phone" role="region" aria-label="WhatsApp-style chat preview">
        <header className="wa-head"><span className="wa-avatar" aria-hidden>CS</span><div><b>CareSaathi</b><small>care companion · for {patientName}</small></div></header>
        <div className="wa-body" aria-live="polite">
          {msgs.map((m) => (
            <div key={m.id} className={`wa-row ${m.who}`}>
              <div className={`wa-bubble ${m.who}${m.refused ? " warn" : ""}`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                {m.image && <img src={m.image} alt="Photo you sent" className="wa-img" />}
                {m.text && <span style={{ whiteSpace: "pre-wrap" }}>{m.text}</span>}
                {m.sources && m.sources.length > 0 && <span className="wa-src">{m.sources.slice(0, 3).map((s, k) => <SourceChip key={k} source={s} short />)}</span>}
                <small className="wa-time">{m.at}{m.who === "me" ? " ✓✓" : ""}</small>
              </div>
              {m.buttons && <div className="wa-btns">{m.buttons.map((b) => <button key={b.label} onClick={b.run}>{b.label}</button>)}</div>}
            </div>
          ))}
          {busy && <div className="wa-row bot"><div className="wa-bubble bot wa-typing" aria-label="CareSaathi is working"><i /><i /><i /></div></div>}
          <div ref={end} />
        </div>
        <div className="wa-quick">{quick.map(([l, f]) => <button key={l} disabled={busy} onClick={f}>{l}</button>)}</div>
        {menu && (
          <div className="wa-menu" role="menu">
            <button role="menuitem" onClick={() => { setMenu(false); docInput.current?.click(); }}>📄 Prescription or report</button>
            <button role="menuitem" onClick={() => { setMenu(false); labelInput.current?.click(); }}>💊 Medicine box or strip</button>
          </div>
        )}
        <input ref={docInput} type="file" hidden accept="image/jpeg,image/png,image/webp,application/pdf" onChange={(e) => sendDocument(e.target.files?.[0])} />
        <input ref={labelInput} type="file" hidden accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(e) => sendLabel(e.target.files?.[0])} />
        <form className="wa-compose" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
          <button type="button" className="wa-icon" aria-label="Attach a photo or document" aria-expanded={menu} disabled={busy} onClick={() => setMenu((v) => !v)}>＋</button>
          <label className="sr-only" htmlFor="wa-in">Message</label>
          <input id="wa-in" value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder="Message" autoComplete="off" />
          <button type="submit" className="wa-send" aria-label="Send" disabled={busy || !text.trim()}>➤</button>
        </form>
      </div>
      <p style={{ color: "var(--ink-3)", fontSize: 14 }}>
        Real WhatsApp needs a Meta business account, approved message templates and a public webhook. That is the next step after the hackathon; see docs/09-decisions.md.
        Voice notes are not in this preview.
      </p>
    </div>
  );
}
