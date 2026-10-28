"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppGate } from "@/components/AppGate";
import { api, ApiError } from "@/lib/api";
import { readSelected, usePatients } from "@/lib/live";
import type { FridgeSheet } from "@/lib/types";

type Lang = "en" | "hi" | "mr";
type Slot = "morning" | "noon" | "evening" | "night";
const SLOTS: Slot[] = ["morning", "noon", "evening", "night"];

// Fixed words, written once. Hindi and Marathi have not been reviewed by a native speaker yet (docs/10-hackathon-facts.md).
const T: Record<Lang, { title: string; slot: Record<Slot, string>; none: string; empty: string; confirmed: string; written: string; allergy: string; notRecorded: string; note: string; print: string; back: string; label: string }> = {
  en: { title: "Today’s medicines", slot: { morning: "Morning", noon: "Noon", evening: "Evening", night: "Night" }, none: "Nothing at this time", empty: "No medicine has been confirmed yet, so none is shown.",
        confirmed: "Only medicines your family has confirmed are shown.", written: "Written in", allergy: "Allergy on record", notRecorded: "Allergies not recorded. That does not mean none.",
        note: "Copied from the family’s documents. Not medical advice. Ask the doctor or pharmacist if anything is unclear.", print: "Print", back: "Back", label: "Language" },
  hi: { title: "आज की दवाइयाँ", slot: { morning: "सुबह", noon: "दोपहर", evening: "शाम", night: "रात" }, none: "इस समय कुछ नहीं", empty: "अभी कोई दवा पक्की नहीं हुई है, इसलिए कुछ नहीं दिखाया गया।",
        confirmed: "सिर्फ़ वही दवाइयाँ दिखती हैं जिन्हें आपके परिवार ने पक्का किया है।", written: "इसमें लिखा है", allergy: "दर्ज एलर्जी", notRecorded: "एलर्जी दर्ज नहीं है। इसका मतलब यह नहीं कि कोई एलर्जी नहीं है।",
        note: "परिवार के कागज़ों से लिया गया है। यह चिकित्सा सलाह नहीं है। कुछ समझ न आए तो डॉक्टर या फार्मासिस्ट से पूछें।", print: "प्रिंट करें", back: "वापस", label: "भाषा" },
  mr: { title: "आजची औषधे", slot: { morning: "सकाळी", noon: "दुपारी", evening: "संध्याकाळी", night: "रात्री" }, none: "यावेळी काही नाही", empty: "अजून कोणतेही औषध पक्के झालेले नाही, म्हणून काही दाखवले नाही.",
        confirmed: "फक्त कुटुंबाने पक्की केलेली औषधेच इथे दिसतात.", written: "यात लिहिले आहे", allergy: "नोंदलेली ऍलर्जी", notRecorded: "ऍलर्जी नोंदलेली नाही. याचा अर्थ ऍलर्जी नाही असा नाही.",
        note: "कुटुंबाच्या कागदपत्रांवरून घेतले आहे. हा वैद्यकीय सल्ला नाही. काही समजले नाही तर डॉक्टर किंवा फार्मासिस्टला विचारा.", print: "छापा", back: "मागे", label: "भाषा" },
};

