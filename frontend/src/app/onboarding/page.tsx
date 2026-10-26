"use client";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AppGate } from "@/components/AppGate";
import { Field } from "@/components/auth/Field";
import { Icon } from "@/components/Icon";
import { api, ApiError } from "@/lib/api";
import { writeSelected } from "@/lib/live";
import type { Lang } from "@/lib/types";

const LANGS: [Lang, string, string][] = [["hi", "हिन्दी", "Hindi"], ["mr", "मराठी", "Marathi"], ["en", "English", "English"]];

function Form() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [rel, setRel] = useState("");
  const [lang, setLang] = useState<Lang>("hi");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    setFormError("");
    if (!name.trim()) { setErrors({ full_name: "Enter their name" }); return; }
    setErrors({});
    setBusy(true);
    try {
      const p = await api<{ id: string }>("/patients", {
        method: "POST",
        json: { full_name: name.trim(), date_of_birth: dob || null, preferred_language: lang, relationship_label: rel.trim() || null },
      });
      writeSelected(p.id);
      router.replace("/app");
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) setErrors(Object.fromEntries(err.errors.map((e) => [e.field, e.message])));
      else setFormError(err instanceof ApiError ? `${err.title}. ${err.detail}` : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap" style={{ maxWidth: 640, padding: "44px 0 80px" }}>
      <p className="eyebrow">Step 1 of 1</p>
      <h1 style={{ fontSize: "clamp(32px,5vw,46px)", margin: "8px 0 8px" }}>Who are you looking after?</h1>
      <p style={{ color: "var(--ink-2)", marginBottom: 24 }}>
        This builds their care plan. You can add more relatives and family members later. For this build, please use a fictional person.
      </p>
      <form onSubmit={submit} noValidate className="card card-pad auth-fields">
        <Field label="Their name" value={name} onChange={setName} error={errors.full_name} placeholder="Ramesh Kulkarni" />
        <Field label="Date of birth (optional)" type="date" value={dob} onChange={setDob} error={errors.date_of_birth} />
        <Field label="Your relationship (optional)" value={rel} onChange={setRel} placeholder="Daughter" />
        <fieldset className="lang-pick">
          <legend>Language they are most comfortable in</legend>
          <div className="seg">
            {LANGS.map(([code, native, en]) => (
              <button key={code} type="button" aria-pressed={lang === code} onClick={() => setLang(code)}>
                <span lang={code} style={{ fontSize: 18 }}>{native}</span><small>{en}</small>
              </button>
            ))}
          </div>
        </fieldset>
        {formError && <div className="form-error" role="alert"><Icon name="alert" /> {formError}</div>}
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Creating…" : "Continue to the care plan"}</button>
      </form>
    </div>
  );
}

export default function Onboarding() {
  return <AppGate><Form /></AppGate>;
}
