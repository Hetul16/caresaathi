"use client";
import { useState } from "react";
import Link from "next/link";
import type { CarePlan, PendingChange } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { Icon, type IconName } from "../Icon";
import { SourceProvider } from "../Source";
import { AllergyBanner, ApprovalCard, ChangeCard, ConflictCard, OmissionCard, PlanItemCard, Timeline, useToast } from "./parts";
import { UploadPanel } from "./UploadPanel";

type Tab = "overview" | "plan" | "documents" | "approvals" | "history";

export interface LiveCtx { patientId: string; reload: () => void }

export function Dashboard({ plan: p, basePath, live }: { plan: CarePlan; basePath: "/demo" | "/app"; live?: LiveCtx }) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("overview");
  const [changes, setChanges] = useState<PendingChange[]>(p.pending_changes);
  const [approvals, setApprovals] = useState(p.approvals);
  const toast = useToast();

  const medicines = p.items.filter((i) => i.kind === "medicine");
  const warnings = p.items.filter((i) => i.kind === "warning_sign");
  const others = p.items.filter((i) => i.kind !== "medicine" && i.kind !== "warning_sign");
  const waiting = changes.length + approvals.length;
  const empty = p.items.length === 0 && p.allergies.items.length === 0;

  const tabs: { id: Tab; label: string; icon: IconName; count?: number }[] = [
    { id: "overview", label: "Overview", icon: "heart" },
    { id: "plan", label: "Care plan", icon: "list", count: p.items.filter((i) => !i.confirmed).length || undefined },
    ...(live ? [{ id: "documents" as Tab, label: "Documents", icon: "file" as IconName }] : []),
    { id: "approvals", label: "Approvals", icon: "shield", count: waiting || undefined },
    { id: "history", label: "History", icon: "history" },
  ];

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
                    <button className="btn btn-primary" onClick={() => setTab("documents")}><Icon name="file" /> Add a document</button>
                  </div>
                )}
                {p.open_conflicts.map((c) => <ConflictCard key={c.id} c={c} onAsk={ask} />)}
                {p.omissions.map((o) => <OmissionCard key={o.id} o={o} onAsk={ask} />)}

                {!empty && (
                  <>
                    <div className="section-title"><h2>Waiting for you</h2><span className="pill pill-marigold">{changes.length} from the visit</span></div>
                    {changes.length === 0 && <p className="card card-pad">Nothing is waiting. Everything you have confirmed is in the care plan.</p>}
                    {changes.map((c) => (
                      <ChangeCard key={c.id} c={c} onDecide={(id, d) => {
                        setChanges((cs) => cs.filter((x) => x.id !== id));
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
                <div className="section-title"><h2>Medicines</h2><span className="pill">{medicines.length}</span></div>
                {medicines.length === 0 && <p className="card card-pad">No medicines yet.</p>}
                <div className="grid-2">{medicines.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
                <div className="section-title"><h2>Tests, visits and diet</h2></div>
                <div className="grid-2">{others.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
                <div className="section-title"><h2>Warning signs</h2></div>
                <div className="grid-2">{warnings.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
              </>
            )}

            {tab === "documents" && live && <UploadPanel patientId={live.patientId} onProcessed={live.reload} />}

            {tab === "approvals" && (
              <>
                <div className="section-title"><h2>Asks first</h2></div>
                <p style={{ color: "var(--ink-2)" }}>CareSaathi never sends a message to a doctor or a relative on its own. It drafts, and a named family member approves.</p>
                {approvals.length === 0 && <p className="card card-pad">No approvals waiting.</p>}
                {approvals.map((a) => (
                  <ApprovalCard key={a.id} a={a} onDecide={(id, d) => {
                    setApprovals((as) => as.filter((x) => x.id !== id));
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
