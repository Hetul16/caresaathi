"use client";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { Icon } from "@/components/Icon";

export default function Home() {
  const { t } = useI18n();
  return (
    <div className="wrap">
      <section className="hero">
        <div>
          <p className="eyebrow">A care companion for families</p>
          <h1 style={{ marginTop: 14 }}>
            Every instruction, <em>with its source.</em>
          </h1>
          <p className="lead">
            CareSaathi listens to the doctor visit, reads the prescriptions, and turns them into one living care plan.
            Every line points back to the page or the exact words it came from. Then it explains the plan aloud, in the language the patient trusts.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary" href="/family"><Icon name="users" /> {t("familyMode")}</Link>
            <Link className="btn btn-quiet" href="/elder"><Icon name="volume" /> {t("elderMode")}</Link>
            <Link className="btn btn-quiet" href="/e/demo-token"><Icon name="card" /> Emergency Card</Link>
          </div>
        </div>

        <div className="paper-demo" aria-hidden="true">
          <div><span className="ln">12</span>Hypertension</div>
          <div><span className="ln">13</span>Allergic to penicillin (rash)</div>
          <div><span className="ln">14</span><mark>Tab Metformin 500 mg 1-0-1 after food</mark></div>
          <div><span className="ln">15</span>Tab Amlodipine 5 mg 1-0-0</div>
          <div><span className="ln">16</span>Review in two weeks</div>
          <div className="margin-note">Care plan item · source: Discharge summary, p.1 line 14</div>
        </div>
      </section>

      <section className="facts" aria-label="What makes it different">
        <div className="card fact">
          <span className="icon-tile"><Icon name="quote" /></span>
          <h3>Sourced, not guessed</h3>
          <p>A line only enters the plan if its quote is found on the page. If the model cannot show where it read something, it is dropped.</p>
        </div>
        <div className="card fact">
          <span className="icon-tile"><Icon name="shield" /></span>
          <h3>Safe by construction</h3>
          <p>Allergy checks run in code against a reference list. Nothing is ever called safe. Unknown stays unknown, and every flag ends with a question for the doctor.</p>
        </div>
        <div className="card fact">
          <span className="icon-tile"><Icon name="volume" /></span>
          <h3>Voice first</h3>
          <p>One big button for the patient. Hindi, Marathi and English. The family confirms every change they heard in the clinic.</p>
        </div>
      </section>

      <p style={{ color: "var(--ink-3)", fontSize: 14.5, paddingBottom: 56 }}>
        CareSaathi is a care-coordination and document-organization tool. It does not give medical advice. Demo uses synthetic data only.
      </p>
    </div>
  );
}
