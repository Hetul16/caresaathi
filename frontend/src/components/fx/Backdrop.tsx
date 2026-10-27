// Fixed, decorative layers behind everything: a drifting aurora, a faint grid, film grain and a cursor glow.
// All motion is transform or opacity; it is switched off for reduced motion in motion.css.
export function Backdrop() {
  return (
    <div className="backdrop" aria-hidden="true">
      <i className="blob b1" /><i className="blob b2" /><i className="blob b3" />
      <i className="grid" /><i className="grain" /><i className="cursor-glow" />
    </div>
  );
}

// A hairline at the top of the window that fills as you scroll. Pure CSS (scroll-driven animation); absent where unsupported.
export function ScrollProgress() {
  return <div className="scroll-progress" aria-hidden="true" />;
}
