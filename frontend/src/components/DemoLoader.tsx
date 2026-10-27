"use client";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { CarePlan } from "@/lib/types";
import { Icon } from "./Icon";

// Loads the fictional demo family (Ramesh Kulkarni) by running the synthetic documents and a mock visit through the real pipeline.
export function DemoLoader({ onReady, label = "Load the demo family" }: { onReady: (patientId: string) => void; label?: string }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError("");
    try {
      const r = await api<{ patient_id: string; status: string }>("/demo/seed", { method: "POST", json: { display_name: user?.display_name ?? "A family member" } });
      if (r.status === "seeding") {
        const t0 = Date.now();
        for (;;) {
          await new Promise((res) => setTimeout(res, 700));
          const plan = await api<CarePlan>(`/patients/${r.patient_id}/care-plan`);
          if (plan.timeline.some((e) => e.text.startsWith("Demo family ready"))) break;
          if (plan.timeline.some((e) => e.text.includes("could not be fully loaded"))) throw new Error("The demo could not be fully loaded.");
          if (Date.now() - t0 > 90000) throw new Error("The demo is taking too long. Please try again.");
        }
      }
      onReady(r.patient_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail || e.title : e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: 8, justifyItems: "start" }}>
      <button type="button" className="btn btn-quiet" disabled={busy} onClick={load}>
        <Icon name="sparkle" /> {busy ? "Loading the story…" : label}
      </button>
      {busy && <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>Reading the fictional documents and a mock visit with the same steps a real upload uses. This takes a few seconds.</p>}
      {error && <p role="alert" style={{ color: "var(--coral)", fontWeight: 700 }}>{error}</p>}
    </div>
  );
}
