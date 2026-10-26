"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { Field } from "@/components/auth/Field";
import { Icon } from "@/components/Icon";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, status } = useAuth();
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (status === "authed") router.replace("/app"); }, [status, router]);

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    setFormError("");
    const e: Record<string, string> = {};
    if (identifier.trim().length < 3) e.identifier = "Enter your email or mobile number";
    if (!password) e.password = "Enter your password";
    setErrors(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      await login(identifier.trim(), password);
      router.replace("/app");
    } catch (err) {
      // The server gives one answer for "no such account" and "wrong password" on purpose.
      setFormError(err instanceof ApiError ? `${err.title}.` : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to see your family’s care plan."
      footer={<>New to CareSaathi? <Link href="/signup">Create an account</Link></>}
    >
      <form onSubmit={submit} noValidate className="auth-fields">
        <Field label="Email or mobile number" value={identifier} onChange={setIdentifier} error={errors.identifier} autoComplete="username" placeholder="you@example.com" />
        <Field label="Password" type="password" value={password} onChange={setPassword} error={errors.password} autoComplete="current-password" />
        {formError && <div className="form-error" role="alert"><Icon name="alert" /> {formError}</div>}
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <Link href="/demo" className="btn btn-quiet btn-block"><Icon name="sparkle" /> Explore the demo without an account</Link>
      </form>
    </AuthShell>
  );
}
