"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "@/lib/i18n";
import type { Lang } from "@/lib/types";

export function Logo() {
  // Two figures sharing one roof line: a companion walking beside you.
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <rect x="1" y="1" width="38" height="38" rx="11" fill="var(--ink)" />
      <path d="M8 22 20 11l12 11" fill="none" stroke="var(--marigold)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="15" cy="25" r="3" fill="var(--paper)" />
      <circle cx="25" cy="25" r="3" fill="var(--paper)" />
      <path d="M11 33c0-3 2-5 4-5s4 2 4 5M21 33c0-3 2-5 4-5s4 2 4 5" fill="none" stroke="var(--paper)" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

const LANGS: { code: Lang; label: string; name: string }[] = [
  { code: "en", label: "EN", name: "English" },
  { code: "hi", label: "हिं", name: "हिन्दी" },
  { code: "mr", label: "मरा", name: "मराठी" },
];

export function SiteHeader() {
  const { lang, setLang, t } = useI18n();
  const path = usePathname();
  if (path?.startsWith("/e/")) return null; // the public Emergency Card is a clean, standalone page
  return (
    <header className="site-header">
      <div className="wrap">
        <Link className="brand" href="/" aria-label="CareSaathi home">
          <Logo />
          <span>{t("appName")}</span>
        </Link>
        <div className="lang-switch" role="group" aria-label="Language">
          {LANGS.map((l) => (
            <button key={l.code} type="button" aria-pressed={lang === l.code} aria-label={l.name} onClick={() => setLang(l.code)}>
              {l.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
