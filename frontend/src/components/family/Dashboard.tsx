"use client";
import { useState } from "react";
import Link from "next/link";
import type { CarePlan, Explanation, PendingChange } from "@/lib/types";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Icon, type IconName } from "../Icon";
import { SourceProvider } from "../Source";
import { AllergyBanner, ApprovalCard, ChangeCard, ConflictCard, DuplicateCard, OmissionCard, PlanItemCard, Timeline, useToast } from "./parts";
import { CardPanel } from "./CardPanel";
import { CrewPanel } from "./CrewPanel";
import { LabelPanel } from "./LabelPanel";
import { OutcomesPanel } from "./OutcomesPanel";
import { DoctorPanel } from "./DoctorPanel";
import { ChatPanel } from "./ChatPanel";
import { FamilyPanel } from "./FamilyPanel";
import { TrackerPanel } from "./TrackerPanel";
import { UploadPanel } from "./UploadPanel";
import { VisitPanel } from "./VisitPanel";
import { DemoLoader } from "../DemoLoader";
import { writeSelected } from "@/lib/live";

type Tab = "overview" | "plan" | "documents" | "visits" | "tracker" | "ask" | "outcomes" | "crew" | "doctor" | "label" | "card" | "family" | "approvals" | "history";

export interface LiveCtx { patientId: string; reload: () => void }

