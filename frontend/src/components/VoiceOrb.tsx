"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { Icon } from "./Icon";

export type OrbState = "idle" | "listening" | "speaking";

// Real microphone level drives the orb. The audio is NOT sent anywhere from this component; the
// backend voice socket (docs/15-api-spec.md section 5) is wired in a later step.
export function useMicLevel(active: boolean) {
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!active) { setLevel(0); return; }
    let raf = 0;
    let stream: MediaStream | undefined;
    let ctx: AudioContext | undefined;
    let cancelled = false;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        ctx = new AudioContext();
        const src = ctx.createMediaStreamSource(stream);
        const an = ctx.createAnalyser();
        an.fftSize = 256;
        src.connect(an);
        const buf = new Uint8Array(an.frequencyBinCount);
        const tick = () => {
          an.getByteTimeDomainData(buf);
          let sum = 0;
          for (const v of buf) sum += ((v - 128) / 128) ** 2;
          setLevel(Math.min(1, Math.sqrt(sum / buf.length) * 4));
          raf = requestAnimationFrame(tick);
        };
        tick();
      } catch {
        setError("mic");
      }
    })();
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
      ctx?.close();
    };
  }, [active]);
  return { level, error };
}

export function VoiceOrb({ state, onToggle, level }: { state: OrbState; onToggle: () => void; level: number }) {
  const { t } = useI18n();
  const label = state === "listening" ? t("listening") : state === "speaking" ? t("speaking") : t("tapToSpeak");
  return (
    <div className="orb-stage">
      <div className="orb-wrap" data-state={state}>
        <span className="orb-ring" /><span className="orb-ring" /><span className="orb-ring" />
        <button
          type="button"
          className="orb"
          onClick={onToggle}
          style={{ ["--level" as string]: level }}
          aria-pressed={state === "listening"}
          aria-label={label}
        >
          <Icon name={state === "speaking" ? "volume" : "mic"} />
        </button>
      </div>
      <p className="orb-label" aria-live="polite">{label}</p>
    </div>
  );
}

// Interim text-to-speech with the browser voice. The product voice comes from the TTS provider chosen in D-08.
//
// The voices belong to the viewer's device, not to us (D-65). Many Windows and desktop Linux machines ship no Hindi or Marathi voice at all.
// Setting `lang = "hi-IN"` on such a machine does not fail: the browser quietly hands the Devanagari text to an English voice, which reads
// nonsense to someone who may not be able to read the screen. So the voice is chosen explicitly, and when the language has none we say so
// instead of speaking it badly.
function pickVoice(voices: SpeechSynthesisVoice[], locale: string): SpeechSynthesisVoice | null {
  const base = locale.split("-")[0].toLowerCase();
  return voices.find((v) => v.lang.replace("_", "-").toLowerCase() === locale.toLowerCase())
      ?? voices.find((v) => v.lang.replace("_", "-").toLowerCase().startsWith(base + "-"))
      ?? voices.find((v) => v.lang.toLowerCase() === base)
      ?? null;
}

export function useSpeech(locale: string) {
  const [speaking, setSpeaking] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const last = useRef<{ text: string; rate: number } | null>(null);

  // The list arrives asynchronously in most browsers, and on some it is empty until the event fires.
  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const read = () => setVoices(window.speechSynthesis.getVoices());
    read();
    window.speechSynthesis.addEventListener("voiceschanged", read);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", read);
  }, []);

  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const voice = useMemo(() => pickVoice(voices, locale), [voices, locale]);
  // Unknown until the list loads; false means this device has no voice for that language.
  const available = voices.length === 0 ? null : voice !== null;

  const speak = useCallback((text: string, rate = 0.9) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const v = pickVoice(window.speechSynthesis.getVoices(), locale);
    if (!v) return;                       // no voice for this language: stay silent rather than read it in the wrong one
    window.speechSynthesis.cancel();
    last.current = { text, rate };
    const u = new SpeechSynthesisUtterance(text);
    u.voice = v;
    u.lang = v.lang;
    u.rate = rate;
    u.onstart = () => setSpeaking(true);
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(u);
  }, [locale]);

  const repeat = useCallback((slower = false) => {
    if (last.current) speak(last.current.text, slower ? Math.max(0.6, last.current.rate - 0.2) : last.current.rate);
  }, [speak]);

  const stop = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  useEffect(() => stop, [stop]);
  return { speak, repeat, stop, speaking, available, supported, voiceName: voice?.name ?? null };
}
