"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { clearPendingJoin, rememberJoin } from "@/lib/join";
import { writeSelected } from "@/lib/live";
import { Icon } from "@/components/Icon";

// An invitation link. If you are signed in it joins at once; otherwise it is remembered for the moment you sign in or sign up.
export function JoinClient({ code }: { code: string }) {
  const { status } = useAuth();
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  // Signed out is read straight from the session rather than copied into state, so there is nothing to keep in step.
  const state = failed ? "bad" : status === "anon" ? "anon" : "working";

  useEffect(() => {
    if (status === "loading") return;
    if (status === "anon") { rememberJoin(code); return; }
    api<{ patient_id: string }>("/invites/accept", { method: "POST", json: { code } })
      .then((r) => { clearPendingJoin(); writeSelected(r.patient_id); router.replace("/app"); })
      .catch(() => { clearPendingJoin(); setFailed(true); });
  }, [status, code, router]);

  return (
    <div className="center-page">
      <div style={{ maxWidth: 480 }}>
        <Icon name="users" />
        {state === "working" && <><h1 style={{ fontSize: 30, marginTop: 10 }}>Joining the family…</h1><div className="spinner" style={{ marginTop: 16 }} aria-hidden="true" /></>}
        {state === "anon" && (
          <>
            <h1 style={{ fontSize: 30, marginTop: 10 }}>You have been invited to a family&apos;s care plan</h1>
            <p style={{ color: "var(--ink-2)", margin: "10px 0 20px" }}>Sign in, or make a free account, and you will join straight away.</p>
            <div className="hero-actions" style={{ justifyContent: "center" }}>
              <Link className="btn btn-primary btn-lg" href="/signup">Create an account</Link>
              <Link className="btn btn-quiet btn-lg" href="/login">Sign in</Link>
            </div>
          </>
        )}
        {state === "bad" && (
          <>
            <h1 style={{ fontSize: 30, marginTop: 10 }}>This invitation is not available</h1>
            <p style={{ color: "var(--ink-2)", margin: "10px 0 20px" }}>It may have been used already, expired, or been withdrawn. Ask the family to send a new one.</p>
            <Link className="btn btn-quiet" href="/app">Go to your care plan</Link>
          </>
        )}
      </div>
    </div>
  );
}
