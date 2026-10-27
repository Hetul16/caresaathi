"""Checks a recording before it is stored or sent anywhere (Meta's documented limits for POST /v1/asr/transcribe).

Accepted: a RIFF/WAVE container, mono, 16-bit integer PCM at 16 or 24 kHz, at most 10 minutes. The browser recorder
produces exactly this. Anything else is refused with a plain message instead of being converted or guessed at."""
from __future__ import annotations

import io
import wave
from dataclasses import dataclass

MAX_MS = 10 * 60 * 1000
MAX_BYTES = 32 * 1024 * 1024


class AudioRejected(ValueError):
    """The message is safe to show to the family."""


@dataclass(frozen=True)
class WavInfo:
    duration_ms: int
    rate: int


def check_wav(data: bytes) -> WavInfo:
    if not data:
        raise AudioRejected("The recording is empty.")
    if len(data) > MAX_BYTES:
        raise AudioRejected("The recording is too large (limit 32 MB).")
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AudioRejected("The recording must be a WAV file.")
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            channels, width, rate, frames, comp = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype()
    except (wave.Error, EOFError):
        raise AudioRejected("The recording could not be read. Please record again.") from None
    if comp != "NONE" or width != 2:
        raise AudioRejected("The recording must be 16-bit PCM audio.")
    if channels != 1:
        raise AudioRejected("The recording must be mono (one channel).")
    if rate not in (16000, 24000):
        raise AudioRejected("The recording must be sampled at 16 kHz or 24 kHz.")
    duration = int(frames * 1000 / rate)
    if duration <= 0:
        raise AudioRejected("The recording is empty.")
    if duration > MAX_MS:
        raise AudioRejected("The recording is longer than 10 minutes. Please record the visit in shorter parts.")
    return WavInfo(duration, rate)
