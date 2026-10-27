"use client";
import { useCallback, useEffect, useRef, useState } from "react";

// Records the microphone as mono, 16-bit PCM at 16 kHz in a WAV container: exactly what Muse Voice Transcribe's file endpoint accepts
// (docs: RIFF/WAVE, mono 16-bit PCM, 16 or 24 kHz, at most 10 minutes). No conversion is needed on the server. The audio stays in
// the browser until the person presses stop and chooses to send it.

const RATE = 16000;
export const MAX_SECONDS = 590;

const WORKLET = `class Pcm extends AudioWorkletProcessor {
  process(inputs) { const ch = inputs[0] && inputs[0][0]; if (ch) this.port.postMessage(ch.slice(0)); return true; }
}
registerProcessor("pcm", Pcm);`;

function resample(input: Float32Array, from: number, to: number): Float32Array {
  if (from === to) return input;
  const ratio = from / to;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const pos = i * ratio, i0 = Math.floor(pos), i1 = Math.min(i0 + 1, input.length - 1), f = pos - i0;
    out[i] = input[i0] * (1 - f) + input[i1] * f;
  }
  return out;
}

export function encodeWav(samples: Float32Array, rate = RATE): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const w = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);            // PCM, mono
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, "data"); v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const x = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true);
  }
  return new Blob([buf], { type: "audio/wav" });
}

export type RecState = "idle" | "starting" | "recording" | "denied" | "unsupported";

export function useWavRecorder() {
  const [state, setState] = useState<RecState>("idle");
  const [level, setLevel] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const chunks = useRef<Float32Array[]>([]);
  const parts = useRef<{ stream?: MediaStream; ctx?: AudioContext; node?: AudioWorkletNode; timer?: number; t0?: number }>({});

  const cleanup = useCallback(() => {
    const p = parts.current;
    if (p.timer) window.clearInterval(p.timer);
    p.node?.disconnect();
    p.stream?.getTracks().forEach((t) => t.stop());
    p.ctx?.close().catch(() => undefined);
    parts.current = {};
    setLevel(0);
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const start = useCallback(async () => {
    if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia || !window.AudioContext || !("audioWorklet" in AudioContext.prototype)) {
      setState("unsupported"); return false;
    }
    setState("starting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      let ctx: AudioContext;
      try { ctx = new AudioContext({ sampleRate: RATE }); } catch { ctx = new AudioContext(); }     // some browsers ignore the rate: we resample later
      const url = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));
      await ctx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      const node = new AudioWorkletNode(ctx, "pcm");
      chunks.current = [];
      node.port.onmessage = (e: MessageEvent<Float32Array>) => {
        chunks.current.push(e.data);
        let sum = 0;
        for (const x of e.data) sum += x * x;
        setLevel(Math.min(1, Math.sqrt(sum / e.data.length) * 5));
      };
      ctx.createMediaStreamSource(stream).connect(node);
      parts.current = { stream, ctx, node, t0: Date.now(), timer: window.setInterval(() => setSeconds(Math.floor((Date.now() - (parts.current.t0 ?? Date.now())) / 1000)), 500) };
      setSeconds(0);
      setState("recording");
      return true;
    } catch (e) {
      cleanup();
      setState(e instanceof DOMException && (e.name === "NotAllowedError" || e.name === "SecurityError") ? "denied" : "unsupported");
      return false;
    }
  }, [cleanup]);

  /** Stops and returns the recording as a WAV, or null if nothing was captured. */
  const stop = useCallback((): Blob | null => {
    const rate = parts.current.ctx?.sampleRate ?? RATE;
    const total = chunks.current.reduce((n, c) => n + c.length, 0);
    const all = new Float32Array(total);
    let o = 0;
    for (const c of chunks.current) { all.set(c, o); o += c.length; }
    chunks.current = [];
    cleanup();
    setState("idle");
    return total > rate * 0.5 ? encodeWav(resample(all, rate, RATE)) : null;      // under half a second is not a recording
  }, [cleanup]);

  return { state, level, seconds, start, stop };
}