export function Dashboard({ plan: p, basePath, live }: { plan: CarePlan; basePath: "/demo" | "/app"; live?: LiveCtx }) {
  const { t, lang } = useI18n();
  const [tab, setTab] = useState<Tab>("overview");
  // The demo keeps its choices in memory; a live plan is always re-read from the server after a decision.
  const [demoChanges, setDemoChanges] = useState<PendingChange[]>(p.pending_changes);
  const [demoApprovals, setDemoApprovals] = useState(p.approvals);
  const changes = live ? p.pending_changes : demoChanges;
  const approvals = live ? p.approvals : demoApprovals;
  const canApprove = live ? p.can_approve !== false : true;
  const toast = useToast();

  async function run(call: () => Promise<unknown>, done: string) {
    try { await call(); toast.show(done); live?.reload(); }
    catch (e) { toast.show(e instanceof ApiError ? e.detail || e.title : "Something went wrong. Please try again."); }
  }
  const post = (path: string, json: unknown = {}) => api(path, { method: "POST", json });

  const medicines = p.items.filter((i) => i.kind === "medicine");
  const warnings = p.items.filter((i) => i.kind === "warning_sign");
  const others = p.items.filter((i) => i.kind !== "medicine" && i.kind !== "warning_sign");
  const waiting = changes.length + approvals.length;
  const empty = p.items.length === 0 && p.allergies.items.length === 0;
  const confirmItem = live && canApprove
    ? (key: string) => run(() => post(`/patients/${live.patientId}/plan-items/${key}/confirm`), "Confirmed by you. Recorded in the history.")
    : undefined;

  const explain = live ? async (key: string): Promise<Explanation> => api<Explanation>(`/patients/${live.patientId}/explain`, { method: "POST", json: { item_key: key, language: lang } }) : undefined;
  async function confirmAll() {
    const todo = p.items.filter((i) => !i.confirmed && !i.alert_level);
    if (!live || todo.length === 0) return;
    await run(async () => { for (const i of todo) await post(`/patients/${live.patientId}/plan-items/${i.item_key}/confirm`); }, `Confirmed ${todo.length} item${todo.length === 1 ? "" : "s"} by you. Each is recorded in the history.`);
  }

  const tabs: { id: Tab; label: string; icon: IconName; count?: number }[] = [
    { id: "overview", label: "Overview", icon: "heart" },
    { id: "plan", label: "Care plan", icon: "list", count: p.items.filter((i) => !i.confirmed && !i.alert_level).length || undefined },
    ...(live ? [{ id: "documents" as Tab, label: "Documents", icon: "file" as IconName }, { id: "visits" as Tab, label: "Visits", icon: "mic" as IconName },
                { id: "tracker" as Tab, label: "Tracker", icon: "calendar" as IconName }, { id: "ask" as Tab, label: "Ask", icon: "quote" as IconName },
                { id: "outcomes" as Tab, label: "Outcomes", icon: "check" as IconName },
                { id: "crew" as Tab, label: "Care crew", icon: "sparkle" as IconName }, { id: "doctor" as Tab, label: "Doctor link", icon: "stethoscope" as IconName },
                { id: "label" as Tab, label: "Label check", icon: "pill" as IconName },
                { id: "card" as Tab, label: "Emergency Card", icon: "card" as IconName }, { id: "family" as Tab, label: "Family", icon: "users" as IconName }] : []),
    { id: "approvals", label: "Approvals", icon: "shield", count: waiting || undefined },
    { id: "history", label: "History", icon: "history" },
  ];

  async function copyQuestion(q: string) {
    try { await navigator.clipboard.writeText(q); toast.show("Question copied. Take it to the doctor or pharmacist."); }
    catch { toast.show("Could not copy. Select the question and copy it by hand."); }
  }
  function ask() {
    setTab("approvals");
    toast.show("Drafted. Nothing is sent until you approve it.");
  }

  return (
    <SourceProvider>
      <div className="wrap fam-shell">
        <nav className="fam-nav" aria-label="Family sections">
          {tabs.map((x) => (
            <button key={x.id} aria-current={tab === x.id ? "page" : undefined} onClick={() => setTab(x.id)}>
              <Icon name={x.icon} /> {x.label}
              {x.count ? <span className="count" aria-label={`${x.count} waiting`}>{x.count}</span> : null}
            </button>
          ))}
          {!live && (
            <Link href="/e/demo-token" style={{ textDecoration: "none" }}>
              <span className="btn btn-quiet btn-sm" style={{ width: "100%", justifyContent: "flex-start", marginTop: 6 }}><Icon name="card" /> Emergency Card</span>
            </Link>
          )}
        </nav>

        <div>
          <header className="patient-head">
            <div>
              <p className="eyebrow">Family mode</p>
              <h1>{p.patient.name}</h1>
              <div className="meta-row">
                {p.patient.age != null && <><span>{p.patient.age} years</span><span aria-hidden="true">·</span></>}
                {p.last_updated_at && <span>{t("lastUpdated")}: {new Date(p.last_updated_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>}
                <span className="pill">Synthetic patient</span>
              </div>
            </div>
            <Link href={`${basePath}/elder`} className="btn btn-quiet btn-sm"><Icon name="volume" /> {t("elderMode")}</Link>
          </header>

          <div style={{ marginTop: 20 }} className="stack">
            <AllergyBanner state={p.allergies.state} items={p.allergies.items} reviewed={p.reference_list_reviewed} />

            {tab === "overview" && (
              <>
                {empty && (
                  <div className="card empty">
                    <span className="empty-ic"><Icon name="file" /></span>
                    <h2>Start with one document</h2>
                    <p>Upload a prescription or discharge summary. CareSaathi reads it, and every line it adds will point back to the exact text it came from.</p>
                    <div className="item-foot" style={{ justifyContent: "center" }}>
                      <button className="btn btn-primary" onClick={() => setTab(live ? "documents" : "overview")}><Icon name="file" /> Add a document</button>
                      {live && <DemoLoader onReady={(id) => { writeSelected(id); window.location.assign("/app"); }} label="Or load the demo family" />}
                    </div>
                  </div>
                )}
                {p.open_conflicts.map((c) => live
                  ? <ConflictCard key={c.id} c={c} askLabel="Copy the question" note="Take it to the doctor or pharmacist."
                      onAsk={() => copyQuestion(c.doctor_question)}
                      onAck={() => run(() => post(`/allergy-conflicts/${c.id}/acknowledge`), "Marked as seen. It is still a question for the doctor.")} />
                  : <ConflictCard key={c.id} c={c} onAsk={ask} />)}
                {(p.duplicates ?? []).map((d) => <DuplicateCard key={d.ingredient} d={d} onCopy={() => copyQuestion(d.question)} />)}
                {p.omissions.map((o) => live
                  ? <OmissionCard key={o.id} o={o} onAsk={() => copyQuestion(o.question)}
                      onState={(state) => run(() => post(`/reconciliation-flags/${o.id}/state`, { state }), state === "asked" ? "Noted that you asked." : "Marked as settled with the doctor.")} />
                  : <OmissionCard key={o.id} o={o} onAsk={ask} />)}

                {!empty && (
                  <>
                    <div className="section-title"><h2>Waiting for you</h2><span className="pill pill-marigold">{changes.length} from the visit</span></div>
                    {changes.length === 0 && <p className="card card-pad">Nothing is waiting. Everything you have confirmed is in the care plan.</p>}
                    {changes.map((c) => (
                      <ChangeCard key={c.id} c={c} onDecide={(id, d) => {
                        if (live) {
                          if (!canApprove) { toast.show("Only a family member with approval rights can decide this."); return; }
                          run(() => post(`/plan-changes/${id}/decision`, { decision: d }),
                              d === "confirm" ? "Confirmed. A new version was added to the plan." : "Marked as not right. The plan was not changed.");
                          return;
                        }
                        setDemoChanges((cs) => cs.filter((x) => x.id !== id));
                        toast.show(d === "confirm" ? "Confirmed. A new version was added to the plan." : "Marked as not right. The plan was not changed.");
                      }} />
                    ))}
                    {warnings.length > 0 && (
                      <>
                        <div className="section-title"><h2>The written warning signs</h2><span className="pill">From the documents</span></div>
                        <div className="grid-2">{warnings.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
                      </>
                    )}
                  </>
                )}
              </>
            )}

            {tab === "plan" && (
              <>
                <div className="section-title"><h2>Medicines</h2>
                  <span className="item-foot">
                    {live && canApprove && p.items.some((i) => !i.confirmed && !i.alert_level) && <button className="btn btn-quiet btn-sm" onClick={confirmAll}><Icon name="check" /> Confirm all</button>}
                    {live && <Link href="/app/fridge" className="btn btn-quiet btn-sm"><Icon name="list" /> Fridge sheet</Link>}
                    {live && <Link href="/app/schedule" className="btn btn-quiet btn-sm"><Icon name="clock" /> Picture schedule</Link>}
                    <span className="pill">{medicines.length}</span></span></div>
                {medicines.length === 0 && <p className="card card-pad">No medicines yet.</p>}
                <div className="grid-2">{medicines.map((i) => <PlanItemCard key={i.item_key} i={i} onConfirm={confirmItem} explain={explain} />)}</div>
                {others.length > 0 && <div className="section-title"><h2>Tests, visits and diet</h2></div>}
                <div className="grid-2">{others.map((i) => <PlanItemCard key={i.item_key} i={i} onConfirm={confirmItem} />)}</div>
                {warnings.length > 0 && <div className="section-title"><h2>Warning signs</h2></div>}
                <div className="grid-2">{warnings.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
              </>
            )}

            {tab === "documents" && live && <UploadPanel patientId={live.patientId} onProcessed={live.reload} />}

            {tab === "visits" && live && <VisitPanel patientId={live.patientId} canManage={p.can_approve !== false} onChange={live.reload} toast={toast.show} />}

            {tab === "tracker" && live && <TrackerPanel patientId={live.patientId} canApprove={canApprove} toast={toast.show} onChange={live.reload} />}

            {tab === "ask" && live && <ChatPanel patientId={live.patientId} />}

            {tab === "outcomes" && live && <OutcomesPanel patientId={live.patientId} canApprove={canApprove} toast={toast.show} onChange={live.reload} />}

            {tab === "crew" && live && <CrewPanel patientId={live.patientId} canApprove={canApprove} toast={toast.show} onChange={live.reload} />}

            {tab === "label" && live && <LabelPanel patientId={live.patientId} toast={toast.show} />}

            {tab === "doctor" && live && <DoctorPanel patientId={live.patientId} canApprove={canApprove} toast={toast.show} onChange={live.reload} />}

            {tab === "family" && live && <FamilyPanel patientId={live.patientId} canManage={p.can_approve !== false} toast={toast.show} />}

            {tab === "card" && live && <CardPanel patientId={live.patientId} onChange={live.reload} toast={toast.show} />}

            {tab === "approvals" && (
              <>
                <div className="section-title"><h2>Asks first</h2></div>
                <p style={{ color: "var(--ink-2)" }}>CareSaathi never sends a message to a doctor or a relative on its own. It drafts, and a named family member approves.</p>
                {approvals.length === 0 && <p className="card card-pad">No approvals waiting.</p>}
                {approvals.map((a) => (
                  <ApprovalCard key={a.id} a={a} onDecide={(id, d) => {
                    if (live) {
                      run(() => post(`/actions/${id}/${d}`), d === "approve" ? "Approved by you. Recorded in the history." : "Declined. Nothing was sent.");
                      return;
                    }
                    setDemoApprovals((as) => as.filter((x) => x.id !== id));
                    toast.show(d === "approve" ? "Approved by you. Recorded in the audit log." : "Declined. Nothing was sent.");
                  }} />
                ))}
              </>
            )}

            {tab === "history" && (
              <>
                <div className="section-title"><h2>What happened</h2><span className="pill">Audit log</span></div>
                <div className="card card-pad">{p.timeline.length ? <Timeline events={p.timeline} /> : <p>Nothing yet.</p>}</div>
              </>
            )}
          </div>
        </div>
      </div>
      {toast.node}
    </SourceProvider>
  );
}
