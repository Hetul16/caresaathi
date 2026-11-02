"use client";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import type { TodayItem, TodayView } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { afterCommit } from "@/lib/defer";

type Lang = "en" | "hi" | "mr";

// Written for someone who may be ill, tired, or unable to read the screen. One job is on it: say whether the medicine due right now was
// taken. What is still to come, what is already done, and how they feel are each one line until they ask for them.
// Hindi and Marathi have not been reviewed by a native speaker yet (docs/10-hackathon-facts.md).
const T: Record<Lang, Record<string, string>> = {
  en: { now: "Take now", took: "I took it", not: "I did not take it", taken: "Taken", notTaken: "Not taken", listen: "Read this to me",
        nothing: "Nothing to take right now.", next: "Next", later: "Later today", done: "Finished today", medicines: "medicines",
        medicine: "medicine", feel: "How are you feeling?", pain: "0 means no pain. 10 means the most pain.",
        saved: "Saved. Your family can see it.", none: "Nothing is on your list for today.", err: "Could not save. Please try again." },
  hi: { now: "अभी लेनी है", took: "मैंने ले ली", not: "मैंने नहीं ली", taken: "ले ली", notTaken: "नहीं ली", listen: "पढ़कर सुनाएँ",
        nothing: "अभी कुछ नहीं लेना है।", next: "अगली", later: "आज बाद में", done: "आज हो गया", medicines: "दवाइयाँ",
        medicine: "दवा", feel: "आप कैसा महसूस कर रहे हैं?", pain: "0 यानी कोई दर्द नहीं। 10 यानी सबसे ज़्यादा दर्द।",
        saved: "सेव हो गया। आपका परिवार इसे देख सकता है।", none: "आज आपकी सूची में कुछ नहीं है।", err: "सेव नहीं हो सका। कृपया फिर कोशिश करें।" },
  mr: { now: "आता घ्यायची", took: "मी घेतली", not: "मी घेतली नाही", taken: "घेतली", notTaken: "घेतली नाही", listen: "वाचून दाखवा",
        nothing: "आत्ता काही घ्यायचे नाही.", next: "पुढची", later: "आज नंतर", done: "आज झाले", medicines: "औषधे",
        medicine: "औषध", feel: "तुम्हाला कसे वाटते आहे?", pain: "0 म्हणजे वेदना नाही. 10 म्हणजे सर्वात जास्त वेदना.",
        saved: "जतन झाले. तुमचे कुटुंब ते पाहू शकते.", none: "आज तुमच्या यादीत काही नाही.", err: "जतन झाले नाही. कृपया पुन्हा प्रयत्न करा." },
};
const SLOT: Record<Lang, Record<string, string>> = {
  en: { morning: "Morning", noon: "Noon", evening: "Evening", night: "Night" },
  hi: { morning: "सुबह", noon: "दोपहर", evening: "शाम", night: "रात" },
  mr: { morning: "सकाळी", noon: "दुपारी", evening: "संध्याकाळी", night: "रात्री" },
};

type Row = TodayItem & { slot: string; time: string };

