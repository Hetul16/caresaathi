"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Invite, Member } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { Field } from "../auth/Field";
import { Icon } from "../Icon";
import { afterCommit } from "@/lib/defer";

const errText = (e: unknown) => (e instanceof ApiError ? e.detail || e.title : "Something went wrong. Please try again.");
const ROLES: [string, string][] = [["patient", "The patient"], ["child", "Son or daughter"], ["spouse", "Husband or wife"], ["relative", "Other relative"], ["attendant", "Attendant"], ["nurse", "Nurse"], ["other", "Someone else"]];

export function FamilyPanel({ patientId, canManage, toast }: { patientId: string; canManage: boolean; toast: (m: string) => void }) {
  const { user } = useAuth();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [fresh, setFresh] = useState<{ url: string } | null>(null);
  const [role, setRole] = useState("child");
  const isPatient = role === "patient";
  const [label, setLabel] = useState("");
  const [approve, setApprove] = useState(false);
  const [rec, setRec] = useState(false);
  const [manage, setManage] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setMembers(await api<Member[]>(`/patients/${patientId}/members`));
      if (canManage) setInvites(await api<Invite[]>(`/patients/${patientId}/invites`));
    } catch (e) { toast(errText(e)); }
  }, [patientId, canManage, toast]);
  useEffect(() => { afterCommit(load); }, [load]);

  async function patch(id: string, body: Record<string, unknown>, ok: string) {
    try { await api(`/members/${id}`, { method: "PATCH", json: body }); toast(ok); load(); } catch (e) { toast(errText(e)); }
  }
  async function invite() {
    setBusy(true);
    try { setFresh(await api<{ url: string }>(`/patients/${patientId}/invites`, { method: "POST", json: { member_role: role, relationship_label: label.trim() || null, can_approve: approve, can_view_recordings: rec, can_manage_members: manage, expires_in_days: 7 } })); load(); }
    catch (e) { toast(errText(e)); } finally { setBusy(false); }
  }
  async function copy(t: string) { try { await navigator.clipboard.writeText(t); toast("Copied."); } catch { toast("Could not copy. Select the link and copy it by hand."); } }

  if (!members) return <div className="skeleton" style={{ height: 200 }} aria-busy="true" />;
  return (
    <div className="stack">
      <div className="section-title"><h2>Family</h2><span className="pill">{members.length} {members.length === 1 ? "person" : "people"}</span></div>
      <p style={{ color: "var(--ink-2)" }}>Only the people listed here can see this care plan. Only someone who can approve may confirm items and decide changes, and everything they do is recorded under their name.</p>
      {members.map((m) => (
        <article key={m.id} className="card item">
          <div className="item-top">
            <div><h3>{m.name}{m.user_id === user?.id ? " (you)" : ""}</h3><p className="detail">{m.relationship ?? m.role}</p></div>
            <div className="item-foot">
              {m.can_manage_members && <span className="pill pill-blue">Manages the family</span>}
              {m.role === "patient" ? <span className="pill pill-blue">The patient · Elder mode</span>
                : m.can_approve ? <span className="pill pill-leaf">Can approve</span> : <span className="pill">Can view</span>}
              {m.can_view_recordings && <span className="pill">Hears recordings</span>}
            </div>
          </div>
          {canManage && (
            <div className="item-foot">
              {m.role !== "patient" && <button className="btn btn-quiet btn-sm" onClick={() => patch(m.id, { can_approve: !m.can_approve }, m.can_approve ? "Approval removed." : "Can now approve.")}>{m.can_approve ? "Remove approval" : "Allow approving"}</button>}
              {m.role !== "patient" && <button className="btn btn-quiet btn-sm" onClick={() => patch(m.id, { can_view_recordings: !m.can_view_recordings }, "Updated.")}>{m.can_view_recordings ? "Hide recordings" : "Allow recordings"}</button>}
              {m.user_id !== user?.id && <button className="btn btn-quiet btn-sm" onClick={() => patch(m.id, { remove: true }, "Removed from the family.")}><Icon name="ban" /> Remove</button>}
            </div>
          )}
        </article>
      ))}

      {canManage && (
        <>
          <div className="section-title"><h2>Invite someone</h2></div>
          {fresh && (
            <div className="card card-pad stack" role="status" style={{ borderColor: "var(--gold)" }}>
              <p className="eyebrow">Invitation link · shown once · works once · expires in 7 days</p>
              <code style={{ wordBreak: "break-all", fontSize: 15 }}>{fresh.url}</code>
              <div className="item-foot"><button className="btn btn-primary btn-sm" onClick={() => copy(fresh.url)}><Icon name="copy" /> Copy link</button><button className="btn btn-quiet btn-sm" onClick={() => setFresh(null)}>Done</button></div>
            </div>
          )}
          <div className="card card-pad stack">
            <fieldset className="lang-pick"><legend>Who are they?</legend>
              <div className="seg" style={{ gridAutoFlow: "row", gridTemplateColumns: "repeat(3, 1fr)" }}>{ROLES.map(([k, v]) => <button key={k} type="button" aria-pressed={role === k} onClick={() => setRole(k)}>{v}</button>)}</div></fieldset>
            <Field label="How you would describe them (optional)" value={label} onChange={setLabel} placeholder={isPatient ? "Mother" : "Brother"} />
            {isPatient && (
              <p className="detail" style={{ color: "var(--ink-2)" }}>
                The patient signs in to Elder mode only: their medicines, one tap to say they took each one, and how they feel today. They
                cannot confirm the plan, approve a change, read visit transcripts or invite anyone. That is enforced by the database, not by
                hiding buttons.
              </p>
            )}
            <label className="check"><input type="checkbox" checked={approve && !isPatient} disabled={isPatient} onChange={(e) => setApprove(e.target.checked)} /><span>They can confirm items and approve changes.</span></label>
            <label className="check"><input type="checkbox" checked={rec && !isPatient} disabled={isPatient} onChange={(e) => setRec(e.target.checked)} /><span>They can read doctor-visit transcripts.</span></label>
            <label className="check"><input type="checkbox" checked={manage && !isPatient} disabled={isPatient} onChange={(e) => setManage(e.target.checked)} /><span>They can manage the family and invite others.</span></label>
            <div className="item-foot"><button className="btn btn-primary" disabled={busy} onClick={invite}><Icon name="users" /> Make an invitation link</button></div>
          </div>
          {invites.filter((i) => i.status === "open").map((i) => (
            <div key={i.id} className="card card-pad item-top" style={{ alignItems: "center" }}>
              <p>Link ending …{i.hint} · {i.relationship ?? i.role} · expires {new Date(i.expires_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</p>
              <button className="btn btn-quiet btn-sm" onClick={async () => { try { await api(`/invites/${i.id}/revoke`, { method: "POST" }); toast("Invitation withdrawn."); load(); } catch (e) { toast(errText(e)); } }}>Withdraw</button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
