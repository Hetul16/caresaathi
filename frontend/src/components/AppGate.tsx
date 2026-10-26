"use client";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";

// Client-side gate for signed-in pages. The API enforces the real access rules; this only avoids showing a
// signed-out visitor an empty shell.
export function AppGate({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  useEffect(() => { if (status === "anon") router.replace("/login"); }, [status, router]);
  if (status !== "authed") {
    return (
      <div className="center-page" aria-busy="true">
        <div><div className="spinner" aria-hidden="true" /><p style={{ marginTop: 14, color: "var(--ink-2)" }}>Opening your care plan…</p></div>
      </div>
    );
  }
  return <>{children}</>;
}
