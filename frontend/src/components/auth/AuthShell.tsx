import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "../SiteHeader";
import { Icon, type IconName } from "../Icon";

const points: { icon: IconName; title: string; body: string }[] = [
  { icon: "quote", title: "Every line has a source", body: "A page and line number, or the doctor's exact words." },
  { icon: "shield", title: "Never says “safe”", body: "Allergy checks run in code. Every flag ends in a question for the doctor." },
  { icon: "users", title: "Your family decides", body: "Nothing from a visit enters the plan until a named person confirms." },
];

export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="auth">
      <aside className="auth-art" aria-hidden="false">
        <Link href="/" className="auth-brand"><Logo /><span>CareSaathi</span></Link>
        <div className="auth-art-body">
          <p className="eyebrow" style={{ color: "var(--marigold)" }}>A care companion for families</p>
          <h2>Care for the people who cared for you, <em>without losing a single instruction.</em></h2>
          <ul className="auth-points">
            {points.map((p) => (
              <li key={p.title}>
                <span className="auth-ic"><Icon name={p.icon} /></span>
                <div><strong>{p.title}</strong><span>{p.body}</span></div>
              </li>
            ))}
          </ul>
        </div>
        <svg className="auth-thread" viewBox="0 0 400 400" aria-hidden="true">
          <path d="M-20 320 C 80 260, 120 380, 220 300 S 380 180, 440 220" />
          <path d="M-20 360 C 100 300, 160 420, 260 340 S 400 240, 460 280" />
        </svg>
      </aside>

      <section className="auth-form-wrap">
        <div className="auth-form">
          <Link href="/" className="auth-brand auth-brand-mobile"><Logo /><span>CareSaathi</span></Link>
          <h1>{title}</h1>
          <p className="auth-sub">{subtitle}</p>
          {children}
          <div className="auth-foot">{footer}</div>
          <p className="auth-legal">
            CareSaathi is a care-coordination and document-organization tool. It does not give medical advice.
            This build uses synthetic data only.
          </p>
        </div>
      </section>
    </div>
  );
}
