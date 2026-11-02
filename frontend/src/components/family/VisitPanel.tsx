"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { MAX_SECONDS, useWavRecorder } from "@/lib/recorder";
import type { VisitDetail, VisitRow } from "@/lib/types";
import { Field } from "../auth/Field";
import { Icon } from "../Icon";
import { afterCommit } from "@/lib/defer";

const CONSENT_VERSION = "visit-recording-v1";
const ROLES = ["doctor", "patient", "family", "nurse", "other", "unknown"] as const;
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const errText = (e: unknown) => (e instanceof ApiError ? e.detail || e.title : "Something went wrong. Please try again.");

interface Script { id: string; title: string; language: string; experimental: boolean }

const STATUS: Record<VisitRow["status"], [string, string]> = {
  recording: ["pill pill-amber", "Waiting for the recording"], processing: ["pill pill-blue", "Reading"], needs_review: ["pill pill-amber", "Needs a look"],
  completed: ["pill pill-leaf", "Done"], failed: ["pill pill-rose", "Could not be read"], cancelled: ["pill", "Consent withdrawn"],
};

function useVisit(id: string | null) {
  // Held with the visit it belongs to, so opening a second visit cannot show the first one's transcript underneath
  // the new heading while the new one is still loading.
  const [got, setGot] = useState<{ id: string; visit: VisitDetail } | null>(null);
  const load = useCallback(async () => { if (id) setGot({ id, visit: await api<VisitDetail>(`/visits/${id}`) }); }, [id]);
  useEffect(() => {
    if (!id) return;
    let alive = true, timer = 0;
    const tick = async () => {
      try {
        const v = await api<VisitDetail>(`/visits/${id}`);
        if (!alive) return;
        setGot({ id, visit: v });
        if (v.status === "processing" || (v.status === "recording" && v.origin === "mock")) timer = window.setTimeout(tick, 1200);
      } catch { /* shown by the caller on the next action */ }
    };
    afterCommit(tick);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [id]);
  return { visit: got && got.id === id ? got.visit : null, reload: load };
}

export function VisitPanel({ patientId, canManage, onChange, toast }: { patientId: string; canManage: boolean; onChange: () => void; toast: (m: string) => void }) {
  const [rows, setRows] = useState<VisitRow[] | null>(null);
  const [mode, setMode] = useState<"list" | "consent" | "record">("list");
  const [openId, setOpenId] = useState<string | null>(null);
  const [visitId, setVisitId] = useState<string | null>(null);

  const loadRows = useCallback(async () => {
    try { setRows(await api<VisitRow[]>(`/patients/${patientId}/visits`)); } catch (e) { toast(errText(e)); }
  }, [patientId, toast]);
  useEffect(() => { afterCommit(loadRows); }, [loadRows]);

  if (mode === "consent") {
    return <ConsentStep patientId={patientId} onCancel={() => setMode("list")} toast={toast}
      onStarted={(id, mock) => { setVisitId(id); if (mock) { setOpenId(id); setMode("list"); loadRows(); onChange(); } else setMode("record"); }} />;
  }
  if (mode === "record" && visitId) {
    return <RecordStep visitId={visitId} toast={toast} onDone={() => { setOpenId(visitId); setMode("list"); loadRows(); }} />;
  }
  if (openId) {
    return <VisitDetailView id={openId} canManage={canManage} toast={toast} onBack={() => { setOpenId(null); loadRows(); }} onChange={onChange} />;
  }

  return (
    <div className="stack">
      <div className="section-title"><h2>Doctor visits</h2><span className="pill">{rows?.length ?? 0}</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        Record a visit (with everyone&apos;s consent on screen) and CareSaathi writes down what the doctor said. Nothing from a visit enters the care
        plan until a named family member confirms it, and every change shows the doctor&apos;s exact words.
      </p>
      <div className="item-foot"><button className="btn btn-primary" onClick={() => setMode("consent")}><Icon name="mic" /> Start a visit</button></div>
      {rows && rows.length === 0 && <p className="card card-pad">No visits yet.</p>}
      {rows?.map((v) => (
        <button key={v.id} className="card item" style={{ textAlign: "left", cursor: "pointer" }} onClick={() => setOpenId(v.id)}>
          <div className="item-top">
            <div>
              <p className="eyebrow">{v.origin === "mock" ? "Mock visit · scripted" : "Recorded visit"}</p>
              <h3 style={{ marginTop: 4 }}>{v.doctor_name ?? "Doctor visit"}</h3>
              <p className="detail">{when(v.started_at)}{v.duration_ms ? ` · ${mmss(Math.round(v.duration_ms / 1000))}` : ""}</p>
            </div>
            <span className={STATUS[v.status][0]}>{STATUS[v.status][1]}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

// ---- step 1: consent, on screen, before anything is recorded --------------------------------------------------------------------------------
function ConsentStep({ patientId, onStarted, onCancel, toast }: { patientId: string; onStarted: (id: string, mock: boolean) => void; onCancel: () => void; toast: (m: string) => void }) {
  const [pName, setPName] = useState("");
  const [behalf, setBehalf] = useState(true);
  const [pAgree, setPAgree] = useState(false);
  const [dName, setDName] = useState("");
  const [dAgree, setDAgree] = useState(false);
  const [hospital, setHospital] = useState("");
  const [lang, setLang] = useState<"hi" | "mr" | "en">("hi");
  const [scripts, setScripts] = useState<Script[]>([]);
  const [script, setScript] = useState("V1");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api<Script[]>("/visit-scripts").then(setScripts).catch(() => setScripts([])); }, []);

  const ready = pAgree && dAgree && pName.trim().length > 0 && dName.trim().length > 0;
  async function go(mock: boolean) {
    if (!ready) return;
    setBusy(true);
    const body = { patient_consent: { agreed: pAgree, given_by_name: pName.trim(), on_behalf_of_patient: behalf }, doctor_consent: { agreed: dAgree, given_by_name: dName.trim() },
      doctor_name: dName.trim(), hospital: hospital.trim() || null, language_hint: lang, consent_text_version: CONSENT_VERSION };
    try {
      const r = mock
        ? await api<{ id: string }>(`/patients/${patientId}/visits/mock`, { method: "POST", json: { ...body, script_id: script } })
        : await api<{ id: string }>(`/patients/${patientId}/visits`, { method: "POST", json: body });
      onStarted(r.id, mock);
    } catch (e) { toast(errText(e)); } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      <div className="section-title"><h2>Before we record</h2></div>
      <div className="card card-pad stack" role="group" aria-labelledby="consent-h">
        <h3 id="consent-h" style={{ fontSize: 22 }}>Please read this together</h3>
        <ul style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 6, color: "var(--ink-2)" }}>
          <li>Everyone who speaks agrees to be recorded.</li>
          <li>The audio is used only to write down what the doctor said, and is deleted as soon as that is done.</li>
          <li>You can withdraw consent at any time. The recording and its words are then removed.</li>
          <li>Nothing from the visit enters the care plan until a named family member confirms it.</li>
          <li>This build is for synthetic data only. Please do not record a real consultation.</li>
        </ul>
        <label className="check"><input type="checkbox" checked={pAgree} onChange={(e) => setPAgree(e.target.checked)} />
          <span>The patient agrees to this recording{behalf ? ", and I am agreeing on their behalf" : ""}.</span></label>
        <Field label="Name of the person agreeing for the patient side" value={pName} onChange={setPName} placeholder="Priya Kulkarni" />
        <label className="check"><input type="checkbox" checked={behalf} onChange={(e) => setBehalf(e.target.checked)} /><span>I am agreeing on the patient&apos;s behalf.</span></label>
        <label className="check"><input type="checkbox" checked={dAgree} onChange={(e) => setDAgree(e.target.checked)} /><span>The doctor agrees to this recording.</span></label>
        <Field label="Doctor's name" value={dName} onChange={setDName} placeholder="Dr. Joshi" />
        <Field label="Hospital or clinic (optional)" value={hospital} onChange={setHospital} />
        <fieldset className="lang-pick"><legend>Language mostly spoken</legend>
          <div className="seg">{(["hi", "mr", "en"] as const).map((l) => <button key={l} type="button" aria-pressed={lang === l} onClick={() => setLang(l)}>{l === "hi" ? "हिन्दी" : l === "mr" ? "मराठी" : "English"}</button>)}</div>
        </fieldset>
        <div className="item-foot">
          <button className="btn btn-primary" disabled={!ready || busy} onClick={() => go(false)}><Icon name="mic" /> Agree and continue to recording</button>
          <button className="btn btn-quiet" onClick={onCancel}>Cancel</button>
        </div>
      </div>

      {scripts.length > 0 && (
        <div className="card card-pad stack">
          <h3 style={{ fontSize: 20 }}>No audio? Replay a scripted mock visit</h3>
          <p style={{ color: "var(--ink-2)" }}>A fictional conversation, played through the same reading steps. It is labeled as a mock everywhere. Consent above is still required.</p>
          <label className="select"><span className="sr-only">Script</span>
            <select value={script} onChange={(e) => setScript(e.target.value)}>
              {scripts.map((s) => <option key={s.id} value={s.id}>{s.id}: {s.title}{s.experimental ? " (language not verified)" : ""}</option>)}
            </select></label>
          <div className="item-foot"><button className="btn btn-quiet" disabled={!ready || busy} onClick={() => go(true)}><Icon name="sparkle" /> Replay this mock visit</button></div>
        </div>
      )}
    </div>
  );
}

// ---- step 2: record, then send once --------------------------------------------------------------------------------------------------------------
function RecordStep({ visitId, onDone, toast }: { visitId: string; onDone: () => void; toast: (m: string) => void }) {
  const rec = useWavRecorder();
  const [busy, setBusy] = useState(false);
  const stopped = useRef(false);

  const finish = useCallback(async () => {
    if (stopped.current) return;
    stopped.current = true;
    const wav = rec.stop();
    if (!wav) { toast("Nothing was recorded."); stopped.current = false; return; }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", wav, "visit.wav");
      await api(`/visits/${visitId}/audio`, { method: "POST", body: form });
      onDone();
    } catch (e) { toast(errText(e)); stopped.current = false; } finally { setBusy(false); }
  }, [rec, visitId, onDone, toast]);

  // Ten minutes reached: stop and send, after this render rather than inside it.
  useEffect(() => { if (rec.state === "recording" && rec.seconds >= MAX_SECONDS) afterCommit(finish); }, [rec.state, rec.seconds, finish]);

  return (
    <div className="stack">
      <div className="section-title"><h2>Recording</h2></div>
      <div className="card card-pad stack" style={{ justifyItems: "center", textAlign: "center" }}>
        <div className="orb-wrap" data-state={rec.state === "recording" ? "listening" : "idle"} style={{ width: 200 }}>
          <span className="orb-ring" /><span className="orb-ring" /><span className="orb-ring" />
          <button type="button" className="orb" style={{ ["--level" as string]: rec.level }} aria-label={rec.state === "recording" ? "Stop recording" : "Start recording"}
            onClick={() => (rec.state === "recording" ? finish() : rec.start())} disabled={busy}><Icon name="mic" /></button>
        </div>
        <p style={{ fontSize: 28, fontFamily: "var(--font-display)", fontWeight: 700 }}>{rec.state === "recording" ? mmss(rec.seconds) : busy ? "Sending…" : "Ready"}</p>
        <p style={{ color: "var(--ink-2)", maxWidth: "52ch" }}>
          {rec.state === "recording" ? "Recording. Tap the button again when the visit ends. The audio stays in this browser until you stop."
            : rec.state === "denied" ? "The microphone is blocked. Allow it in the browser's address bar and try again."
            : rec.state === "unsupported" ? "This browser cannot record audio here. Try Chrome or Edge on a secure (https) page."
            : "Tap the button to begin. Maximum ten minutes per recording."}
        </p>
        {rec.state === "recording" && <button className="btn btn-primary" onClick={finish} disabled={busy}>Stop and send</button>}
      </div>
    </div>
  );
}

// ---- step 3: the result -----------------------------------------------------------------------------------------------------------------------------
function VisitDetailView({ id, canManage, onBack, onChange, toast }: { id: string; canManage: boolean; onBack: () => void; onChange: () => void; toast: (m: string) => void }) {
  const { visit: v, reload } = useVisit(id);
  const [roles, setRoles] = useState<Record<string, { role: string; name: string }>>({});
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);
  // Seeds the editable speaker form once the visit arrives. Deferred so the arrival and the seeding are two passes.
  useEffect(() => {
    if (v) afterCommit(() => setRoles(Object.fromEntries(v.speakers.map((s) => [s.label, { role: s.role, name: s.name ?? "" }]))));
  }, [v?.speakers.map((s) => `${s.label}${s.role}${s.name}`).join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (v && v.status !== "processing") onChange(); }, [v?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!v) return <div className="skeleton" style={{ height: 220 }} aria-busy="true" />;
  const roleOf = (label: string) => roles[label]?.role ?? "unknown";

  async function saveSpeakers() {
    try {
      await api(`/visits/${id}/speakers`, { method: "PUT", json: { speakers: Object.entries(roles).map(([label, r]) => ({ label, role: r.role, name: r.name.trim() || null })) } });
      toast("Saved. Who said what is now confirmed by you."); reload();
    } catch (e) { toast(errText(e)); }
  }
  async function revoke(cid: string) {
    try { await api(`/visits/${id}/consents/${cid}/revoke`, { method: "POST" }); toast("Consent withdrawn. The recording and its words were removed."); setConfirmRevoke(null); reload(); onChange(); }
    catch (e) { toast(errText(e)); }
  }
  async function retry() { try { await api(`/visits/${id}/retry`, { method: "POST" }); toast("Trying again."); reload(); } catch (e) { toast(errText(e)); } }

  return (
    <div className="stack">
      <div className="item-foot"><button className="btn btn-quiet btn-sm" onClick={onBack}>← All visits</button></div>
      <div className="card card-pad stack">
        <div className="item-top">
          <div>
            <p className="eyebrow">{v.origin === "mock" ? "Mock visit · a scripted conversation, not a real consultation" : "Recorded visit"}</p>
            <h3 style={{ fontSize: 26, marginTop: 4 }}>{v.doctor_name ?? "Doctor visit"}</h3>
            <p className="detail">{when(v.started_at)}{v.hospital ? ` · ${v.hospital}` : ""}</p>
          </div>
          <span className={STATUS[v.status][0]}>{STATUS[v.status][1]}</span>
        </div>
        {v.status === "processing" && <div className="skeleton" style={{ height: 14, width: "60%" }} aria-busy="true" />}
        {v.failure_note && (
          <div className="notice"><Icon name="alert" /><div>{v.failure_note}{v.origin === "recording" && <div style={{ marginTop: 8 }}><button className="btn btn-quiet btn-sm" onClick={retry}>Try again</button></div>}</div></div>
        )}
        <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>
          {v.origin === "recording" ? (v.audio_deleted ? "The audio has been deleted. Only the words below were kept." : "The audio will be deleted once it has been read.") : "No audio exists for a mock visit."}
        </p>
      </div>

      {v.changes.length > 0 && (
        <div className="stack">
          <div className="section-title"><h2>What the doctor said</h2><span className="pill pill-marigold">{v.changes.filter((c) => c.status === "pending").length} waiting for you</span></div>
          <p style={{ color: "var(--ink-2)" }}>These are waiting on the Overview tab for a named family member to confirm. Each one quotes the doctor.</p>
          {v.changes.map((c) => (
            <article key={c.id} className="card item">
              <div className="item-top"><div><p className="eyebrow">{c.change_type === "changed" ? "Changed" : c.change_type === "new" ? "New" : c.change_type === "stopped" ? "Stopped" : "Noted"}</p><h3 style={{ marginTop: 4 }}>{c.title}</h3></div>
                <span className={c.status === "pending" ? "pill pill-marigold" : c.status === "applied" ? "pill pill-leaf" : "pill"}>{c.status === "pending" ? "Waiting for you" : c.status === "applied" ? "Added to the plan" : c.status}</span></div>
              <blockquote style={{ margin: 0, borderLeft: "3px solid var(--signal)", paddingLeft: 12, fontSize: 18 }}>“{c.quote}”</blockquote>
            </article>
          ))}
        </div>
      )}

      {v.unclear.length > 0 && (
        <div className="notice" role="note"><Icon name="help" /><div><strong>Please listen to this part again.</strong>
          {v.unclear.map((u, i) => <p key={i} style={{ marginTop: 4 }}>{u.note}</p>)}
          <p style={{ marginTop: 4 }}>Nothing was guessed or added to the plan from it.</p></div></div>
      )}

      {v.follow_ups.length > 0 && (
        <div className="card card-pad stack"><h3 style={{ fontSize: 20 }}>Follow-ups mentioned</h3>
          {v.follow_ups.map((f, i) => <p key={i}><strong>{f.what}</strong>: “{f.due_text}”{f.due_date ? `, which works out to ${new Date(f.due_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}` : ", no date could be worked out"} <span className="pill">{f.status}</span></p>)}
          <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>Confirm these on the Tracker tab.</p></div>
      )}

      {v.speakers.length > 0 && (
        <div className="card card-pad stack">
          <h3 style={{ fontSize: 20 }}>Who is who</h3>
          <p style={{ color: "var(--ink-2)" }}>The reader labels voices A, B, C and suggests who they are. Please check, and correct if needed.</p>
          {v.speakers.map((s) => (
            <div key={s.label} style={{ display: "grid", gridTemplateColumns: "auto 1fr 1fr", gap: 10, alignItems: "center" }}>
              <span className="pill">Voice {s.label}</span>
              <label className="select"><span className="sr-only">Role of voice {s.label}</span>
                <select value={roleOf(s.label)} onChange={(e) => setRoles({ ...roles, [s.label]: { ...(roles[s.label] ?? { name: "" }), role: e.target.value } })}>{ROLES.map((r) => <option key={r} value={r}>{r}</option>)}</select></label>
              <input className="select" style={{ minHeight: 46, padding: "0 12px", borderRadius: 12, border: "1px solid var(--line)", background: "var(--card)", color: "var(--ink)" }} aria-label={`Name of voice ${s.label}`}
                placeholder="Name (optional)" value={roles[s.label]?.name ?? ""} onChange={(e) => setRoles({ ...roles, [s.label]: { ...(roles[s.label] ?? { role: "unknown" }), name: e.target.value } })} />
            </div>
          ))}
          <div className="item-foot"><button className="btn btn-quiet btn-sm" onClick={saveSpeakers}><Icon name="check" /> Confirm who is who</button>
            {v.speakers.every((s) => s.confirmed) && <span className="pill pill-leaf">Confirmed by a family member</span>}</div>
        </div>
      )}

      {v.transcript_hidden ? (
        <p className="card card-pad" style={{ color: "var(--ink-2)" }}>The transcript is visible only to family members who were given access to recordings.</p>
      ) : v.segments.length > 0 && (
        <div className="card card-pad stack">
          <h3 style={{ fontSize: 20 }}>Transcript</h3>
          {v.segments.map((g) => (
            <p key={g.id} style={{ display: "grid", gridTemplateColumns: "72px 1fr", gap: 10 }}>
              <span className="eyebrow" style={{ paddingTop: 3 }}>{g.role !== "unknown" ? g.role : `Voice ${g.speaker}`}<br />{mmss(Math.round(g.start_ms / 1000))}</span>
              <span lang={v.language_hint === "unknown" ? undefined : v.language_hint}>{g.text}</span>
            </p>
          ))}
        </div>
      )}

      <div className="card card-pad stack">
        <h3 style={{ fontSize: 20 }}>Consent</h3>
        {v.consents.map((c) => (
          <div key={c.id} className="item-top" style={{ alignItems: "center" }}>
            <p><strong>{c.role === "patient" ? "Patient side" : "Doctor"}</strong>: {c.given_by}, {when(c.granted_at)}{c.revoked_at ? <span className="pill pill-rose" style={{ marginLeft: 8 }}>Withdrawn</span> : null}</p>
            {canManage && !c.revoked_at && (confirmRevoke === c.id
              ? <span className="item-foot"><button className="btn btn-danger btn-sm" onClick={() => revoke(c.id)}>Yes, remove the recording and its words</button><button className="btn btn-quiet btn-sm" onClick={() => setConfirmRevoke(null)}>Keep</button></span>
              : <button className="btn btn-quiet btn-sm" onClick={() => setConfirmRevoke(c.id)}>Withdraw consent</button>)}
          </div>
        ))}
      </div>
    </div>
  );
}
