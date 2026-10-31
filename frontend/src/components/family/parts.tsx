"use client";
import { useCallback, useState } from "react";
import type { Allergy, AllergyState, ApprovalAction, DuplicateGroup, Explanation, OmissionFlag, OpenConflict, PendingChange, PlanItem, TimelineEvent } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { Icon, type IconName } from "../Icon";
import { SourceChip } from "../Source";
import { useSpeech } from "../VoiceOrb";
import { speechLocale } from "@/lib/i18n";

export function AllergyBanner({ state, items, reviewed }: { state: AllergyState; items: Allergy[]; reviewed: boolean }) {
  const { t } = useI18n();
  // The three states are rendered from the effective view only. An empty list is never "none".
  if (state === "listed") {
    return (
      <section className="banner banner-listed" aria-label={t("allergies")}>
        <span className="banner-ic"><Icon name="alert" /></span>
        <div>
          <h2>{t("allergies")}: {items.map((a) => a.substance).join(", ")}</h2>
          <div className="stack" style={{ marginTop: 8 }}>
            {items.map((a) => (
              <div key={a.allergy_key} className="item-foot">
                <span>{a.reaction ?? "Reaction not recorded"}</span>
                <span className="pill pill-rose">{a.severity}</span>
                <SourceChip source={a.source} />
              </div>
            ))}
          </div>
          {!reviewed && (
            <p className="detail" style={{ color: "var(--ink-2)", fontSize: 14.5, marginTop: 8 }}>
              Drug-family reference list not yet reviewed by a pharmacist. Synthetic data only.
            </p>
          )}
        </div>
      </section>
    );
  }
  if (state === "no_known_allergies") {
    return (
      <section className="banner banner-none">
        <span className="banner-ic"><Icon name="shield" /></span>
        <div><h2>{t("allergyNone")}</h2></div>
      </section>
    );
  }
  return (
    <section className="banner banner-unknown">
      <span className="banner-ic"><Icon name="help" /></span>
      <div>
        <h2>{t("allergyNotRecorded")}</h2>
        <p>Ask the doctor and add it as soon as it is known. Not recorded does not mean none.</p>
      </div>
    </section>
  );
}

export function ConflictCard({ c, onAsk, onAck, askLabel = "Ask the doctor", note = "Nothing is sent until you approve it." }:
  { c: OpenConflict; onAsk: () => void; onAck?: () => void; askLabel?: string; note?: string }) {
  return (
    <article className="card conflict" role="alert">
      <div className="item-top">
        <div>
          <p className="eyebrow" style={{ color: "var(--rose)" }}>Possible allergy conflict · {c.match.replace("_", " ")} match</p>
          <h3 style={{ fontSize: 24, marginTop: 4 }}>{c.medicine}</h3>
        </div>
        <span className="pill pill-rose"><Icon name="alert" className="icon" /> Open</span>
      </div>
      <p>{c.flag}</p>
      {c.basis && (
        <details className="basis">
          <summary>{c.basis.confirmed ? `Why: both are ${c.basis.atc_group} in the WHO ATC classification` : "Why: our own reference list, not confirmed"}</summary>
          <p>{c.basis.text}</p>
          {c.basis.source && <p className="basis-src">{c.basis.source}{c.basis.checked_on ? ` · checked ${c.basis.checked_on}` : ""}</p>}
        </details>
      )}
      <div className="question-box">{c.doctor_question}</div>
      <div className="item-foot">
        <button className="btn btn-primary btn-sm" onClick={onAsk}><Icon name={onAck ? "copy" : "stethoscope"} /> {askLabel}</button>
        {onAck && <button className="btn btn-quiet btn-sm" onClick={onAck}><Icon name="check" /> I have seen this</button>}
        <span style={{ color: "var(--ink-3)", fontSize: 14.5 }}>{note}</span>
      </div>
    </article>
  );
}

