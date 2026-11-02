"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { SourceRef } from "@/lib/types";
import { Icon } from "./Icon";

const Ctx = createContext<(s: SourceRef) => void>(() => {});
export const useOpenSource = () => useContext(Ctx);

function mmss(ms: number) {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function describe(src: SourceRef): string {
  if (src.kind === "document") return `${src.document_title}, p.${src.page}${src.line_start ? ` line ${src.line_start}` : ""}`;
  if (src.kind === "visit_segment") return src.speaker ? `${src.speaker}, visit${src.at_ms != null ? ` at ${mmss(src.at_ms)}` : ""}` : "The doctor's words, from the visit";
  if (src.kind === "doctor_message") return "The doctor's reply, in the doctor link";
  return src.stated_by ? `Said by ${src.stated_by}` : "Said by a family member";
}

export function SourceProvider({ children }: { children: ReactNode }) {
  const [src, setSrc] = useState<SourceRef | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);

  const open = useCallback((s: SourceRef) => {
    opener.current = document.activeElement as HTMLElement | null;
    setSrc(s);
  }, []);
  const close = useCallback(() => {
    setSrc(null);
    opener.current?.focus();
  }, []);

  useEffect(() => {
    if (!src) return;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [src, close]);

  return (
    <Ctx.Provider value={open}>
      {children}
      {src && (
        <>
          <div className="scrim" onClick={close} />
          <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="src-title">
            <div className="drawer-head">
              <div>
                <p className="eyebrow">Show source</p>
                <h2 id="src-title">{src.kind === "document" ? src.document_title : src.kind === "visit_segment" ? "Doctor visit recording" : src.kind === "doctor_message" ? "The doctor's reply" : "Family input"}</h2>
              </div>
              <button ref={closeBtn} className="btn btn-quiet btn-sm" onClick={close} aria-label="Close">
                <Icon name="x" />
              </button>
            </div>

            {src.kind === "document" && (
              <div className="sheet" aria-label="Source document excerpt">
                <div className="dim"><span className="ln">…</span>page {src.page}</div>
                <div>
                  <span className="ln">{src.line_start ?? "·"}</span>
                  <mark>{src.quote}</mark>
                </div>
                <div className="dim"><span className="ln">…</span></div>
              </div>
            )}
            {src.kind === "visit_segment" && (
              <div className="sheet">
                <p className="dim" style={{ marginBottom: 8 }}>{src.speaker ?? "Doctor"}{src.at_ms != null ? ` · ${mmss(src.at_ms)}` : ""}</p>
                <blockquote><mark>{src.quote}</mark></blockquote>
              </div>
            )}
            {src.kind === "doctor_message" && (
              <div className="sheet">
                <p className="dim" style={{ marginBottom: 8 }}>The doctor&apos;s exact words, written in the doctor link</p>
                <blockquote><mark>{src.quote}</mark></blockquote>
              </div>
            )}
            {src.kind === "family_input" && (
              <div className="sheet">
                <p className="dim" style={{ marginBottom: 8 }}>{src.stated_by ?? "Family member"}</p>
                <blockquote><mark>{src.quote}</mark></blockquote>
              </div>
            )}
            <p style={{ marginTop: 14, color: "var(--ink-2)", fontSize: 15 }}>
              This is the exact text the item was taken from. If it looks wrong, do not rely on the item: ask the doctor or pharmacist.
            </p>
          </aside>
        </>
      )}
    </Ctx.Provider>
  );
}

export function SourceChip({ source, short = false }: { source: SourceRef; short?: boolean }) {
  const open = useOpenSource();
  return (
    <button type="button" className="source-chip" onClick={() => open(source)} aria-label={`Show source: ${describe(source)}`}>
      <Icon name="quote" />
      {short ? "Show source" : describe(source)}
    </button>
  );
}
