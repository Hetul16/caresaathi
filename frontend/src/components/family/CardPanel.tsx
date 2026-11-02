"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { CardLink, EmergencyCardData } from "@/lib/types";
import { Field } from "../auth/Field";
import { Icon } from "../Icon";
import { afterCommit } from "@/lib/defer";

interface CardList { cards: CardLink[]; preview: EmergencyCardData }
interface Created { id: string; url: string; hint: string; expires_at: string | null }

const when = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

// Emergency Card links. The full link is shown once, right after it is made; afterwards only its last four characters.
export function CardPanel({ patientId, onChange, toast }: { patientId: string; onChange: () => void; toast: (m: string) => void }) {
  const [data, setData] = useState<CardList | null>(null);
  const [fresh, setFresh] = useState<Created | null>(null);
  const [busy, setBusy] = useState(false);
  const [share, setShare] = useState<{ card: string; name: string } | null>(null);

  const load = useCallback(async () => {
    try { setData(await api<CardList>(`/patients/${patientId}/emergency-card`)); }
    catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not load the card"); }
  }, [patientId, toast]);
  useEffect(() => { afterCommit(load); }, [load]);

  async function create() {
    setBusy(true);
    try {
      setFresh(await api<Created>(`/patients/${patientId}/emergency-card`, { method: "POST", json: { expires_in_days: 30 } }));
      await load(); onChange();
    } catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not create the link"); }
    finally { setBusy(false); }
  }
  async function revoke(id: string) {
    try {
      await api(`/emergency-cards/${id}/revoke`, { method: "POST" });
      if (fresh?.id === id) setFresh(null);
      toast("Link switched off. It no longer opens."); await load(); onChange();
    } catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not switch it off"); }
  }
  async function askToShare() {
    if (!share || !share.name.trim()) return;
    try {
      await api(`/emergency-cards/${share.card}/share`, { method: "POST", json: { contact_name: share.name.trim() } });
      setShare(null); toast("Added to Approvals. Nothing is sent until someone approves it."); onChange();
    } catch (e) { toast(e instanceof ApiError ? e.detail || e.title : "Could not queue that"); }
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); toast("Copied."); } catch { toast("Could not copy. Select the link and copy it by hand."); }
  }

  if (!data) return <div className="skeleton" style={{ height: 180 }} aria-busy="true" />;
  const { cards, preview } = data;
  const active = cards.filter((c) => c.status === "active");

  return (
    <div className="stack">
      <div className="section-title"><h2>Emergency Card</h2><span className="pill">{active.length} active link{active.length === 1 ? "" : "s"}</span></div>
      <p style={{ color: "var(--ink-2)" }}>
        One page a stranger can open without signing in: allergies first, the medicines as written, and when it was last updated.
        It shows only what your documents say. Switch a link off at any time.
      </p>

      {fresh && (
        <div className="card card-pad stack" role="status" style={{ borderColor: "var(--marigold)" }}>
          <p className="eyebrow">New link · shown once</p>
          <code style={{ wordBreak: "break-all", fontSize: 15 }}>{fresh.url}</code>
          <div className="item-foot">
            <button className="btn btn-primary btn-sm" onClick={() => copy(fresh.url)}><Icon name="copy" /> Copy link</button>
            <a className="btn btn-quiet btn-sm" href={fresh.url} target="_blank" rel="noopener noreferrer"><Icon name="link" /> Open it</a>
          </div>
          <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>Keep it somewhere safe. We cannot show this link again; we only keep a fingerprint of it.</p>
        </div>
      )}

      <div className="item-foot">
        <button className="btn btn-primary" disabled={busy} onClick={create}><Icon name="card" /> {active.length ? "Make another link" : "Make an Emergency Card link"}</button>
      </div>

      {cards.length > 0 && (
        <div className="card card-pad stack">
          {cards.map((c) => (
            <div key={c.id} className="item-top" style={{ alignItems: "center" }}>
              <div>
                <strong>Link ending …{c.hint}</strong>
                <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>
                  Made {when(c.created_at)}{c.expires_at ? ` · expires ${when(c.expires_at)}` : ""}
                </p>
              </div>
              <div className="item-foot" style={{ margin: 0 }}>
                <span className={`pill ${c.status === "active" ? "pill-leaf" : ""}`}>{c.status === "active" ? "Active" : c.status === "revoked" ? "Switched off" : "Expired"}</span>
                {c.status === "active" && <button className="btn btn-quiet btn-sm" onClick={() => setShare({ card: c.id, name: "" })}>Share…</button>}
                {c.status === "active" && <button className="btn btn-quiet btn-sm" onClick={() => revoke(c.id)}><Icon name="ban" /> Switch off</button>}
              </div>
            </div>
          ))}
        </div>
      )}

      {share && (
        <div className="card card-pad stack">
          <Field label="Who should it go to?" value={share.name} onChange={(v) => setShare({ ...share, name: v })} placeholder="For example, Dr Joshi" maxLength={120} />
          <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>This only asks. A family member with approval rights must approve it before anything is sent.</p>
          <div className="item-foot">
            <button className="btn btn-primary btn-sm" onClick={askToShare} disabled={!share.name.trim()}>Ask for approval</button>
            <button className="btn btn-quiet btn-sm" onClick={() => setShare(null)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="section-title"><h2>What the card shows now</h2></div>
      <div className="card card-pad stack">
        <p><strong>Allergies:</strong> {preview.allergies.state === "listed" ? preview.allergies.items.map((a) => a.substance).join(", ")
          : preview.allergies.state === "no_known_allergies" ? "No known allergies, per document" : "Not recorded. Not recorded does not mean none."}</p>
        <p><strong>Medicines:</strong> {preview.medicines.length ? preview.medicines.map((m) => m.title).join(", ") : "None yet"}</p>
        <p style={{ color: "var(--ink-3)", fontSize: 14.5 }}>
          {preview.last_updated_at ? `Last updated ${new Date(preview.last_updated_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}.` : "Nothing has been added yet."}
        </p>
      </div>
    </div>
  );
}
