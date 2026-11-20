"""Fluxo completo com um motor de voz falso (sem GPU nem modelos)."""
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from estudio_voz import paths, ui, video
from estudio_voz.tts import ENGINE


class _Progress:
    def __call__(self, *a, **k):
        pass


@pytest.fixture
def fake_engine(monkeypatch):
    def synth(segments, reference, s, progress=None):
        sr, parts, timings, pos = 24000, [], [], 0
        for seg in segments:
            if seg.text:
                n = int(0.05 * len(seg.text) * sr)
                parts.append((0.3 * np.sin(np.arange(n) * 2 * np.pi * 200 / sr)).astype(np.float32))
                timings.append((pos / sr, (pos + n) / sr, seg.text))
                pos += n
            if seg.pause_after:
                parts.append(np.zeros(int(seg.pause_after * sr), dtype=np.float32))
                pos += len(parts[-1])
        return np.concatenate(parts), sr, timings

    monkeypatch.setattr(ENGINE, "synthesize", synth)


def _controls(**over):
    d = dict(accent="multilingue", speed=1.0, pitch=0, timbre=0, exag=0.5, cfg=0.5, temp=0.8, seed=0, preset="natural",
             loud=-16, s_pause=0.25, p_pause=0.6)
    d.update(over)
    return list(d.values())


def test_ui_builds():
    ui.build()


def test_voice_library_and_settings():
    sel, _, _ = ui.create_voice("A minha voz")
    slug = sel.value
    assert slug == "a-minha-voz"
    ui.save_voice_settings(slug, *_controls(speed=1.2, accent="ptpt"))
    assert ui.load_voice_settings(slug)[:2] == ["ptpt", 1.2]
    ui.delete_voice(slug, True)
    assert all(v.slug != slug for v in ui.LIB.list())


def test_generate_and_video(fake_engine, tmp_path):
    audio, files, status, state = ui.generate("Olá a todos. Esta é uma locução de teste.\n\nFim.",
                                              "_padrao", *_controls(speed=1.1), {}, progress=_Progress())
    assert Path(audio).exists() and len(files) == 3 and "✔" in status
    assert Path(files[2]).read_text(encoding="utf-8").startswith("1\n")

    clip = tmp_path / "clip.mp4"
    subprocess.run([paths.ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=6",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(clip)], check=True)
    for subs in ("gravadas", "faixa", "nenhuma"):
        out, _, msg = ui.make_video(str(clip), "Última locução gerada", None, state, 0.5, 0.35, True, subs,
                                    progress=_Progress())
        assert video.has_audio(Path(out))
        assert video.duration(Path(out)) == pytest.approx(6.0, abs=0.2)
    data, sr = sf.read(audio)
    assert sr == 24000 and len(data) > 0
