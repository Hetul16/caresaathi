"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppGate } from "@/components/AppGate";
import { api, ApiError } from "@/lib/api";
import { readSelected, usePatients } from "@/lib/live";
import type { FridgeSheet } from "@/lib/types";

const SLOTS: ["morning" | "noon" | "evening" | "night", string][] = [["morning", "Morning"], ["noon", "Noon"], ["evening", "Evening"], ["night", "Night"]];

// A one-page sheet for the fridge. Confirmed medicines only, nothing under an open allergy flag, and the source of every line.
// Printed on white paper: it is evidence, so it uses the paper look.
function Sheet() {
  const { patients } = usePatients();
  const id = patients ? (patients.find((p) => p.id === readSelected())?.id ?? patients[0]?.id ?? null) : null;
  const [sheet, setSheet] = useState<FridgeSheet | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!id) return;
    api<FridgeSheet>(`/patients/${id}/fridge-sheet`).then(setSheet).catch((e) => setError(e instanceof ApiError ? e.detail || e.title : "Could not load the sheet"));
  }, [id]);

  if (error) return <div className="center-page"><div><h1 style={{ fontSize: 26 }}>We could not load the sheet</h1><p style={{ color: "var(--ink-2)", marginTop: 8 }}>{error}</p></div></div>;
  if (!sheet) return <div className="wrap" style={{ padding: "30px 0" }}><div className="skeleton" style={{ height: 320 }} aria-busy="true" /></div>;

  const made = new Date(sheet.generated_at).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
  return (
    <div className="wrap fridge-wrap">
      <div className="no-print item-foot" style={{ padding: "18px 0" }}>
        <Link href="/app" className="btn btn-quiet btn-sm">← Back</Link>
        <button className="btn btn-primary btn-sm" onClick={() => window.print()}>Print this sheet</button>
        <span style={{ color: "var(--ink-3)", fontSize: 14.5 }}>Only medicines your family has confirmed appear here.</span>
      </div>
      <article className="fridge on-paper" aria-label="Fridge sheet">
        <header className="fridge-head"><div><p className="eyebrow">Medicines for the fridge</p><h1>{sheet.patient}</h1></div><p className="eyebrow">CareSaathi · synthetic data</p></header>

        <section className="fridge-allergy" aria-labelledby="fa">
          <h2 id="fa">Allergies</h2>
          {sheet.allergy_state === "listed" && <p className="fridge-bad">{sheet.allergies.map((a) => `${a.substance}${a.reaction ? ` (${a.reaction})` : ""}`).join(", ")}</p>}
          {sheet.allergy_state === "no_known_allergies" && <p>No known allergies, per the documents.</p>}
          {sheet.allergy_state === "not_recorded" && <p className="fridge-bad">Not recorded. Not recorded does not mean none.</p>}
        </section>

        <section aria-labelledby="fm">
          <h2 id="fm">Medicines</h2>
          {sheet.medicines.length === 0 ? <p>No medicine has been confirmed yet, so none is listed.</p> : (
            <table className="fridge-table">
              <thead><tr><th scope="col">Medicine</th>{SLOTS.map(([, l]) => <th key={l} scope="col">{l}</th>)}<th scope="col">Written</th></tr></thead>
              <tbody>{sheet.medicines.map((m) => (
                <tr key={m.title}>
                  <th scope="row">{m.title}{m.detail ? <span>{m.detail}</span> : null}</th>
                  {SLOTS.map(([k]) => <td key={k}>{m.when[k] ? <b>{m.when[k]}</b> : <i aria-label="none">·</i>}</td>)}
                  <td className="fridge-src">{m.source}</td>
                </tr>))}</tbody>
            </table>
          )}
        </section>

        {sheet.warning_signs.length > 0 && (
          <section aria-labelledby="fw"><h2 id="fw">Written in the documents</h2>
            <ul>{sheet.warning_signs.map((w) => <li key={w.title}>{w.title}</li>)}</ul></section>
        )}
        {sheet.doctors.length > 0 && (
          <section aria-labelledby="fd"><h2 id="fd">Doctor</h2>
            <ul>{sheet.doctors.map((d) => <li key={d.name}>{d.name}{d.hospital ? `, ${d.hospital}` : ""}{d.phone ? ` · ${d.phone}` : ""}</li>)}</ul></section>
        )}
        <footer className="fridge-foot">Made {made}. {sheet.note}</footer>
      </article>
    </div>
  );
}

export default function Page() {
  return <AppGate><Sheet /></AppGate>;
}
