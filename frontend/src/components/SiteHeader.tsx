"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Lang } from "@/lib/types";

export function Logo() {
  // Two figures under one roof line: a companion walking beside you.
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <rect x="1" y="1" width="38" height="38" rx="12" fill="var(--signal)" />
      <path d="M8 22 20 11l12 11" fill="none" stroke="var(--on-signal)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="15" cy="25" r="3" fill="var(--on-signal)" />
      <circle cx="25" cy="25" r="3" fill="var(--on-signal)" />
      <path d="M11 33c0-3 2-5 4-5s4 2 4 5M21 33c0-3 2-5 4-5s4 2 4 5" fill="none" stroke="var(--on-signal)" strokeWidth="2.2" strokeLinecap="round" />
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
  const { status, user, logout } = useAuth();
  const path = usePathname() ?? "";
  const router = useRouter();
  // Standalone pages: the public Emergency Card and the split-screen sign-in pages carry their own chrome.
  if (path.startsWith("/e/") || path === "/login" || path === "/signup") return null;
  const initials = (user?.display_name ?? "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <header className="site-header">
      <div className="wrap">
        <Link className="brand" href="/" aria-label="CareSaathi home">
          <Logo />
          <span>{t("appName")}</span>
        </Link>
        <div className="header-actions">
          <Link href="/trust" className="btn btn-quiet btn-sm hide-sm">Trust</Link>
          <div className="lang-switch" role="group" aria-label="Language">
            {LANGS.map((l) => (
              <button key={l.code} type="button" aria-pressed={lang === l.code} aria-label={l.name} onClick={() => setLang(l.code)}>
                {l.label}
              </button>
            ))}
          </div>
          {status === "authed" ? (
            <>
              {!path.startsWith("/app") && <Link href="/app" className="btn btn-primary btn-sm">Open care plan</Link>}
              <button className="avatar" onClick={async () => { await logout(); router.replace("/"); }} aria-label={`Signed in as ${user?.display_name}. Sign out`} title="Sign out">
                {initials}
              </button>
            </>
          ) : status === "anon" ? (
            <>
              <Link href="/login" className="btn btn-quiet btn-sm hide-sm">Sign in</Link>
              <Link href="/signup" className="btn btn-primary btn-sm">Get started</Link>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