export function OmissionCard({ o, onAsk, onState }: { o: OmissionFlag; onAsk: () => void; onState?: (s: "asked" | "resolved") => void }) {
  return (
    <article className="card conflict" style={{ borderLeftColor: "var(--amber)" }}>
      <div className="item-top">
        <div>
          <p className="eyebrow" style={{ color: "var(--amber)" }}>On the earlier list, not on the new one</p>
          <h3 style={{ fontSize: 24, marginTop: 4 }}>{o.medicine}</h3>
        </div>
        <span className="pill pill-amber">Gap between documents</span>
      </div>
      <div className="grid-2">
        <div><p className="eyebrow">Earlier</p><div style={{ marginTop: 6 }}><SourceChip source={o.previous_source} /></div></div>
        <div><p className="eyebrow">New document</p><p style={{ marginTop: 6, fontWeight: 700 }}>{o.new_document}: not listed</p></div>
      </div>
      <div className="question-box">{o.question}</div>
      <div className="item-foot">
        <button className="btn btn-primary btn-sm" onClick={onAsk}><Icon name={onState ? "copy" : "stethoscope"} /> {onState ? "Copy the question" : "Ask the doctor"}</button>
        {onState && o.state !== "asked" && <button className="btn btn-quiet btn-sm" onClick={() => onState("asked")}>I have asked</button>}
        {onState && <button className="btn btn-quiet btn-sm" onClick={() => onState("resolved")}><Icon name="check" /> Settled with the doctor</button>}
        {o.state === "asked" && <span className="pill">Asked</span>}
      </div>
    </article>
  );
}

export function ChangeCard({ c, onDecide }: { c: PendingChange; onDecide: (id: string, d: "confirm" | "reject") => void }) {
  const { t } = useI18n();
  return (
    <article className="card item">
      <div className="item-top">
        <div>
          <p className="eyebrow">{c.change_type === "new" ? "New" : c.change_type === "changed" ? "Changed" : "Stopped"} · heard in the visit</p>
          <h3 style={{ marginTop: 4 }}>{c.title}</h3>
        </div>
        <span className="pill pill-marigold">Waiting for you</span>
      </div>
      <div className="diff">
        {c.before && <span className="old">{c.before}</span>}
        {c.before && <span aria-hidden="true">→</span>}
        {c.after && <span className="new">{c.after}</span>}
      </div>
      <div className="item-foot">
        <SourceChip source={c.source} />
      </div>
      <div className="item-foot">
        <button className="btn btn-leaf btn-sm" onClick={() => onDecide(c.id, "confirm")}><Icon name="check" /> {t("confirm")}</button>
        <button className="btn btn-quiet btn-sm" onClick={() => onDecide(c.id, "reject")}><Icon name="x" /> {t("reject")}</button>
      </div>
    </article>
  );
}

const kindIcon: Record<PlanItem["kind"], IconName> = {
  medicine: "pill", condition: "heart", test: "flask", appointment: "calendar", warning_sign: "alert", restriction: "ban", instruction: "list",
};
const levelPill: Record<NonNullable<PlanItem["alert_level"]>, [string, string]> = {
  emergency: ["pill pill-rose", "Emergency"],
  call_doctor_today: ["pill pill-amber", "Call the doctor today"],
  watch: ["pill pill-blue", "Keep watching"],
};

export function DuplicateCard({ d, onCopy }: { d: DuplicateGroup; onCopy: () => void }) {
  return (
    <article className="card conflict" style={{ boxShadow: "inset 5px 0 0 var(--gold), var(--shadow-1)" }}>
      <div className="item-top">
        <div>
          <p className="eyebrow" style={{ color: "var(--gold)" }}>Two medicines list the same ingredient</p>
          <h3 style={{ fontSize: 24, marginTop: 4 }}>{d.medicines.join(" and ")}</h3>
        </div>
        <span className="pill pill-amber">{d.ingredient}</span>
      </div>
      <div className="item-foot">{d.sources.map((s, k) => <SourceChip key={k} source={s} />)}</div>
      <div className="question-box">{d.question}</div>
      <div className="item-foot">
        <button className="btn btn-primary btn-sm" onClick={onCopy}><Icon name="copy" /> Copy the question</button>
        <span style={{ color: "var(--ink-3)", fontSize: 14.5 }}>It may be the same medicine under two brand names. Only the doctor or pharmacist can say.</span>
      </div>
    </article>
  );
}

function ExplainBox({ itemKey, explain }: { itemKey: string; explain: (key: string) => Promise<Explanation> }) {
  const { lang } = useI18n();
  const { speak, speaking, stop } = useSpeech(speechLocale[lang]);
  const [e, setE] = useState<Explanation | null>(null);
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    try { setE(await explain(itemKey)); } finally { setBusy(false); }
  }
  if (!e) return <button className="btn btn-quiet btn-sm" disabled={busy} onClick={go}><Icon name="volume" /> {busy ? "Writing…" : "Explain this"}</button>;
  return (
    <div className="question-box" style={{ flexBasis: "100%" }}>
      <p>{e.text}</p>
      <div className="item-foot" style={{ marginTop: 8 }}>
        <button className="btn btn-quiet btn-sm" onClick={() => (speaking ? stop() : speak(e.text))}><Icon name="volume" /> {speaking ? "Stop" : "Listen"}</button>
        <SourceChip source={e.source} />
        {!e.confirmed && <span className="pill pill-marigold">Not confirmed yet</span>}
        {!e.passed && <span className="pill pill-amber">A safe default text is shown</span>}
      </div>
    </div>
  );
}

