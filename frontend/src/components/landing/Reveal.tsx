"use client";
import { useEffect, useRef, useState, type ElementType, type ReactNode } from "react";

// Fades a block in once it scrolls into view. With reduced motion, or without IntersectionObserver, it just shows.
export function Reveal({ children, as: Tag = "div", delay = 0, className = "" }: { children: ReactNode; as?: ElementType; delay?: number; className?: string }) {
  const ref = useRef<HTMLElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } }, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return <Tag ref={ref} className={`reveal ${shown ? "in" : ""} ${className}`} style={{ transitionDelay: `${delay}ms` }}>{children}</Tag>;
}