// Fixed icons only. There are no pictures of medicines on purpose: a drawing of a pill could be mistaken for the real one.
function SlotIcon({ slot }: { slot: Slot }) {
  const common = { width: 56, height: 56, viewBox: "0 0 48 48", fill: "none", stroke: "currentColor", strokeWidth: 2.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  if (slot === "night") return <svg {...common}><path d="M36 27A15 15 0 0 1 21 12a15 15 0 1 0 15 15Z" /><path d="M34 8v6M31 11h6" /></svg>;
  const rays = <path d="M24 5v5M24 38v5M5 24h5M38 24h5M10.5 10.5l3.5 3.5M34 34l3.5 3.5M10.5 37.5 14 34M34 14l3.5-3.5" />;
  if (slot === "noon") return <svg {...common}><circle cx="24" cy="24" r="8" fill="currentColor" />{rays}</svg>;
  if (slot === "morning") return <svg {...common}><path d="M8 34h32M14 34a10 10 0 0 1 20 0" /><path d="M24 9v6M10 18l4 4M38 18l-4 4M5 26h4M39 26h4" /></svg>;
  return <svg {...common}><path d="M8 36h32M14 36a10 10 0 0 1 20 0" /><path d="M16 26l-3-3M32 26l3-3M24 20v-4" /><path d="M10 42h28" /></svg>;
}

function Schedule() {
  const { patients } = usePatients();
  const id = patients ? (patients.find((p) => p.id === readSelected())?.id ?? patients[0]?.id ?? null) : null;
  const [sheet, setSheet] = useState<FridgeSheet | null>(null);
  const [lang, setLang] = useState<Lang | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!id) return;
    api<FridgeSheet>(`/patients/${id}/fridge-sheet`).then(setSheet).catch((e) => setError(e instanceof ApiError ? e.detail || e.title : "Could not load the schedule"));
  }, [id]);

  if (error) return <div className="center-page"><div><h1 style={{ fontSize: 26 }}>We could not load the schedule</h1><p style={{ color: "var(--ink-2)", marginTop: 8 }}>{error}</p></div></div>;
  if (!sheet) return <div className="wrap" style={{ padding: "30px 0" }}><div className="skeleton" style={{ height: 320 }} aria-busy="true" /></div>;

  const l: Lang = lang ?? (sheet.language === "hi" || sheet.language === "mr" ? sheet.language : "en");
  const t = T[l];
  return (
    <div className="wrap fridge-wrap">
      <div className="no-print item-foot" style={{ padding: "18px 0" }}>
        <Link href="/app" className="btn btn-quiet btn-sm">← {t.back}</Link>
        <button className="btn btn-primary btn-sm" onClick={() => window.print()}>{t.print}</button>
        <span role="group" aria-label={t.label} className="item-foot" style={{ gap: 6 }}>
          {(["en", "hi", "mr"] as Lang[]).map((x) => <button key={x} className={x === l ? "btn btn-primary btn-sm" : "btn btn-quiet btn-sm"} aria-pressed={x === l} onClick={() => setLang(x)}>{x === "en" ? "English" : x === "hi" ? "हिन्दी" : "मराठी"}</button>)}
        </span>
      </div>
      <article className="psched on-paper" aria-label={t.title} lang={l}>
        <header className="fridge-head"><div><p className="eyebrow">{t.title}</p><h1>{sheet.patient}</h1></div><p className="eyebrow">CareSaathi · synthetic data</p></header>
        {sheet.allergy_state === "listed" && <p className="fridge-bad"><b>{t.allergy}:</b> {sheet.allergies.map((a) => a.substance + (a.reaction ? ` (${a.reaction})` : "")).join(", ")}</p>}
        {sheet.allergy_state === "not_recorded" && <p className="fridge-bad">{t.notRecorded}</p>}
        {sheet.medicines.length === 0 ? <p className="psched-empty">{t.empty}</p> : (
          <div className="psched-grid">
            {SLOTS.map((slot) => {
              const here = sheet.medicines.filter((m) => m.when[slot]);
              return (
                <section key={slot} className={`pslot ${slot}`} aria-labelledby={`ps-${slot}`}>
                  <div className="pslot-head"><SlotIcon slot={slot} /><h2 id={`ps-${slot}`}>{t.slot[slot]}</h2></div>
                  {here.length === 0 ? <p className="pslot-none">{t.none}</p> : (
                    <ul>{here.map((m) => (
                      <li key={m.title}><span className="pcount" aria-label={`${m.when[slot]}`}>{m.when[slot]}</span>
                        <span className="pname">{m.title}{m.detail ? <small>{m.detail}</small> : null}<small className="psrc">{t.written}: {m.source}</small></span></li>))}
                    </ul>)}
                </section>);
            })}
          </div>
        )}
        <footer className="fridge-foot">{t.confirmed} {t.note}</footer>
      </article>
    </div>
  );
}

export default function Page() {
  return <AppGate><Schedule /></AppGate>;
}
