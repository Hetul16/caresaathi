"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppGate } from "@/components/AppGate";
import { CardView } from "@/components/CardView";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import { readSelected, useCarePlan, usePatients } from "@/lib/live";
import type { EmergencyCardData } from "@/lib/types";

// What Elder mode's emergency button opens. It does not decide anything: it offers a one-tap call, repeats the
// warning signs the patient's OWN documents wrote down, and shows the Emergency Card as it stands now.
function Sos() {
  const { patients } = usePatients();
  const id = patients ? (patients.find((p) => p.id === readSelected())?.id ?? patients[0]?.id ?? null) : null;
  const { plan } = useCarePlan(id);
  const [card, setCard] = useState<EmergencyCardData | null>(null);
  useEffect(() => {
    if (!id) return;
    api<{ preview: EmergencyCardData }>(`/patients/${id}/emergency-card`).then((r) => setCard(r.preview)).catch(() => setCard(null));
  }, [id]);

  const signs = plan?.items.filter((i) => i.kind === "warning_sign") ?? [];
  return (
    <div className="wrap" style={{ paddingTop: 20 }}>
      <div className="stack">
        <a className="btn sos" href="tel:112" style={{ minHeight: 76, fontSize: 26 }}><Icon name="phone" /> Call 112 (India emergency number)</a>
        {signs.length > 0 && (
          <section className="card card-pad stack" aria-labelledby="h-signs">
            <h2 id="h-signs" style={{ fontSize: 24 }}>What your own papers say</h2>
            {signs.map((s) => (
              <p key={s.item_key} style={{ fontSize: 20 }}>
                <strong>{s.title}</strong> <span style={{ color: "var(--ink-3)", fontSize: 15 }}>({s.source.kind === "document" ? `${s.source.document_title}, page ${s.source.page}` : "doctor's words"})</span>
              </p>
            ))}
            <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>These are copied from the patient&apos;s documents. CareSaathi does not judge how serious anything is.</p>
          </section>
        )}
      </div>
      {card ? <CardView c={card} /> : <div className="skeleton" style={{ height: 240, marginTop: 20 }} aria-busy="true" />}
      <p style={{ textAlign: "center", marginBottom: 80 }}><Link href="/app/elder" className="btn btn-quiet">Back</Link></p>
    </div>
  );
}

export default function Page() {
  return <AppGate><Sos /></AppGate>;
}
