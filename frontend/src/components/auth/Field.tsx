"use client";
import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { Icon } from "../Icon";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "onChange"> {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  hint?: ReactNode;
}

export function Field({ label, value, onChange, error, hint, type = "text", ...rest }: Props) {
  const id = useId();
  const [show, setShow] = useState(false);
  const isPw = type === "password";
  const describedBy = [error ? `${id}-err` : null, hint ? `${id}-hint` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`field ${error ? "has-error" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <div className="field-box">
        <input
          id={id}
          type={isPw && show ? "text" : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...rest}
        />
        {isPw && (
          <button type="button" className="field-eye" onClick={() => setShow((s) => !s)} aria-pressed={show} aria-label={show ? "Hide password" : "Show password"}>
            <span>{show ? "Hide" : "Show"}</span>
          </button>
        )}
      </div>
      {hint && !error && <p className="field-hint" id={`${id}-hint`}>{hint}</p>}
      {error && <p className="field-error" id={`${id}-err`} role="alert"><Icon name="alert" className="icon" /> {error}</p>}
    </div>
  );
}

// Strength is only guidance. The server enforces the real rule (at least 10 characters).
export function passwordStrength(pw: string): { score: 0 | 1 | 2 | 3 | 4; label: string } {
  if (!pw) return { score: 0, label: "" };
  let s = 0;
  if (pw.length >= 10) s++;
  if (pw.length >= 14) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s++;
  const score = Math.min(4, s) as 0 | 1 | 2 | 3 | 4;
  return { score, label: ["Too short", "Okay", "Good", "Strong", "Very strong"][score] };
}

export function StrengthMeter({ password }: { password: string }) {
  const { score, label } = passwordStrength(password);
  if (!password) return null;
  return (
    <div className="strength" aria-live="polite">
      <div className="strength-bars" data-score={score}>{[1, 2, 3, 4].map((i) => <span key={i} className={i <= score ? "on" : ""} />)}</div>
      <span>{label}</span>
    </div>
  );
}
