"""Measures Muse Voice Transcribe on REAL human Hindi and Marathi speech from the public FLEURS test set (Google, CC BY 4.0).

    cd backend
    python scripts\\speech_eval.py              # 12 clips per language, about $0.02
    python scripts\\speech_eval.py --clips 20

FLEURS is read speech (sentences from Wikipedia text), not doctor-visit conversation, so this measures how well the model hears Hindi and
Marathi voices, NOT how well it follows a Hinglish consultation. The Trust page says so. Only the first part of each archive is downloaded
(HTTP range request); nothing here is stored in the repository except the result. No patient data is involved.
Writes the result into data/live_results/latest.json under "speech" (run live_report.py first, or this creates the file)."""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import spend  # noqa: E402
from app.clients.models import ModelError, get_model_client  # noqa: E402
from app.config import get_settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "live_results" / "latest.json"
HF = "https://huggingface.co/datasets/google/fleurs/resolve/main/data"
LANGS = {"hi_in": "Hindi", "mr_in": "Marathi"}
_PUNCT = re.compile(r"[।॥.,!?;:\"'()\[\]{}\-–—‘’“”]")


def norm(s: str) -> list[str]:
    return _PUNCT.sub(" ", s.casefold()).split()


def edit_distance(a: list[str], b: list[str]) -> int:
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return d[len(b)]


def to_pcm16(wav: bytes) -> bytes:
    """FLEURS files are 32-bit float WAV; the Meta endpoint wants mono 16-bit PCM at 16 or 24 kHz. Converts float to 16-bit, nothing else."""
    import array
    import struct
    i, fmt, data = 12, None, b""
    while i + 8 <= len(wav):
        cid, size = wav[i:i + 4], struct.unpack("<I", wav[i + 4:i + 8])[0]
        body = wav[i + 8:i + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            data = body
            break
        i += 8 + size + (size & 1)
    if fmt is None or not data:
        raise ValueError("not a WAV file")
    tag, channels, rate, _, _, bits = fmt
    if tag == 1 and bits == 16:
        return wav
    if tag != 3 or bits != 32 or channels != 1:
        raise ValueError(f"unsupported WAV (format {tag}, {bits} bit, {channels} channels)")
    floats = array.array("f")
    floats.frombytes(data[: len(data) // 4 * 4])
    pcm = array.array("h", (max(-32768, min(32767, int(round(x * 32767)))) for x in floats))
    body = pcm.tobytes()
    return b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(body)) + body


def clips(lang: str, n: int, nbytes: int) -> list[tuple[str, bytes, str]]:
    """The first n test clips (wav bytes and reference text) from the start of the archive."""
    tsv = httpx.get(f"{HF}/{lang}/test.tsv", follow_redirects=True, timeout=60).text
    refs = {row[1]: row[3] for row in csv.reader(io.StringIO(tsv), delimiter="\t") if len(row) > 3}
    with httpx.stream("GET", f"{HF}/{lang}/audio/test.tar.gz", follow_redirects=True, timeout=180, headers={"Range": f"bytes=0-{nbytes}"}) as r:
        blob = r.read()
    out: list[tuple[str, bytes, str]] = []
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r|gz") as tar:
            for m in tar:
                name = Path(m.name).name
                if m.isfile() and name in refs and len(out) < n:
                    f = tar.extractfile(m)
                    if f is not None:
                        out.append((name, f.read(), refs[name]))
                if len(out) >= n:
                    break
    except (tarfile.ReadError, EOFError):
        pass                                            # the download was cut on purpose; the clips read so far are enough
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=int, default=12)
    ap.add_argument("--bytes", type=int, default=24_000_000)
    a = ap.parse_args()
    cfg = get_settings()
    if cfg.model_mode != "live" or not cfg.meta_api_key:
        print("Set MODEL_MODE=live and the key in .env first.")
        return 2
    client = get_model_client()
    before = spend.total()
    langs: dict[str, dict] = {}
    for code, name in LANGS.items():
        rows = []
        tot = {"plain": [0, 0, 0, 0], "hint": [0, 0, 0, 0]}          # word errors, words, char errors, chars
        for fname, wav, ref in clips(code, a.clips, a.bytes):
            pcm = to_pcm16(wav)
            row = {"id": fname, "ok": True, "reference": ref}
            rw = norm(ref)
            for key, bias in (("plain", None), ("hint", [name])):
                t0 = time.monotonic()
                try:
                    turns, _ = client.transcribe_audio(pcm, language_bias=bias)
                    hyp = " ".join(t.text for t in turns)
                except ModelError as e:
                    row.update(ok=False, error=str(e)[:100])
                    break
                hw = norm(hyp)
                we, ce = edit_distance(rw, hw), edit_distance(list("".join(rw)), list("".join(hw)))
                t = tot[key]
                t[0] += we; t[1] += len(rw); t[2] += ce; t[3] += len("".join(rw))
                row[key] = {"heard": hyp, "word_errors": we, "words": len(rw), "seconds": round(time.monotonic() - t0, 1)}
            rows.append(row)
        def rate(t, i):
            return round(t[i] / t[i + 1], 3) if t[i + 1] else None
        langs[code] = {"language": name, "clips": len(rows), "failed": sum(not r["ok"] for r in rows),
                       "without_language_hint": {"wer": rate(tot["plain"], 0), "cer": rate(tot["plain"], 2)},
                       "with_language_hint": {"wer": rate(tot["hint"], 0), "cer": rate(tot["hint"], 2)}, "cases": rows}
        print(f"{name}: {len(rows)} clips | no hint WER {rate(tot['plain'], 0)} CER {rate(tot['plain'], 2)} | with languageBias WER {rate(tot['hint'], 0)} CER {rate(tot['hint'], 2)}")
    report = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                                              "synthetic_data_only": True, "mode": "live", "sections": {}, "history": [], "not_measured": []}
    report["speech"] = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": cfg.meta_asr_model, "dataset": "Google FLEURS test split (CC BY 4.0)",
                        "what": "Real human voices reading sentences. This measures how well the model hears Hindi and Marathi. It is not a doctor-visit conversation, so it does not show how well a Hinglish consultation is understood.",
                        "cost_usd": round(spend.total() - before, 4), "languages": langs}
    report["not_measured"] = [x for x in report.get("not_measured", []) if "Voice Transcribe" not in x] + [
        "Muse Voice Transcribe on a real Hinglish doctor-visit conversation (the clips above are read sentences, not a consultation)"]
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"written to {OUT}, cost ${report['speech']['cost_usd']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
