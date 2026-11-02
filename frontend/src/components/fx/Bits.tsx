"use client";
import { Fragment, useEffect, useRef, useState, type ElementType, type ReactNode } from "react";
import { afterCommit } from "@/lib/defer";

// Splits a heading into words that rise out of a mask one after another. The full text stays in one
// aria-label, so a screen reader hears the sentence, not the pieces.
export function SplitText({ text, as: Tag = "span", className = "", start = 0, step = 70 }: { text: string; as?: ElementType; className?: string; start?: number; step?: number }) {
  return (
    <Tag className={`split ${className}`} aria-label={text}>
      {text.split(" ").map((w, i) => (
        // The space sits between the inline-blocks, not inside one: trailing whitespace in an inline-block collapses.
        <Fragment key={i}>
          {i > 0 && " "}
          <span className="split-w" aria-hidden="true"><span style={{ animationDelay: `${start + i * step}ms` }}>{w}</span></span>
        </Fragment>
      ))}
    </Tag>
  );
}

// Counts up to a number the first time it scrolls into view. With reduced motion it simply shows the number.
export function CountUp({ to, suffix = "", duration = 1400 }: { to: number; suffix?: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Nothing to animate: show the number, but after this commit rather than during it.
    if (typeof IntersectionObserver === "undefined") { afterCommit(() => setN(to)); return; }
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      if (still) { setN(to); return; }
      const t0 = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - t0) / duration);
        setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, { threshold: 0.6 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to, duration]);
  return <span ref={ref} aria-label={`${to}${suffix}`}>{n}{suffix}</span>;
}

// An endless ticker. Duplicated once so the loop is seamless; the copy is hidden from assistive tech.
export function Marquee({ children, speed = 38 }: { children: ReactNode; speed?: number }) {
  return (
    <div className="marquee" style={{ ["--speed" as string]: `${speed}s` }}>
      <div className="marquee-track">
        <div className="marquee-set">{children}</div>
        <div className="marquee-set" aria-hidden="true">{children}</div>
      </div>
    </div>
  );
}
