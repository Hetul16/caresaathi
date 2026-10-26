"use client";
import Link from "next/link";
import { Icon, type IconName } from "@/components/Icon";
import { Reveal } from "@/components/landing/Reveal";
import { StoryDemo } from "@/components/landing/StoryDemo";
import { useAuth } from "@/lib/auth";

const ALWAYS = [
  "Shows the page and line, or the doctor’s exact words, behind every item",
  "Checks allergies in code against a vetted list, and asks the doctor when it matches",
  "Says “could not check” when it does not know, and never reads an empty list as “none”",
  "Waits for a named family member before a visit’s changes enter the plan",
  "Records who did what, in a log that can only be added to",
];
const NEVER = [
  "Call a medicine safe",
  "Tell anyone to stop, skip or change a dose",
  "Suggest a substitute, or diagnose",
  "Decide whether to go to hospital",
  "Send a message without a family member’s approval",
];
const STEPS: { icon: IconName; title: string; body: string }[] = [
  { icon: "file", title: "Read", body: "A photo or PDF is transcribed page by page, line by line." },
  { icon: "quote", title: "Verify", body: "Each quote must exist on the page it cites, or the item is dropped." },
  { icon: "list", title: "Plan", body: "Items become versions of a living plan. Nothing is ever overwritten." },
  { icon: "shield", title: "Check", body: "Code compares ingredients with the family’s allergies and earlier lists." },
  { icon: "users", title: "Confirm", body: "A named person confirms. Every action lands in the audit log." },
];

export default function Home() {
  const { status } = useAuth();
  return (
    <div className="landing">
      <section className="wrap hero2">
        <div className="hero2-copy">
          <p className="pill pill-marigold" style={{ width: "fit-content" }}><Icon name="sparkle" className="icon" /> Built for the Meta Global AI Developer Hackathon</p>
          <h1>
            Every instruction,<br /><em>with its source.</em>
          </h1>
          <p className="lead">
            CareSaathi listens to the doctor visit, reads the prescriptions and turns them into one living care plan for your family.
            Every line points back to the page, or the doctor’s exact words. Then it explains the plan aloud in Hindi, Marathi or English.
          </p>
          <div className="hero-actions">
            {status === "authed"
              ? <Link className="btn btn-primary btn-lg" href="/app">Open your care plan</Link>
              : <Link className="btn btn-primary btn-lg" href="/signup">Create a free account</Link>}
            <Link className="btn btn-quiet btn-lg" href="/demo"><Icon name="sparkle" /> Try the live demo</Link>
          </div>
          <ul className="trust-row" aria-label="Principles">
            <li><Icon name="quote" /> Sourced</li>
            <li><Icon name="shield" /> Never says “safe”</li>
            <li><Icon name="volume" /> Voice first</li>
          </ul>
        </div>
        <StoryDemo />
      </section>

      <section className="wrap band">
        <Reveal as="header" className="band-head">
          <p className="eyebrow">The promise</p>
          <h2>Built so it <em>cannot</em> overstep.</h2>
          <p>These are not instructions to a model. They are rules in code and in the database, tested on every change.</p>
        </Reveal>
        <div className="ledger">
          <Reveal className="ledger-col ledger-yes">
            <h3><Icon name="check" /> CareSaathi always</h3>
            <ul>{ALWAYS.map((t) => <li key={t}>{t}</li>)}</ul>
          </Reveal>
          <Reveal className="ledger-col ledger-no" delay={120}>
            <h3><Icon name="ban" /> CareSaathi never</h3>
            <ul>{NEVER.map((t) => <li key={t}>{t}</li>)}</ul>
            <p className="ledger-note">Every flag ends with a question to the doctor or pharmacist, because that is where the answer lives.</p>
          </Reveal>
        </div>
      </section>

      <section className="wrap band">
        <Reveal as="header" className="band-head">
          <p className="eyebrow">How a line earns its place</p>
          <h2>From a blurry photo to a plan you can trust.</h2>
        </Reveal>
        <ol className="pipeline">
          {STEPS.map((s, i) => (
            <Reveal as="li" key={s.title} delay={i * 90} className="pipe-step">
              <span className="pipe-n">{i + 1}</span>
              <span className="pipe-ic"><Icon name={s.icon} /></span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </Reveal>
          ))}
        </ol>
      </section>

      <section className="wrap band">
        <Reveal as="header" className="band-head">
          <p className="eyebrow">One plan, three ways in</p>
          <h2>For the person, the family and the stranger in an emergency.</h2>
        </Reveal>
        <div className="trio">
          <Reveal className="trio-card trio-elder">
            <div className="trio-art"><div className="mini-orb big"><span /><span /><span /><i><Icon name="mic" /></i></div></div>
            <h3>Elder mode</h3>
            <p>One big button. Large type. Everything is spoken, slowly, with “repeat that”. Only confirmed medicines are read out.</p>
            <Link href="/demo/elder" className="trio-link">See Elder mode →</Link>
          </Reveal>
          <Reveal className="trio-card" delay={100}>
            <div className="trio-art trio-art-fam">
              <div className="fam-chip rose"><Icon name="alert" className="icon" /> Penicillin</div>
              <div className="fam-chip"><Icon name="quote" className="icon" /> p.1 line 4</div>
              <div className="fam-chip ok"><Icon name="check" className="icon" /> Confirmed by Priya</div>
            </div>
            <h3>Family mode</h3>
            <p>Plan, sources, approvals and history. Confirm what was heard in the clinic, and see exactly who changed what.</p>
            <Link href="/demo" className="trio-link">See Family mode →</Link>
          </Reveal>
          <Reveal className="trio-card" delay={200}>
            <div className="trio-art trio-art-card">
              <div className="ec"><b>EMERGENCY CARD</b><span>Allergies first</span><span>Updated 28 Oct, 9:12</span><i /></div>
            </div>
            <h3>Emergency Card</h3>
            <p>One page for a stranger: allergies first, last-updated time, a random link you can revoke in one tap.</p>
            <Link href="/e/demo-token" className="trio-link">Open a sample card →</Link>
          </Reveal>
        </div>
      </section>

      <section className="wrap">
        <Reveal className="cta">
          <h2>Bring every instruction home.</h2>
          <p>Free to try. Synthetic data only in this build.</p>
          <div className="hero-actions" style={{ justifyContent: "center" }}>
            <Link className="btn btn-lg cta-primary" href={status === "authed" ? "/app" : "/signup"}>{status === "authed" ? "Open your care plan" : "Create an account"}</Link>
            <Link className="btn btn-lg cta-ghost" href="/demo">Explore the demo</Link>
          </div>
        </Reveal>
        <footer className="foot">
          <p>CareSaathi is a care-coordination and document-organization tool. It does not give medical advice, diagnose, or decide on treatment. Always ask the doctor or pharmacist.</p>
          <p>Hackathon build · synthetic data only · Hindi, Marathi and English</p>
        </footer>
      </section>
    </div>
  );
}
