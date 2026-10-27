import type { Metadata } from "next";
import { headers } from "next/headers";
import { CardView } from "@/components/CardView";
import { Icon } from "@/components/Icon";
import { mockCard } from "@/lib/mock";
import type { EmergencyCardData } from "@/lib/types";

export const instant = false; // dynamic public page: the token is runtime data

export const metadata: Metadata = {
  title: "Emergency Card",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

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

// Public, read-only page. The API validates the random token, logs the access, and answers the same way for
// unknown, expired and revoked links; this page then shows one neutral message (docs/13-architecture.md section 4.4).
export default async function EmergencyCardPage(props: PageProps<"/e/[token]">) {
  const { token } = await props.params;
  if (token === "demo-token") return <CardView c={mockCard} />;

  const h = await headers();
  try {
    const res = await fetch(`${BACKEND}/api/v1/e/${encodeURIComponent(token)}`, {
      cache: "no-store",
      headers: { "user-agent": h.get("user-agent") ?? "", "x-forwarded-for": h.get("x-forwarded-for") ?? "" },
    });
    if (!res.ok) return <Unavailable />;
    return <CardView c={(await res.json()) as EmergencyCardData} />;
  } catch {
    return <Unavailable />;
  }
}
