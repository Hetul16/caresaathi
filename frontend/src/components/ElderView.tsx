"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import type { CarePlan } from "@/lib/types";
import { speechLocale, useI18n } from "@/lib/i18n";
import { spokenDose } from "@/lib/spoken";
import { Icon } from "@/components/Icon";
import { VoiceOrb, useMicLevel, useSpeech, type OrbState } from "@/components/VoiceOrb";

const SLOTS = ["morning", "noon", "evening", "night"] as const;

export function ElderView({ plan, emergencyHref }: { plan: CarePlan; emergencyHref: string }) {
  const { lang, t } = useI18n();
  const [listening, setListening] = useState(false);
  const { level, error } = useMicLevel(listening);
  const { speak, repeat, stop, speaking } = useSpeech(speechLocale[lang]);

  // The elder only hears medicines the family has confirmed, and nothing under an open conflict.
  const conflictNames = plan.open_conflicts.map((c) => c.medicine.toLowerCase());
  const meds = useMemo(() => plan.items.filter((i) => i.kind === "medicine"), [plan.items]);
  const held = meds.filter((m) => !m.confirmed || conflictNames.some((n) => n.startsWith(m.title.toLowerCase().split(" ")[0])));
  const heard = meds.filter((m) => !held.includes(m));

  const state: OrbState = listening ? "listening" : speaking ? "speaking" : "idle";

  function toggle() {
    if (speaking) { stop(); return; }
    setListening((v) => !v);
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
        {error === "mic" ? "The microphone is not available. You can still use the buttons below." : ""}
      </p>

      <div className="elder-tools">
        <button className="btn btn-primary" onClick={readAll}><Icon name="volume" /> {t("listen")}</button>
        <button className="btn btn-quiet" onClick={() => repeat(false)}><Icon name="repeat" /> {t("repeat")}</button>
        <button className="btn btn-quiet" onClick={() => repeat(true)}><Icon name="clock" /> {t("slower")}</button>
      </div>

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
