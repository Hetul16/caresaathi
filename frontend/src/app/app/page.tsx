"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppGate } from "@/components/AppGate";
import { Dashboard } from "@/components/family/Dashboard";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import { clearPendingJoin, pendingJoin } from "@/lib/join";
import { readSelected, useCarePlan, usePatients, writeSelected, type PatientRow } from "@/lib/live";

function Live() {
  const router = useRouter();
  const { patients, error: pErr, reload: reloadPatients } = usePatients();
  const [selected, setSelected] = useState<string | null>(null);

  // Someone who opened an invitation link and then signed in: join first, then show the family. Until that finishes, do not send them to
  // "add your relative" (they are joining one that already exists).
  const [joining, setJoining] = useState(() => pendingJoin() !== null);
  useEffect(() => {
    const code = pendingJoin();
    if (!code) { setJoining(false); return; }
    clearPendingJoin();
    api<{ patient_id: string }>("/invites/accept", { method: "POST", json: { code } })
      .then((r) => writeSelected(r.patient_id))
      .catch(() => undefined)
      .finally(() => { setJoining(false); reloadPatients(); });
  }, [reloadPatients]);

  // Decide where to go from a FRESH list, never from state kept by this page. The app keeps visited pages alive, so after "load the demo"
  // this page can wake up still holding the empty list it saw before the patient existed.
  useEffect(() => {
    if (joining) return;
    let alive = true;
    api<PatientRow[]>("/patients").then((list) => {
      if (!alive) return;
      if (list.length === 0) { router.replace("/onboarding"); return; }
      const saved = readSelected();
      setSelected(list.find((p) => p.id === saved)?.id ?? list[0].id);
      reloadPatients();
    }).catch(() => undefined);
    return () => { alive = false; };
  }, [joining, router, reloadPatients]);

  const { plan, error, reload } = useCarePlan(selected);

  if (pErr || error) {
    return (
      <div className="center-page"><div>
        <Icon name="alert" /><h1 style={{ fontSize: 26, marginTop: 10 }}>We could not load the care plan</h1>
        <p style={{ color: "var(--ink-2)", margin: "8px 0 16px" }}>{(pErr ?? error)?.detail || (pErr ?? error)?.title}</p>
        <button className="btn btn-primary" onClick={() => { reloadPatients(); reload(); }}>Try again</button>
      </div></div>
    );
  }
  if (!plan || !selected) {
    return (
      <div className="wrap fam-shell" aria-busy="true" aria-label="Loading care plan">
        <div className="skeleton" style={{ height: 200 }} /><div className="stack"><div className="skeleton" style={{ height: 90 }} /><div className="skeleton" style={{ height: 160 }} /></div>
      </div>
    );
  }
  return (
    <>
      {patients && patients.length > 1 && (
        <div className="wrap" style={{ paddingTop: 16 }}>
          <label className="select" style={{ maxWidth: 320 }}>
            <span className="sr-only">Who are you looking after?</span>
            <select value={selected} onChange={(e) => { writeSelected(e.target.value); setSelected(e.target.value); }}>
              {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
            </select>
          </label>
        </div>
      )}
      <Dashboard plan={plan} basePath="/app" live={{ patientId: selected, reload }} />
    </>
  );
}

export default function AppHome() {
  return <AppGate><Live /></AppGate>;
}
