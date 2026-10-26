"use client";
import { useEffect, useRef, useState } from "react";
import { Icon } from "../Icon";

const STAGES = [
  { id: "upload", label: "Upload", title: "A discharge summary arrives" },
  { id: "read", label: "Read", title: "Every line is checked against the page" },
  { id: "plan", label: "Plan", title: "A care plan where every item has a source" },
  { id: "safety", label: "Safety", title: "A conflict is caught by code, not guessed" },
  { id: "voice", label: "Voice", title: "Explained aloud, in the patient’s language" },
] as const;

const LINES = [
  "CITY HOSPITAL, PUNE · DISCHARGE SUMMARY",
  "Patient: Ramesh Kulkarni, 74 y",
  "Allergic to penicillin (rash)",
  "Tab Metformin 500 mg 1-0-1 after food",
  "Tab Amlodipine 5 mg 1-0-0",
  "Tab Amoxicillin 500 mg 1-0-1 x 5 days",
  "Go to the emergency immediately if chest pain",
  "Review in two weeks",
];
const FOUND = [2, 3, 4, 5, 6]; // zero-based lines that become plan items
const CAPTIONS = {
  hi: "मेटफॉर्मिन 500 मिलीग्राम। सुबह एक गोली, शाम को एक गोली। जैसा आपके डॉक्टर ने लिखा है।",
  mr: "मेटफॉर्मिन ५०० मिलिग्रॅम. सकाळी एक गोळी, संध्याकाळी एक गोळी. तुमच्या डॉक्टरांनी लिहिल्याप्रमाणे.",
} as const;

function useTyped(text: string, active: boolean) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!active) { setN(0); return; }
    setN(0);
    const id = setInterval(() => setN((v) => (v >= text.length ? v : v + 1)), 34);
    return () => clearInterval(id);
  }, [text, active]);
  return text.slice(0, n);
}

export function StoryDemo() {
  const [stage, setStage] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [lang, setLang] = useState<"hi" | "mr">("hi");
  const root = useRef<HTMLDivElement>(null);
  const typed = useTyped(CAPTIONS[lang], stage === 4);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  useEffect(() => {
    if (paused || reduced) return;
    const id = setTimeout(() => setStage((s) => (s + 1) % STAGES.length), stage === 4 ? 7000 : 3800);
    return () => clearTimeout(id);
  }, [stage, paused, reduced]);

  const lit = stage >= 1;
  const danger = stage === 3;

  return (
    <div
      ref={root}
      className="story"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      role="group"
      aria-roledescription="interactive demonstration"
      aria-label="How CareSaathi turns a document into a sourced care plan"
    >
      <div className="story-head">
        <div className="story-dots" aria-hidden="true"><i /><i /><i /></div>
        <p aria-live="polite" className="story-title">{STAGES[stage].title}</p>
        <span className="story-tag">Synthetic data</span>
      </div>

      <div className="story-body">
        <div className="story-paper" data-stage={stage}>
          <div className="scan" aria-hidden="true" />
          {LINES.map((ln, i) => {
            const isFound = FOUND.includes(i);
            const isRed = danger && (i === 2 || i === 5);
            const cls = ["ln-row", lit && isFound ? "found" : "", isRed ? "danger" : ""].join(" ");
            return (
              <div key={i} className={cls} style={{ ["--d" as string]: `${FOUND.indexOf(i) * 220 + 200}ms` }}>
                <span className="n">{i + 1}</span>
                <span className="t">{ln}</span>
                {lit && isFound && !danger && <span className="tick" aria-hidden="true"><Icon name="check" /></span>}
              </div>
            );
          })}
          <p className="paper-cap">Document · page 1 of 1</p>
        </div>

        <div className="story-out" data-stage={stage}>
          {stage === 0 && (
            <div className="out-pane shimmer-pane" key="s0">
              <p className="eyebrow">Reading the document</p>
              {[88, 64, 92, 52].map((w, i) => <div key={i} className="shim" style={{ width: `${w}%`, animationDelay: `${i * 120}ms` }} />)}
            </div>
          )}
          {stage === 1 && (
            <div className="out-pane" key="s1">
              <p className="eyebrow">Quote check</p>
              {FOUND.map((i, k) => (
                <div className="check-row" key={i} style={{ animationDelay: `${k * 220 + 300}ms` }}>
                  <Icon name="check" />
                  <span>found on page 1, line {i + 1}</span>
                </div>
              ))}
              <p className="out-note">A line that cannot be found on the page is dropped, never applied.</p>
            </div>
          )}
          {stage === 2 && (
            <div className="out-pane" key="s2">
              <p className="eyebrow">Care plan</p>
              {[["Metformin 500 mg", "1-0-1 · after food", "p.1 line 4"], ["Amlodipine 5 mg", "1-0-0", "p.1 line 5"], ["Chest pain: go to the emergency", "from the written instruction", "p.1 line 7"]].map(([a, b, c], k) => (
                <div className="mini-item" key={a} style={{ animationDelay: `${k * 160}ms` }}>
                  <div><strong>{a}</strong><span>{b}</span></div>
                  <em className="chip-src"><Icon name="quote" />{c}</em>
                </div>
              ))}
            </div>
          )}
          {stage === 3 && (
            <div className="out-pane" key="s3">
              <div className="alert-card">
                <p className="eyebrow">Possible allergy conflict</p>
                <h4>Amoxicillin 500 mg <span>↔</span> Penicillin allergy</h4>
                <p>A match in our reference list. Not a medical judgement.</p>
                <div className="q"><b>Question for the doctor</b>Dr. Joshi, could you confirm whether this is intended?</div>
                <p className="out-note" style={{ marginTop: 10 }}>Matched in code against a vetted list. The model only worded the question.</p>
              </div>
            </div>
          )}
          {stage === 4 && (
            <div className="out-pane voice-pane" key="s4">
              <div className="mini-orb"><span /><span /><span /><i><Icon name="volume" /></i></div>
              <div className="seg seg-sm" role="group" aria-label="Language of the spoken reply">
                <button type="button" aria-pressed={lang === "hi"} onClick={() => setLang("hi")}>हिन्दी</button>
                <button type="button" aria-pressed={lang === "mr"} onClick={() => setLang("mr")}>मराठी</button>
              </div>
              <p className="caption" lang={lang} aria-live="off">{typed}<span className="caret" aria-hidden="true" /></p>
            </div>
          )}
        </div>
      </div>

      <div className="story-steps" role="tablist" aria-label="Demonstration steps">
        {STAGES.map((s, i) => (
          <button key={s.id} role="tab" aria-selected={stage === i} className={stage === i ? "on" : ""} onClick={() => { setStage(i); }}>
            <span className="bar"><span style={stage === i && !paused && !reduced ? { animationDuration: i === 4 ? "7s" : "3.8s" } : undefined} /></span>
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
