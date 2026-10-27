"use client";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ChatLine, ChatReply, SourceRef } from "@/lib/types";
import { Icon } from "../Icon";
import { SourceChip } from "../Source";

interface Line { who: "me" | "bot"; text: string; sources?: SourceRef[]; refused?: boolean }
const SUGGEST: Record<string, string[]> = {
  en: ["What are my medicines?", "Do I have any allergies?", "When is my next follow-up?", "What are my warning signs?", "What changed recently?"],
  hi: ["मेरी दवाइयाँ क्या हैं?", "क्या कोई एलर्जी दर्ज है?", "अगली मुलाक़ात कब है?"],
  mr: ["माझी औषधे कोणती?", "कोणती ऍलर्जी नोंदलेली आहे?", "पुढची भेट कधी आहे?"],
};

// Reads back what is in the care plan. It does not give medical advice, and it says so when asked for some.
export function ChatPanel({ patientId }: { patientId: string }) {
  const { lang } = useI18n();
  const [lines, setLines] = useState<Line[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<ChatLine[]>(`/patients/${patientId}/chat`).then((h) => setLines(h.map((m) => ({ who: m.direction === "inbound" ? "me" : "bot", text: m.text })))).catch(() => undefined);
  }, [patientId]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [lines.length]);

  const send = useCallback(async (message: string) => {
    const m = message.trim();
    if (!m || busy) return;
    setBusy(true); setText("");
    setLines((l) => [...l, { who: "me", text: m }]);
    try {
      const r = await api<ChatReply>(`/patients/${patientId}/chat`, { method: "POST", json: { message: m, language: lang } });
      setLines((l) => [...l, { who: "bot", text: r.text, sources: r.sources, refused: r.kind === "refusal" }]);
    } catch (e) {
      setLines((l) => [...l, { who: "bot", text: e instanceof ApiError ? e.detail || e.title : "Something went wrong.", refused: true }]);
    } finally { setBusy(false); }
  }, [busy, lang, patientId]);

  return (
    <div className="stack">
      <div className="section-title"><h2>Ask</h2><span className="pill">Reads your care plan</span></div>
      <p style={{ color: "var(--ink-2)" }}>Ask about the medicines your family has confirmed, follow-ups, allergies or the warning signs in your own documents. CareSaathi will not say whether anything is safe, and will not tell anyone to stop, skip or change a medicine: for that, ask the doctor or pharmacist.</p>
      <div className="card card-pad" style={{ minHeight: 280, display: "grid", gap: 12, alignContent: "start" }} aria-live="polite">
        {lines.length === 0 && <p style={{ color: "var(--ink-3)" }}>Try one of these:</p>}
        {lines.map((l, i) => (
          <div key={i} style={{ justifySelf: l.who === "me" ? "end" : "start", maxWidth: "min(620px, 92%)" }}>
            <div className="card" style={{ padding: "10px 14px", background: l.who === "me" ? "var(--leaf-tint)" : l.refused ? "var(--amber-tint)" : undefined, whiteSpace: "pre-wrap" }}>{l.text}</div>
            {l.sources && l.sources.length > 0 && <div className="item-foot" style={{ marginTop: 6 }}>{l.sources.slice(0, 4).map((s, k) => <SourceChip key={k} source={s} />)}</div>}
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="item-foot">{(SUGGEST[lang] ?? SUGGEST.en).map((q) => <button key={q} className="btn btn-quiet btn-sm" disabled={busy} onClick={() => send(q)}>{q}</button>)}</div>
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); send(text); }} className="item-foot" style={{ flexWrap: "nowrap" }}>
        <label className="sr-only" htmlFor="chat-in">Your question</label>
        <input id="chat-in" value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder="Ask about your plan…" autoComplete="off"
          style={{ flex: 1, minHeight: 52, padding: "0 16px", borderRadius: 14, border: "1px solid var(--line)", background: "var(--card)", color: "var(--ink)", font: "inherit", fontSize: 17 }} />
        <button className="btn btn-primary" disabled={busy || !text.trim()} type="submit"><Icon name="check" /> Ask</button>
      </form>
    </div>
  );
}
