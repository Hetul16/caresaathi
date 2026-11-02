"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { SecondRead, SecondReading } from "@/lib/types";
import { Icon } from "../Icon";
import { afterCommit } from "@/lib/defer";

const FIELDS: { key: keyof SecondReading; field: string; label: string }[] = [
  { key: "title", field: "name", label: "Name" }, { key: "strength", field: "strength", label: "Strength" }, { key: "frequency", field: "frequency", label: "Schedule" },
  { key: "duration", field: "duration", label: "Days" }, { key: "quantity", field: "quantity", label: "Quantity" },
];

function Reading({ label, r, differs, onUse, can }: { label: string; r: SecondReading | null; differs: string[]; onUse?: () => void; can: boolean }) {
  return (
    <div className="mini" style={{ alignContent: "start" }}>
      <p className="eyebrow">{label}</p>
      {r === null ? <p style={{ color: "var(--ink-3)" }}>This reader did not find this medicine.</p> : (
        <>
          <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px" }}>
            {FIELDS.map((f) => (
              <div key={f.label} style={{ display: "contents" }}>
                <dt style={{ color: "var(--ink-3)" }}>{f.label}</dt>
                <dd style={{ margin: 0, fontWeight: differs.includes(f.field) ? 800 : 400, color: differs.includes(f.field) ? "var(--gold)" : undefined }}>
                  {r[f.key] === null || r[f.key] === undefined || r[f.key] === "" ? "·" : String(r[f.key])}
                </dd>
              </div>
            ))}
          </dl>
          {r.quote && <p className="detail" style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>page {r.page ?? "?"}{r.line ? `, line ${r.line}` : ""}: “{r.quote}”</p>}
          {onUse && can && <button className="btn btn-quiet btn-sm" onClick={onUse} style={{ justifySelf: "start" }}><Icon name="check" /> Use this reading</button>}
        </>
      )}
    </div>
  );
}

// Two-reader check: where two readings of the same page disagree, nothing is applied until a named person chooses.
export function ReadingChecks({ patientId, canApprove, toast, onChange }: { patientId: string; canApprove: boolean; toast: (m: string) => void; onChange: () => void }) {
  const [reads, setReads] = useState<SecondRead[]>([]);
  const load = useCallback(async () => {
    try { setReads((await api<{ reads: SecondRead[] }>(`/patients/${patientId}/second-reads`)).reads); } catch { /* the rest of the page still works */ }
  }, [patientId]);
  useEffect(() => { afterCommit(load); }, [load]);

  async function choose(id: string, choice: "a" | "b" | "neither") {
    try {
      await api(`/second-reads/${id}/choose`, { method: "POST", json: { choice } });
      toast(choice === "neither" ? "Neither reading was used. Ask the pharmacist if the page is unclear." : "Added to the plan with your name. The page line is its source.");
      await load(); onChange();
    } catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not record that choice"); }
  }

  const open = reads.filter((r) => !r.chosen);
  if (open.length === 0) return null;
  return (
    <>
      {open.map((r) => (
        <article key={r.id} className="card item" style={{ borderColor: "var(--gold)" }}>
          <div className="item-top">
            <div><p className="eyebrow">Two readings of the page disagree · {r.document}</p><h3 style={{ marginTop: 4 }}>{r.medicine}</h3></div>
            <span className="pill pill-amber">Please look at the original</span>
          </div>
          <p style={{ color: "var(--ink-2)" }}>
            Two independent readings of this page differ on <b>{r.differs_in.join(", ")}</b>. Nothing has been added to the plan. Look at the paper, then choose, or ask the pharmacist.
          </p>
          <div className="grid-2">
            <Reading label="Reading A" r={r.reading_a} differs={r.differs_in} can={canApprove} onUse={r.reading_a ? () => choose(r.id, "a") : undefined} />
            <Reading label="Reading B" r={r.reading_b} differs={r.differs_in} can={canApprove} onUse={r.reading_b ? () => choose(r.id, "b") : undefined} />
          </div>
          <div className="item-foot">
            {canApprove ? <button className="btn btn-quiet btn-sm" onClick={() => choose(r.id, "neither")}><Icon name="x" /> Use neither, I will ask the pharmacist</button>
              : <span style={{ color: "var(--ink-3)" }}>A family member with approval rights must choose.</span>}
          </div>
        </article>
      ))}
    </>
  );
}
