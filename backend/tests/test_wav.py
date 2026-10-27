"""Audio must be RIFF/WAVE, mono, 16-bit PCM at 16 or 24 kHz, at most 10 minutes and 32 MB (Meta's documented limits for
the file endpoint). The browser records in exactly this format; anything else is refused with a plain message."""
import io
import wave

import pytest

from app.safety.audio import AudioRejected, check_wav


def make_wav(seconds=1.0, rate=16000, channels=1, width=2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"\x00" * int(seconds * rate) * channels * width)
    return buf.getvalue()


def test_a_valid_recording_passes_and_reports_its_length():
    assert check_wav(make_wav(2.5, 16000)).duration_ms == 2500
    assert check_wav(make_wav(1.0, 24000)).duration_ms == 1000


@pytest.mark.parametrize("data", [
    pytest.param(b"", id="empty"),
    pytest.param(b"not a wav file at all", id="not-riff"),
    pytest.param(make_wav(channels=2), id="stereo"),
    pytest.param(make_wav(rate=44100), id="sample-rate"),
    pytest.param(make_wav(width=1), id="8-bit"),
    pytest.param(make_wav(width=4), id="32-bit"),
])
def test_other_formats_are_refused(data):
    with pytest.raises(AudioRejected):
        check_wav(data)


def test_longer_than_ten_minutes_is_refused():
    with pytest.raises(AudioRejected):
        check_wav(make_wav(601, 16000))


def test_a_truncated_header_is_refused_not_crashed():
    with pytest.raises(AudioRejected):
        check_wav(make_wav(1.0)[:20])