export function PlanItemCard({ i, onConfirm, explain }: { i: PlanItem; onConfirm?: (key: string) => void; explain?: (key: string) => Promise<Explanation> }) {
  const slots: ["morning" | "noon" | "evening" | "night", string][] = [["morning", "M"], ["noon", "N"], ["evening", "E"], ["night", "Ni"]];
  return (
    <article className={`card item ${i.confirmed ? "" : "unconfirmed"}`}>
      <div className="item-top">
        <div style={{ display: "flex", gap: 12 }}>
          <span className="kind-ic"><Icon name={kindIcon[i.kind]} /></span>
          <div>
            <h3>{i.title}</h3>
            {i.detail && <p className="detail">{i.detail}</p>}
          </div>
        </div>
        {i.alert_level ? <span className={levelPill[i.alert_level][0]}>{levelPill[i.alert_level][1]}</span>
          : i.confirmed ? <span className="pill pill-leaf"><Icon name="check" className="icon" /> Confirmed</span>
          : <span className="pill pill-marigold">From document, not yet confirmed</span>}
      </div>
      {i.schedule && (
        <div className="sched" aria-label="Schedule">
          {slots.map(([k, l]) => <span key={k} className={i.schedule![k] ? "on" : ""}>{l}{i.schedule![k] ? ` ${i.schedule![k]}` : ""}</span>)}
        </div>
      )}
      {i.date_missing && <div className="notice"><Icon name="clock" /> No date was given. Please ask the doctor when.</div>}
      <div className="item-foot">
        <SourceChip source={i.source} />
        {i.confirmed_by && <span style={{ color: "var(--ink-3)", fontSize: 14 }}>Confirmed by {i.confirmed_by}</span>}
        {onConfirm && !i.confirmed && !i.alert_level && (
          <button className="btn btn-leaf btn-sm" onClick={() => onConfirm(i.item_key)}><Icon name="check" /> Confirm this is right</button>
        )}
        {explain && i.kind === "medicine" && <ExplainBox itemKey={i.item_key} explain={explain} />}
      </div>
    </article>
  );
}

const toolName: Record<string, string> = {
  message_doctor_draft: "Message the doctor",
  send_family_message: "Message a family member",
  share_emergency_card: "Share the Emergency Card",
};

export function ApprovalCard({ a, onDecide }: { a: ApprovalAction; onDecide: (id: string, d: "approve" | "refuse") => void }) {
  const { t } = useI18n();
  return (
    <article className="card item">
      <div className="item-top">
        <div>
          <p className="eyebrow">{toolName[a.tool] ?? a.tool} · asks first</p>
          <h3 style={{ marginTop: 4 }}>{a.summary}</h3>
        </div>
        <span className="pill pill-marigold">Awaiting approval</span>
      </div>
      <div className="item-foot">
        <button className="btn btn-leaf btn-sm" onClick={() => onDecide(a.id, "approve")}><Icon name="check" /> {t("approve")}</button>
        <button className="btn btn-quiet btn-sm" onClick={() => onDecide(a.id, "refuse")}><Icon name="x" /> {t("refuse")}</button>
      </div>
    </article>
  );
}

const fmt = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="timeline" style={{ listStyle: "none", margin: 0, paddingLeft: 26 }}>
      {events.map((e) => (
        <li key={e.id} className={`tl ${e.kind}`}>
          <time dateTime={e.at}>{fmt(e.at)} · {e.actor}</time>
          <p>{e.text}</p>
        </li>
      ))}
    </ol>
  );
}

export function useToast() {
  const [msg, setMsg] = useState<string | null>(null);
  const show = useCallback((m: string) => { setMsg(m); window.setTimeout(() => setMsg(null), 3200); }, []);
  const node = msg ? (
    <div role="status" style={{ position: "fixed", left: "50%", bottom: 24, transform: "translateX(-50%)", background: "var(--ink)", color: "var(--paper)", padding: "12px 20px", borderRadius: 999, zIndex: 70, boxShadow: "var(--shadow-2)", fontWeight: 700 }}>
      {msg}
    </div>
  ) : null;
  return { show, node };
}