export function ElderCheckin({ patientId, lang, speak }: { patientId: string; lang: Lang; speak?: (text: string) => void }) {
  const t = T[lang];
  const [v, setV] = useState<TodayView | null>(null);
  const [msg, setMsg] = useState("");
  const [open, setOpen] = useState({ later: false, done: false, feel: false });
  const toggle = (k: "later" | "done" | "feel") => setOpen((o) => ({ ...o, [k]: !o[k] }));
  const load = useCallback(async () => { try { setV(await api<TodayView>(`/patients/${patientId}/today`)); } catch { /* the rest of the screen still works */ } }, [patientId]);
  useEffect(() => { afterCommit(load); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);

  async function dose(item_key: string, slot: string, status: "taken" | "not_taken") {
    try { await api(`/patients/${patientId}/doses`, { method: "POST", json: { item_key, slot, status } }); setMsg(t.saved); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.detail || e.title : t.err); }
  }
  async function pain(n: number) {
    try { await api(`/patients/${patientId}/wellbeing`, { method: "POST", json: { pain: n } }); setMsg(t.saved); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.detail || e.title : t.err); }
  }
  if (!v) return null;

  const all: Row[] = v.slots.flatMap((sl) => sl.items.map((it) => ({ ...it, slot: sl.slot, time: sl.time })));
  const nowRows = all.filter((r) => r.status === "due" || r.status === "not_marked");
  const laterRows = all.filter((r) => r.status === "later");
  const doneRows = all.filter((r) => r.status === "taken" || r.status === "not_taken");
  const count = (n: number) => `${n} ${n === 1 ? t.medicine : t.medicines}`;
  const mixedSlots = new Set(nowRows.map((r) => r.slot)).size > 1;

  // The whole card in one sentence, so it can be heard instead of read.
  const readNow = () => speak?.([t.now, ...nowRows.map((r) => `${r.title}, ${r.units}`)].join(". "));

  const buttons = (r: Row) => (
    <div className="pcheck-acts">
      <button className="btn btn-primary pcheck-took" onClick={() => dose(r.item_key, r.slot, "taken")}><Icon name="check" /> {t.took}</button>
      <button className="btn btn-quiet pcheck-not" onClick={() => dose(r.item_key, r.slot, "not_taken")}>{t.not}</button>
    </div>
  );
  const name = (r: Row, when: boolean) => (
    <p className="pcheck-name">{r.title} <small>&times; {r.units}</small>{when && <small className="pcheck-when"> &middot; {SLOT[lang][r.slot]} {r.time}</small>}</p>
  );
  const fold = (k: "later" | "done" | "feel", icon: "clock" | "check" | "heart", label: string, tail?: ReactNode) => (
    <button className="pcheck-foldbtn" aria-expanded={open[k]} onClick={() => toggle(k)}>
      <Icon name={icon} /><span>{label}</span>{tail}<span className="pcheck-caret" aria-hidden="true">{open[k] ? "▴" : "▾"}</span>
    </button>
  );

  return (
    <section aria-labelledby="pcheck-h" className="pcheck">
      <h2 id="pcheck-h" className="sr-only">{t.now}</h2>
      {all.length === 0 && <p className="card card-pad pcheck-clear">{t.none}</p>}

      {nowRows.length > 0 ? (
        <div className="card card-pad pcheck-now">
          <div className="pcheck-head">
            <h3>{t.now}</h3>
            {speak && <button className="btn btn-quiet btn-sm" onClick={readNow}><Icon name="volume" /> {t.listen}</button>}
          </div>
          {nowRows.map((r) => <div key={r.item_key + r.slot} className="pcheck-row">{name(r, mixedSlots)}{buttons(r)}</div>)}
        </div>
      ) : all.length > 0 && (
        <p className="card card-pad pcheck-clear">
          <Icon name="check" /> {t.nothing}
          {laterRows.length > 0 && <small>{t.next}: {SLOT[lang][laterRows[0].slot]} {laterRows[0].time}</small>}
        </p>
      )}

      {/* Tapping moves the medicine out of this card and into "Finished today", which is a lot of change under a finger.
          The confirmation sits where the row was, not at the bottom of the screen. */}
      {msg && <p role="status" className="pcheck-msg">{msg}</p>}

      {laterRows.length > 0 && (
        <div className="pcheck-fold">
          {fold("later", "clock", `${t.later} · ${count(laterRows.length)}`)}
          {open.later && laterRows.map((r) => <div key={r.item_key + r.slot} className="pcheck-row">{name(r, true)}{buttons(r)}</div>)}
        </div>
      )}

      {doneRows.length > 0 && (
        <div className="pcheck-fold">
          {fold("done", "check", `${t.done} · ${count(doneRows.length)}`)}
          {open.done && doneRows.map((r) => (
            <p key={r.item_key + r.slot} className="pcheck-doneline">
              <span className={r.status === "taken" ? "pill pill-leaf" : "pill pill-rose"}>{r.status === "taken" ? t.taken : t.notTaken}</span>
              {r.title} <small>{r.marked_at}</small>
            </p>
          ))}
        </div>
      )}

      <div className="pcheck-fold">
        {fold("feel", "heart", t.feel, v.checkin?.pain != null ? <span className="pill">{v.checkin.pain}</span> : undefined)}
        {open.feel && (
          <div className="pcheck-pain">
            <p>{t.pain}</p>
            <div role="group" aria-label={t.feel}>
              {Array.from({ length: 11 }, (_, n) => (
                <button key={n} className={v.checkin?.pain === n ? "btn btn-primary" : "btn btn-quiet"} aria-pressed={v.checkin?.pain === n} onClick={() => pain(n)}>{n}</button>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
