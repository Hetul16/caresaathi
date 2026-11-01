"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { TodayView } from "@/lib/types";
import { Icon } from "@/components/Icon";

type Lang = "en" | "hi" | "mr";
// Fixed words. Hindi and Marathi have not been reviewed by a native speaker yet (docs/10-hackathon-facts.md).
const T: Record<Lang, { title: string; took: string; not: string; taken: string; notTaken: string; later: string; pain: string; scale: string; saved: string; none: string; note: string; err: string; listen: string }> = {
  en: { title: "Today", took: "I took it", not: "I did not take it", taken: "Taken", notTaken: "Marked not taken", later: "Later today", pain: "How is your pain today?", scale: "0 means no pain. 10 means the most pain.", saved: "Saved. Your family can see it.",
        none: "Nothing is on your list for today.", note: "Your family will see what you tap.", err: "Could not save. Please try again.", listen: "Listen" },
  hi: { title: "आज", took: "मैंने ले ली", not: "मैंने नहीं ली", taken: "ले ली", notTaken: "नहीं ली", later: "आज बाद में", pain: "आज दर्द कैसा है?", scale: "0 यानी कोई दर्द नहीं। 10 यानी सबसे ज़्यादा दर्द।", saved: "सेव हो गया। आपका परिवार इसे देख सकता है।",
        none: "आज आपकी सूची में कुछ नहीं है।", note: "आप जो दबाते हैं, आपका परिवार उसे देखता है।", err: "सेव नहीं हो सका। कृपया फिर कोशिश करें।", listen: "सुनें" },
  mr: { title: "आज", took: "मी घेतली", not: "मी घेतली नाही", taken: "घेतली", notTaken: "घेतली नाही", later: "आज नंतर", pain: "आज वेदना कशी आहे?", scale: "0 म्हणजे वेदना नाही. 10 म्हणजे सर्वात जास्त वेदना.", saved: "जतन झाले. तुमचे कुटुंब ते पाहू शकते.",
        none: "आज तुमच्या यादीत काही नाही.", note: "तुम्ही जे दाबता ते तुमचे कुटुंब पाहते.", err: "जतन झाले नाही. कृपया पुन्हा प्रयत्न करा.", listen: "ऐका" },
};
const SLOT: Record<Lang, Record<string, string>> = {
  en: { morning: "Morning", noon: "Noon", evening: "Evening", night: "Night" },
  hi: { morning: "सुबह", noon: "दोपहर", evening: "शाम", night: "रात" },
  mr: { morning: "सकाळी", noon: "दुपारी", evening: "संध्याकाळी", night: "रात्री" },
};

// The elder's check-in: tap each medicine as taken or not, and tap a pain number. Everything is recorded with the family's signed-in session
// and shown to the family. Nothing here says what a missed dose means.
export function ElderCheckin({ patientId, lang, speak }: { patientId: string; lang: Lang; speak?: (text: string) => void }) {
  const t = T[lang];
  const [v, setV] = useState<TodayView | null>(null);
  const [msg, setMsg] = useState("");
  const load = useCallback(async () => { try { setV(await api<TodayView>(`/patients/${patientId}/today`)); } catch { /* the rest of the screen still works */ } }, [patientId]);
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);

  async function dose(item_key: string, slot: string, status: "taken" | "not_taken") {
    try { await api(`/patients/${patientId}/doses`, { method: "POST", json: { item_key, slot, status } }); setMsg(t.saved); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.detail || e.title : t.err); }
  }
  async function pain(n: number) {
    try { await api(`/patients/${patientId}/wellbeing`, { method: "POST", json: { pain: n } }); setMsg(t.saved); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.detail || e.title : t.err); }
  }
  if (!v) return null;
  const spoken = (slot: string, title: string, units: number) => `${SLOT[lang][slot]}: ${title}, ${units}`;

  return (
    <section aria-labelledby="ec-h" style={{ maxWidth: 720, margin: "0 auto 28px", display: "grid", gap: 14 }}>
      <h2 id="ec-h" className="elder-title" style={{ margin: 0 }}>{t.title}</h2>
      {v.slots.length === 0 && <p className="card card-pad" style={{ fontSize: 20 }}>{t.none}</p>}
      {v.slots.map((sl) => (
        <div key={sl.slot} className="card card-pad" style={{ display: "grid", gap: 12 }}>
          <h3 style={{ fontSize: 26, margin: 0 }}>{SLOT[lang][sl.slot]} <small style={{ color: "var(--ink-3)", fontSize: 16 }}>{sl.time}</small></h3>
          {sl.items.map((it) => (
            <div key={it.item_key} style={{ display: "grid", gap: 8 }}>
              <p style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>{it.title} <small style={{ fontWeight: 400, color: "var(--ink-2)" }}>× {it.units}</small></p>
              {it.status === "taken" && <p className="pill pill-leaf" style={{ justifySelf: "start", fontSize: 18 }}><Icon name="check" /> {t.taken} {it.marked_at}</p>}
              {it.status === "not_taken" && <p className="pill pill-rose" style={{ justifySelf: "start", fontSize: 18 }}>{t.notTaken}</p>}
              {it.status === "later" && <p className="pill" style={{ justifySelf: "start", fontSize: 18 }}>{t.later}</p>}
              {(it.status === "due" || it.status === "not_marked") && (
                <div className="item-foot" style={{ gap: 10 }}>
                  <button className="btn btn-primary" style={{ minHeight: 64, fontSize: 22, flex: 1 }} onClick={() => dose(it.item_key, sl.slot, "taken")}><Icon name="check" /> {t.took}</button>
                  <button className="btn btn-quiet" style={{ minHeight: 64, fontSize: 18 }} onClick={() => dose(it.item_key, sl.slot, "not_taken")}>{t.not}</button>
                </div>
              )}
              {speak && <button className="btn btn-quiet" style={{ justifySelf: "start", minHeight: 44 }} onClick={() => speak(spoken(sl.slot, it.title, it.units))}
                                aria-label={`${t.listen}: ${it.title}`}><Icon name="volume" /> {t.listen}</button>}
            </div>
          ))}
        </div>
      ))}

      <div className="card card-pad" style={{ display: "grid", gap: 10 }}>
        <h3 style={{ fontSize: 26, margin: 0 }}>{t.pain}</h3>
        <p style={{ color: "var(--ink-2)", margin: 0 }}>{t.scale}</p>
        <div role="group" aria-label={t.pain} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(58px, 1fr))", gap: 8 }}>
          {Array.from({ length: 11 }, (_, n) => (
            <button key={n} className={v.checkin?.pain === n ? "btn btn-primary" : "btn btn-quiet"} style={{ minHeight: 64, fontSize: 24 }} aria-pressed={v.checkin?.pain === n} onClick={() => pain(n)}>{n}</button>
          ))}
        </div>
      </div>
      <p role="status" style={{ color: "var(--ink-2)", fontSize: 18, margin: 0 }}>{msg || t.note}</p>
    </section>
  );
}
