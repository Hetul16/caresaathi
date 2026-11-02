"use client";
import { useEffect } from "react";

// One pointer listener for the whole app (event delegation, one rAF per frame). It feeds CSS variables only:
//   --mx / --my  on the nearest .card or .fx under the pointer: the spotlight border and glow
//   --tx / --ty  on [data-tilt]: a gentle 3D tilt
//   --cx / --cy  on <html>: the large glow that trails the cursor
//   --mag-x/y    on [data-magnetic]: buttons lean toward the pointer
// Skipped entirely for touch screens and for people who asked for less motion.
export function FxProvider() {
  useEffect(() => {
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!fine.matches || calm.matches) return;

    const root = document.documentElement;
    let raf = 0;
    let ev: PointerEvent | null = null;
    let glowX = window.innerWidth / 2, glowY = window.innerHeight / 3, targetX = glowX, targetY = glowY, glowRaf = 0;
    let lastTilt: HTMLElement | null = null, lastMag: HTMLElement | null = null;

    const follow = () => {
      glowX += (targetX - glowX) * 0.12; glowY += (targetY - glowY) * 0.12;
      root.style.setProperty("--cx", `${glowX.toFixed(1)}px`); root.style.setProperty("--cy", `${glowY.toFixed(1)}px`);
      glowRaf = Math.abs(targetX - glowX) + Math.abs(targetY - glowY) > 0.5 ? requestAnimationFrame(follow) : 0;
    };

    const frame = () => {
      raf = 0;
      if (!ev) return;
      const t = ev.target as HTMLElement | null;
      targetX = ev.clientX; targetY = ev.clientY;
      if (!glowRaf) glowRaf = requestAnimationFrame(follow);

      const fx = t?.closest?.<HTMLElement>(".card, .fx") ?? null;
      if (fx) { const r = fx.getBoundingClientRect(); fx.style.setProperty("--mx", `${ev.clientX - r.left}px`); fx.style.setProperty("--my", `${ev.clientY - r.top}px`); }

      const tilt = t?.closest?.<HTMLElement>("[data-tilt], .trio-card") ?? null;
      if (lastTilt && lastTilt !== tilt) { lastTilt.style.removeProperty("--tx"); lastTilt.style.removeProperty("--ty"); }
      if (tilt) {
        const r = tilt.getBoundingClientRect();
        tilt.style.setProperty("--tx", `${(((ev.clientX - r.left) / r.width) - 0.5).toFixed(3)}`);
        tilt.style.setProperty("--ty", `${(((ev.clientY - r.top) / r.height) - 0.5).toFixed(3)}`);
      }
      lastTilt = tilt;

      const mag = t?.closest?.<HTMLElement>("[data-magnetic]") ?? null;
      if (lastMag && lastMag !== mag) { lastMag.style.removeProperty("--mag-x"); lastMag.style.removeProperty("--mag-y"); }
      if (mag) {
        const r = mag.getBoundingClientRect();
        mag.style.setProperty("--mag-x", `${((ev.clientX - (r.left + r.width / 2)) * 0.18).toFixed(1)}px`);
        mag.style.setProperty("--mag-y", `${((ev.clientY - (r.top + r.height / 2)) * 0.28).toFixed(1)}px`);
      }
      lastMag = mag;
    };

    const onMove = (e: PointerEvent) => { ev = e; if (!raf) raf = requestAnimationFrame(frame); };
    const onLeave = () => {
      lastTilt?.style.removeProperty("--tx"); lastTilt?.style.removeProperty("--ty");
      lastMag?.style.removeProperty("--mag-x"); lastMag?.style.removeProperty("--mag-y");
      lastTilt = lastMag = null;
    };
    root.classList.add("fx-on");
    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    return () => {
      window.removeEventListener("pointermove", onMove); document.removeEventListener("pointerleave", onLeave);
      cancelAnimationFrame(raf); cancelAnimationFrame(glowRaf); root.classList.remove("fx-on");
    };
  }, []);
  return null;
}
