"use client";
import { useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import type { CarePlan, ChatReply } from "@/lib/types";
import { api, ApiError } from "@/lib/api";
import { useWavRecorder } from "@/lib/recorder";
import { speechLocale, useI18n } from "@/lib/i18n";
import { spokenDose } from "@/lib/spoken";
import { Icon } from "@/components/Icon";
import { ElderCheckin } from "@/components/ElderCheckin";
import { VoiceOrb, useMicLevel, useSpeech, type OrbState } from "@/components/VoiceOrb";

const SLOTS = ["morning", "noon", "evening", "night"] as const;

const VOICE_NEEDS_LIVE: Record<string, string> = {
  en: "Voice questions are not available yet. You can type your question below.",
  hi: "आवाज़ से सवाल अभी उपलब्ध नहीं है। आप नीचे अपना सवाल लिख सकते हैं।",
  mr: "आवाजाने प्रश्न विचारणे अजून उपलब्ध नाही. तुम्ही खाली तुमचा प्रश्न लिहू शकता.",
};

// patientId is set for a signed-in family's patient. Then the orb records a short question, Muse Voice Transcribe turns it into text, and the
// answer is read back from the care plan (never advice). In the demo there is no backend, so the orb only shows the microphone level.
export function ElderView({ plan, emergencyHref, patientId }: { plan: CarePlan; emergencyHref: string; patientId?: string }) {
  const { lang, t } = useI18n();
  const [localListening, setLocalListening] = useState(false);
  const mic = useMicLevel(!patientId && localListening);
  const rec = useWavRecorder();
  const [answer, setAnswer] = useState<{ heard?: string; text: string } | null>(null);
  const [typed, setTyped] = useState("");
  const [asking, setAsking] = useState(false);
  const listening = patientId ? rec.state === "recording" : localListening;
  const level = patientId ? rec.level : mic.level;
  const error = patientId ? (rec.state === "denied" || rec.state === "unsupported" ? "mic" : null) : mic.error;
  const { speak, repeat, stop, speaking } = useSpeech(speechLocale[lang]);

  // The elder only hears medicines the family has confirmed, and nothing under an open conflict.
  const conflictNames = plan.open_conflicts.map((c) => c.medicine.toLowerCase());
  const meds = useMemo(() => plan.items.filter((i) => i.kind === "medicine"), [plan.items]);
  const held = meds.filter((m) => !m.confirmed || conflictNames.some((n) => n.startsWith(m.title.toLowerCase().split(" ")[0])));
  const heard = meds.filter((m) => !held.includes(m));

  const state: OrbState = listening ? "listening" : speaking ? "speaking" : "idle";

  async function ask(call: () => Promise<ChatReply>) {
    setAsking(true);
    try { const r = await call(); setAnswer({ heard: r.heard, text: r.text }); speak(r.text); }
    catch (e) {
      const msg = e instanceof ApiError && e.status === 503 ? VOICE_NEEDS_LIVE[lang] : e instanceof ApiError ? e.detail || e.title : "Something went wrong.";
      setAnswer({ text: msg });
    } finally { setAsking(false); }
  }

  async function toggle() {
    if (speaking) { stop(); return; }
    if (!patientId) { setLocalListening((v) => !v); return; }
    if (rec.state === "recording") {
      const wav = rec.stop();
      if (!wav) return;
      const form = new FormData();
      form.append("file", wav, "question.wav");
      await ask(() => api<ChatReply>(`/patients/${patientId}/chat/voice?language=${lang}`, { method: "POST", body: form }));
    } else {
      setAnswer(null);
      await rec.start();
    }
  }

  function submitTyped(ev: FormEvent) {
    ev.preventDefault();
    const m = typed.trim();
    if (!m || !patientId) return;
    setTyped("");
    ask(() => api<ChatReply>(`/patients/${patientId}/chat`, { method: "POST", json: { message: m, language: lang } }));
  }

  function readAll() {
    const intro = { en: "Here are your medicines for today.", hi: "आज की आपकी दवाइयाँ ये हैं।", mr: "आजची तुमची औषधे ही आहेत." }[lang];
    speak([intro, ...heard.map((m) => spokenDose(m, lang))].join(" "));
  }

  return (
    <div className="elder wrap">
      <h1 className="elder-greet">{t("hello")}, {plan.patient.name.split(" ")[0]}</h1>
      <p className="elder-sub">{t("tagline")}</p>

      <VoiceOrb state={state} onToggle={toggle} level={level} />
      <p className="transcript" aria-live="polite">
        {error === "mic" ? "The microphone is not available. You can still use the buttons below." : asking ? "…" : ""}
      </p>
      {answer && (
        <div className="card card-pad" style={{ maxWidth: 720, margin: "0 auto 20px", fontSize: 22 }} aria-live="polite">
          {answer.heard && <p style={{ color: "var(--ink-3)", fontSize: 16, marginBottom: 6 }}>I heard: “{answer.heard}”</p>}
          <p style={{ whiteSpace: "pre-wrap" }}>{answer.text}</p>
        </div>
      )}

      <div className="elder-tools">
        <button className="btn btn-primary" onClick={readAll}><Icon name="volume" /> {t("listen")}</button>
        <button className="btn btn-quiet" onClick={() => repeat(false)}><Icon name="repeat" /> {t("repeat")}</button>
        <button className="btn btn-quiet" onClick={() => repeat(true)}><Icon name="clock" /> {t("slower")}</button>
      </div>

      {patientId && (
        <form onSubmit={submitTyped} className="item-foot" style={{ maxWidth: 720, margin: "0 auto 24px", flexWrap: "nowrap" }}>
          <label className="sr-only" htmlFor="elder-q">Type a question</label>
          <input id="elder-q" value={typed} onChange={(e) => setTyped(e.target.value)} maxLength={400} placeholder={{ en: "Or type a question", hi: "या अपना सवाल लिखें", mr: "किंवा तुमचा प्रश्न लिहा" }[lang]}
            style={{ flex: 1, minHeight: 58, padding: "0 18px", borderRadius: 16, border: "1px solid var(--line)", background: "var(--card)", color: "var(--ink)", font: "inherit", fontSize: 20 }} />
          <button className="btn btn-quiet" style={{ minHeight: 58 }} disabled={asking || !typed.trim()}><Icon name="check" /> OK</button>
        </form>
      )}

      {patientId && <ElderCheckin patientId={patientId} lang={lang} />}

      <h2 className="elder-title">{t("todayMedicines")}</h2>
      <div className="dose-grid">
        {heard.map((m) => (
          <article className="card dose" key={m.item_key}>
            <h3>{m.title}</h3>
            <div className="dose-times">
              {SLOTS.map((s) => m.schedule?.[s] ? (
                <span className="dose-time" key={s}>{t(s)} <small>{m.schedule[s]} {t("tablet")}</small></span>
              ) : null)}
            </div>
            {m.detail && <p className="detail" style={{ color: "var(--ink-2)", fontSize: 18 }}>{m.detail}</p>}
            <button className="btn btn-quiet" onClick={() => speak(spokenDose(m, lang))}>
              <Icon name="volume" /> {t("listen")}
            </button>
          </article>
        ))}
        {held.length > 0 && (
          <article className="card dose dose-pending" style={{ gridColumn: "1 / -1" }}>
            <h3 style={{ fontSize: 24 }}>
              {{ en: "Your family is checking something with the doctor.", hi: "आपका परिवार डॉक्टर से कुछ पूछ रहा है।", mr: "तुमचे कुटुंब डॉक्टरांना काहीतरी विचारत आहे." }[lang]}
            </h3>
            <p style={{ color: "var(--ink-2)", fontSize: 18 }}>
              {{ en: "They will tell you once it is confirmed.", hi: "पुष्टि होते ही वे आपको बताएँगे।", mr: "पुष्टी झाल्यावर ते तुम्हाला सांगतील." }[lang]}
            </p>
          </article>
        )}
      </div>

      <div className="sos-bar">
        <div className="wrap">
          <Link href={emergencyHref} className="btn sos"><Icon name="siren" /> {t("emergency")}</Link>
        </div>
      </div>
    </div>
  );
}
