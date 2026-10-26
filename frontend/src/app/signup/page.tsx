"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { Field, StrengthMeter } from "@/components/auth/Field";
import { Icon } from "@/components/Icon";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

type Via = "email" | "phone";

export default function SignupPage() {
  const { register, status } = useAuth();
  const { lang } = useI18n();
  const router = useRouter();
  const [name, setName] = useState("");
  const [via, setVia] = useState<Via>("email");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [agree, setAgree] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (status === "authed") router.replace("/app"); }, [status, router]);

  function validate() {
    const e: Record<string, string> = {};
    if (!name.trim()) e.display_name = "Tell us what to call you";
    if (via === "email" && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) e.email = "Enter a valid email address";
    if (via === "phone" && !/^\+[1-9][0-9]{6,14}$/.test(phone.replace(/[\s-]/g, ""))) e.phone = "Use international format, for example +919876543210";
    if (password.length < 10) e.password = "Use at least 10 characters";
    if (!agree) e.agree = "Please confirm to continue";
    return e;
  }

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    setFormError("");
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      await register({ display_name: name.trim(), password, preferred_language: lang, ...(via === "email" ? { email } : { phone }) });
      router.replace("/onboarding");
    } catch (err) {
      if (err instanceof ApiError) {
        const fe: Record<string, string> = {};
        for (const x of err.errors) fe[x.field] = x.message;
        setErrors(fe);
        setFormError(err.errors.length ? "" : `${err.title}. ${err.detail}`.trim());
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your family’s account"
      subtitle="You will add your relative next. It takes about a minute."
      footer={<>Already have an account? <Link href="/login">Sign in</Link></>}
    >
      <form onSubmit={submit} noValidate className="auth-fields">
        <Field label="Your name" value={name} onChange={setName} error={errors.display_name} autoComplete="name" placeholder="Priya Kulkarni" />

        <div className="seg" role="group" aria-label="Sign up with">
          <button type="button" aria-pressed={via === "email"} onClick={() => setVia("email")}>Email</button>
          <button type="button" aria-pressed={via === "phone"} onClick={() => setVia("phone")}>Phone</button>
        </div>
        {via === "email"
          ? <Field label="Email" type="email" value={email} onChange={setEmail} error={errors.email} autoComplete="email" inputMode="email" placeholder="you@example.com" />
          : <Field label="Mobile number" type="tel" value={phone} onChange={setPhone} error={errors.phone} autoComplete="tel" inputMode="tel" placeholder="+91 98765 43210" hint="Include the country code." />}

        <div>
          <Field label="Password" type="password" value={password} onChange={setPassword} error={errors.password} autoComplete="new-password" hint="At least 10 characters. A short sentence works well." />
          <StrengthMeter password={password} />
        </div>

        <label className={`check ${errors.agree ? "has-error" : ""}`}>
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>I understand CareSaathi organizes documents and asks questions. It does not give medical advice.</span>
        </label>
        {errors.agree && <p className="field-error" role="alert"><Icon name="alert" className="icon" /> {errors.agree}</p>}

        {formError && <div className="form-error" role="alert"><Icon name="alert" /> {formError}</div>}
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
        <Link href="/demo" className="btn btn-quiet btn-block"><Icon name="sparkle" /> Explore the demo without an account</Link>
      </form>
    </AuthShell>
  );
}
