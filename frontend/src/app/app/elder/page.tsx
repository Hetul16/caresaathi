"use client";
import { AppGate } from "@/components/AppGate";
import { ElderView } from "@/components/ElderView";
import { readSelected, useCarePlan, usePatients } from "@/lib/live";

function Live() {
  const { patients } = usePatients();
  const id = patients ? (patients.find((p) => p.id === readSelected())?.id ?? patients[0]?.id ?? null) : null;
  const { plan } = useCarePlan(id);
  if (!plan) return <div className="center-page" aria-busy="true"><div className="spinner" aria-hidden="true" /></div>;
  return <ElderView plan={plan} emergencyHref="/app/emergency" patientId={id ?? undefined} />;
}

export default function AppElder() {
  return <AppGate><Live /></AppGate>;
}
