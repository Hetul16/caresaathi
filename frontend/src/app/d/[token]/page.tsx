import type { Metadata } from "next";
import { headers } from "next/headers";
import { DoctorView } from "@/components/DoctorView";
import { Icon } from "@/components/Icon";
import type { DoctorPage } from "@/lib/types";

export const instant = false; // dynamic public page: the token is runtime data

export const metadata: Metadata = { title: "Shared care plan", robots: { index: false, follow: false }, referrer: "no-referrer" };
const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

function Unavailable() {
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

// Public, read-only page for one doctor. The API checks the random token, logs the visit, and answers the same way for unknown, expired and revoked links.
export default async function DoctorLinkPage(props: PageProps<"/d/[token]">) {
  const { token } = await props.params;
  const h = await headers();
  try {
    const res = await fetch(`${BACKEND}/api/v1/d/${encodeURIComponent(token)}`, {
      cache: "no-store", headers: { "user-agent": h.get("user-agent") ?? "", "x-forwarded-for": h.get("x-forwarded-for") ?? "" },
    });
    if (!res.ok) return <Unavailable />;
    return <DoctorView token={token} initial={(await res.json()) as DoctorPage} />;
  } catch {
    return <Unavailable />;
  }
}
