import type { Metadata } from "next";
import { mockCard } from "@/lib/mock";
import { Icon } from "@/components/Icon";

export const instant = false; // dynamic public page: the token is runtime data

export const metadata: Metadata = {
  title: "Emergency Card",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

// Public, read-only page. The real route validates the random token, sets a read-only database
// context for one patient, logs the access, and shows the same neutral page for unknown, expired
// and revoked links (docs/13-architecture.md section 4.4).
export default async function EmergencyCardPage(props: PageProps<"/e/[token]">) {
  const { token } = await props.params;
  if (token !== "demo-token") {
    return (
      <div className="center-page">
        <div>
          <Icon name="lock" className="icon" />
          <h1 style={{ fontSize: 28, marginTop: 10 }}>This link is not available</h1>
          <p style={{ color: "var(--ink-2)", marginTop: 8 }}>It may have expired or been switched off by the family.</p>
        </div>
      </div>
    );
  }
  const c = mockCard;
  const updated = new Date(c.last_updated_at).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });

  return (
    <div className="wrap">
      <article className="ecard" aria-label="Emergency Card">
        <div className="ecard-head">
          <h1>EMERGENCY CARD</h1>
          <span style={{ fontWeight: 700 }}>CareSaathi</span>
        </div>
        <div className="ecard-body">
          <div>
            <p className="ecard-name">{c.patient.name}</p>
            <p style={{ color: "var(--ink-2)" }}>{c.patient.age} years{c.patient.blood_group ? ` · Blood group ${c.patient.blood_group}` : ""}</p>
          </div>

          <section aria-labelledby="h-al">
            <h2 id="h-al">Allergies</h2>
            {c.allergies.state === "listed" && (
              <ul className="ecard-list">
                {c.allergies.items.map((a) => (
                  <li key={a.allergy_key} style={{ color: "var(--rose)", fontWeight: 700 }}>
                    <span>{a.substance}</span><span style={{ fontWeight: 400, color: "var(--ink-2)" }}>{a.reaction}</span>
                  </li>
                ))}
              </ul>
            )}
            {c.allergies.state === "no_known_allergies" && <p>No known allergies, per document</p>}
            {c.allergies.state === "not_recorded" && <p style={{ fontWeight: 700 }}>Allergies not recorded</p>}
          </section>

          <section aria-labelledby="h-co">
            <h2 id="h-co">Conditions</h2>
            <ul className="ecard-list">{c.conditions.map((x) => <li key={x.title}>{x.title}</li>)}</ul>
          </section>

          <section aria-labelledby="h-me">
            <h2 id="h-me">Current medicines, as written</h2>
            <ul className="ecard-list">{c.medicines.map((m) => <li key={m.title}><span>{m.title}</span><span style={{ color: "var(--ink-2)" }}>{m.detail}</span></li>)}</ul>
          </section>

          <section aria-labelledby="h-rc">
            <h2 id="h-rc">Recent changes</h2>
            <p>{c.recent_changes}</p>
          </section>

          <section aria-labelledby="h-dr">
            <h2 id="h-dr">Doctor</h2>
            <ul className="ecard-list">
              {c.providers.map((d) => <li key={d.name}><span>{d.name}, {d.hospital}</span><a href={`tel:${d.phone.replace(/\s/g, "")}`}>{d.phone}</a></li>)}
            </ul>
          </section>

          <section aria-labelledby="h-ct">
            <h2 id="h-ct">Family contacts</h2>
            <ul className="ecard-list">
              {c.contacts.map((p) => <li key={p.phone}><span>{p.name} ({p.relation})</span><a href={`tel:${p.phone.replace(/\s/g, "")}`}>{p.phone}</a></li>)}
            </ul>
          </section>

          <p className="ecard-warn">
            Last updated {updated}. This card copies what the patient&apos;s documents and family have confirmed. It is not medical advice.
            Please verify with the patient or family.
          </p>
        </div>
      </article>
    </div>
  );
}
