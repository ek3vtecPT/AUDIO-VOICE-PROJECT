import numpy as np
import pytest

from estudio_voz import captions
from estudio_voz.effects import VoiceSettings, process

SR = 24000


def tone(seconds=2.0, f=180.0):
    t = np.arange(int(seconds * SR)) / SR
    return (0.3 * np.sin(2 * np.pi * f * t)).astype(np.float32)


def dominant(x):
    spec = np.abs(np.fft.rfft(x))
    return np.fft.rfftfreq(len(x), 1 / SR)[np.argmax(spec)]


def test_speed_changes_length_not_pitch():
    y = process(tone(), SR, VoiceSettings(speed=1.25, preset="nenhum"))
    assert len(y) == pytest.approx(2.0 * SR / 1.25, rel=0.03)
    assert dominant(y) == pytest.approx(180, abs=8)


def test_pitch_shift_up_one_octave():
    y = process(tone(), SR, VoiceSettings(pitch=12, preset="nenhum"))
    assert dominant(y) == pytest.approx(360, abs=15)


@pytest.mark.parametrize("preset", ["natural", "radio", "podcast", "anuncio", "sala", "telefone"])
def test_presets_and_peak_limit(preset):
    y = process(tone(), SR, VoiceSettings(preset=preset, timbre=2.0))
    assert y.dtype == np.float32 and np.isfinite(y).all()
    assert np.max(np.abs(y)) <= 10 ** (-1 / 20) + 1e-4


def test_settings_roundtrip_ignores_unknown():
    s = VoiceSettings.from_dict({"speed": 1.1, "desconhecido": 3})
    assert s.speed == 1.1 and VoiceSettings.from_dict(s.to_dict()) == s


def test_srt_timing_scaled_and_split():
    cues = captions.build_cues([(0.0, 4.0, "uma frase com bastantes palavras para ser dividida em duas partes")],
                               time_scale=0.5, offset=1.0, max_chars=30)
    assert len(cues) >= 2
    assert cues[0].start == pytest.approx(1.0) and cues[-1].end == pytest.approx(3.0)
    srt = captions.to_srt(cues)
    assert srt.startswith("1\n00:00:01,000 --> ")
