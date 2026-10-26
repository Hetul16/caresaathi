"use client";
import { useState } from "react";
import Link from "next/link";
import { mockPlan } from "@/lib/mock";
import type { PendingChange } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { Icon, type IconName } from "@/components/Icon";
import { SourceProvider } from "@/components/Source";
import { AllergyBanner, ApprovalCard, ChangeCard, ConflictCard, OmissionCard, PlanItemCard, Timeline, useToast } from "@/components/family/parts";

type Tab = "overview" | "plan" | "approvals" | "history";

export default function FamilyPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("overview");
  const [changes, setChanges] = useState<PendingChange[]>(mockPlan.pending_changes);
  const [approvals, setApprovals] = useState(mockPlan.approvals);
  const toast = useToast();
  const p = mockPlan;

  const waiting = changes.length + approvals.length;
  const tabs: { id: Tab; label: string; icon: IconName; count?: number }[] = [
    { id: "overview", label: "Overview", icon: "heart" },
    { id: "plan", label: "Care plan", icon: "list", count: p.items.filter((i) => !i.confirmed).length || undefined },
    { id: "approvals", label: "Approvals", icon: "shield", count: waiting || undefined },
    { id: "history", label: "History", icon: "history" },
  ];

  const medicines = p.items.filter((i) => i.kind === "medicine");
  const warnings = p.items.filter((i) => i.kind === "warning_sign");
  const others = p.items.filter((i) => i.kind !== "medicine" && i.kind !== "warning_sign");

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
          <Link href="/e/demo-token" style={{ textDecoration: "none" }}>
            <span className="btn btn-quiet btn-sm" style={{ width: "100%", justifyContent: "flex-start", marginTop: 6 }}><Icon name="card" /> Emergency Card</span>
          </Link>
        </nav>

        <div>
          <header className="patient-head">
            <div>
              <p className="eyebrow">Family mode</p>
              <h1>{p.patient.name}</h1>
              <div className="meta-row">
                <span>{p.patient.age} years</span><span aria-hidden="true">·</span>
                <span>{t("lastUpdated")}: {new Date(p.last_updated_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
                <span className="pill">Synthetic patient</span>
              </div>
            </div>
            <Link href="/elder" className="btn btn-quiet btn-sm"><Icon name="volume" /> {t("elderMode")}</Link>
          </header>

          <div style={{ marginTop: 20 }} className="stack">
            <AllergyBanner state={p.allergies.state} items={p.allergies.items} reviewed={p.reference_list_reviewed} />

            {tab === "overview" && (
              <>
                {p.open_conflicts.map((c) => <ConflictCard key={c.id} c={c} onAsk={ask} />)}
                {p.omissions.map((o) => <OmissionCard key={o.id} o={o} onAsk={ask} />)}

                <div className="section-title"><h2>Waiting for you</h2><span className="pill pill-marigold">{changes.length} from the visit</span></div>
                {changes.length === 0 && <p className="card card-pad">Nothing is waiting. Everything you have confirmed is in the care plan.</p>}
                {changes.map((c) => (
                  <ChangeCard key={c.id} c={c} onDecide={(id, d) => {
                    setChanges((cs) => cs.filter((x) => x.id !== id));
                    toast.show(d === "confirm" ? "Confirmed. A new version was added to the plan." : "Marked as not right. The plan was not changed.");
                  }} />
                ))}

                <div className="section-title"><h2>The written warning signs</h2><span className="pill">From the discharge summary</span></div>
                <div className="grid-2">{warnings.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
              </>
            )}

            {tab === "plan" && (
              <>
                <div className="section-title"><h2>Medicines</h2><span className="pill">{medicines.length}</span></div>
                <div className="grid-2">{medicines.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
                <div className="section-title"><h2>Tests, visits and diet</h2></div>
                <div className="grid-2">{others.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
                <div className="section-title"><h2>Warning signs</h2></div>
                <div className="grid-2">{warnings.map((i) => <PlanItemCard key={i.item_key} i={i} />)}</div>
              </>
            )}

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
                <div className="card card-pad"><Timeline events={p.timeline} /></div>
              </>
            )}
          </div>
        </div>
      </div>
      {toast.node}
    </SourceProvider>
  );
}
