"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CareTask, TodayView } from "@/lib/types";
import { Icon } from "../Icon";

// A one-line look at today on the Overview: what has been marked, and what is open. Counts only.
export function TodayGlance({ patientId, go }: { patientId: string; go: (tab: "today" | "tasks") => void }) {
  const [v, setV] = useState<TodayView | null>(null);
  const [open, setOpen] = useState<CareTask[]>([]);
  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const t = await api<TodayView>(`/patients/${patientId}/today`);
        const k = await api<{ tasks: CareTask[] }>(`/patients/${patientId}/tasks`);
        if (live) { setV(t); setOpen(k.tasks.filter((x) => x.status === "open")); }
      } catch { /* the Overview still works without it */ }
    };
    load(); const id = setInterval(load, 30000);
    return () => { live = false; clearInterval(id); };
  }, [patientId]);
  if (!v) return null;
  const s = v.summary, total = s.taken + s.not_taken + s.due + s.not_marked + s.later;
  const unmarked = s.due + s.not_marked;
  if (total === 0 && open.length === 0 && !v.checkin) return null;
  return (
    <div className="card card-pad" style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center", justifyContent: "space-between" }}>
      <div>
        <p className="eyebrow">Today · {v.now}</p>
        <p style={{ fontSize: 18, margin: "4px 0 0" }}>
          {total > 0 ? <><b>{s.taken} of {total}</b> doses marked as taken{unmarked > 0 ? <>, <b style={{ color: "var(--gold)" }}>{unmarked} not marked yet</b></> : null}{s.not_taken > 0 ? <>, <b style={{ color: "var(--coral)" }}>{s.not_taken} marked not taken</b></> : null}. </> : null}
          {v.checkin?.pain != null ? <>Pain today, in their words: <b>{v.checkin.pain} of 10</b>. </> : null}
          {open.length > 0 ? <>{open.length} open task{open.length === 1 ? "" : "s"}{open.some((t) => t.overdue) ? <b style={{ color: "var(--coral)" }}> (some overdue)</b> : null}.</> : null}
        </p>
      </div>
      <span className="item-foot">
        <button className="btn btn-quiet btn-sm" onClick={() => go("today")}><Icon name="clock" /> Open Today</button>
        <button className="btn btn-quiet btn-sm" onClick={() => go("tasks")}><Icon name="list" /> Tasks</button>
      </span>
    </div>
  );
}
