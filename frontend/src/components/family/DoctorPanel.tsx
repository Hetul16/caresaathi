"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { DoctorLink } from "@/lib/types";
import { Field } from "../auth/Field";
import { Icon } from "../Icon";

const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
interface Created { id: string; url: string; hint: string; doctor_name: string; expires_at: string }

// Doctor links. The full address is shown once. A question only reaches the doctor after someone approves it.
export function DoctorPanel({ patientId, canApprove, toast, onChange }: { patientId: string; canApprove: boolean; toast: (m: string) => void; onChange: () => void }) {
  const [links, setLinks] = useState<DoctorLink[] | null>(null);
  const [name, setName] = useState("");
  const [days, setDays] = useState(7);
  const [fresh, setFresh] = useState<Created | null>(null);
  const [asking, setAsking] = useState<{ id: string; text: string } | null>(null);

  const load = useCallback(async () => {
    try { setLinks((await api<{ links: DoctorLink[] }>(`/patients/${patientId}/doctor-links`)).links); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not load the doctor links"); }
  }, [patientId, toast]);
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [load]);

  const fail = (e: unknown, m: string) => toast(e instanceof ApiError ? e.detail || e.title : m);
  async function create() {
    if (!name.trim()) return;
    try { setFresh(await api<Created>(`/patients/${patientId}/doctor-links`, { method: "POST", json: { doctor_name: name.trim(), expires_in_days: days } })); setName(""); await load(); onChange(); }
    catch (e) { fail(e, "Could not create the link"); }
  }
  async function revoke(id: string) {
    try { await api(`/doctor-links/${id}/revoke`, { method: "POST" }); if (fresh?.id === id) setFresh(null); toast("Link switched off. It no longer opens."); await load(); onChange(); }
    catch (e) { fail(e, "Could not switch it off"); }
  }
  async function ask() {
    if (!asking || !asking.text.trim()) return;
    try { await api(`/doctor-links/${asking.id}/questions`, { method: "POST", json: { body: asking.text.trim() } }); setAsking(null); toast("Added to Approvals. The doctor sees it only after someone approves."); onChange(); }
    catch (e) { fail(e, "Could not queue the question"); }
  }
  async function copy(t: string) { try { await navigator.clipboard.writeText(t); toast("Copied."); } catch { toast("Could not copy. Select the link and copy it by hand."); } }

  return (
    <div className="stack">
      <div className="section-title"><h2>Doctor link</h2><span className="pill">Read-only · expires · revocable</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        Give one doctor a page with the plan as the documents say it, allergies first, with its sources. They can answer your questions there.
        Their reply is saved as their exact words and never changes the plan by itself.
      </p>
      <div className="card card-pad stack">
        <Field label="Doctor's name" value={name} onChange={setName} placeholder="Dr. Joshi" />
        <div className="item-foot">
          <label style={{ color: "var(--ink-2)" }}>Expires in{" "}
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="input" style={{ width: "auto", padding: "8px 12px" }}>
              {[1, 3, 7, 14, 30].map((d) => <option key={d} value={d}>{d} day{d === 1 ? "" : "s"}</option>)}
            </select></label>
          <button className="btn btn-primary" onClick={create} disabled={!name.trim()}><Icon name="link" /> Create link</button>
        </div>
      </div>

      {fresh && (
        <div className="card card-pad stack" role="status" style={{ borderColor: "var(--marigold)" }}>
          <p className="eyebrow">Link for {fresh.doctor_name} · shown once</p>
          <code style={{ wordBreak: "break-all", fontSize: 15 }}>{fresh.url}</code>
          <div className="item-foot">
            <button className="btn btn-primary btn-sm" onClick={() => copy(fresh.url)}><Icon name="copy" /> Copy link</button>
            <a className="btn btn-quiet btn-sm" href={fresh.url} target="_blank" rel="noopener noreferrer"><Icon name="link" /> Open it as the doctor</a>
          </div>
        </div>
      )}

      {links === null && <div className="skeleton" style={{ height: 120 }} aria-busy="true" />}
      {links?.length === 0 && <p className="card card-pad">No links yet.</p>}
      {links?.map((l) => (
        <article key={l.id} className="card item">
          <div className="item-top">
            <div><p className="eyebrow">…{l.hint} · opened {l.opened} time{l.opened === 1 ? "" : "s"}</p><h3 style={{ marginTop: 4 }}>{l.doctor_name}</h3></div>
            <span className={l.status === "active" ? "pill pill-leaf" : "pill pill-rose"}>{l.status === "active" ? `Active until ${when(l.expires_at)}` : l.status === "revoked" ? "Switched off" : "Expired"}</span>
          </div>
          {l.messages.length > 0 && (
            <div className="stack" aria-label={`Messages with ${l.doctor_name}`}>
              {l.messages.map((m) => (
                <div key={m.id} className={`msg ${m.direction}`}>
                  <small>{m.direction === "to_doctor" ? "Sent to the doctor" : `${l.doctor_name}'s exact words`} · {when(m.at)}</small>{m.body}
                </div>
              ))}
            </div>
          )}
          {asking?.id === l.id && (
            <div className="stack">
              <label htmlFor="dq" className="eyebrow">Your question for {l.doctor_name}</label>
              <textarea id="dq" className="input" rows={3} maxLength={1500} value={asking.text} onChange={(e) => setAsking({ id: l.id, text: e.target.value })} />
              <div className="item-foot"><button className="btn btn-primary btn-sm" onClick={ask}>Queue for approval</button><button className="btn btn-quiet btn-sm" onClick={() => setAsking(null)}>Cancel</button></div>
            </div>
          )}
          {l.status === "active" && (
            <div className="item-foot">
              {asking?.id !== l.id && <button className="btn btn-quiet btn-sm" onClick={() => setAsking({ id: l.id, text: "" })}><Icon name="quote" /> Ask the doctor something</button>}
              {canApprove && <button className="btn btn-quiet btn-sm" onClick={() => revoke(l.id)}><Icon name="ban" /> Switch off</button>}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
