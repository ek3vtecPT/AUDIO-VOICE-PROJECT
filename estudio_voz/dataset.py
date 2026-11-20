"""Material de treino: links de vídeo, ficheiros e gravações -> excertos limpos só com a tua voz.

Passos por fonte:
  1. obter o áudio (yt-dlp para links; ffmpeg converte qualquer formato)
  2. retirar música e ruído de fundo (Demucs, licença MIT)
  3. detetar a fala e cortar em excertos de 2 a 12 s (Silero VAD, licença MIT)
  4. manter só os excertos da voz principal (codificador de voz do Chatterbox)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from . import paths

SR = 44100            # taxa dos excertos guardados (serve para RVC e para a referência)
VAD_SR = 16000
MIN_CLIP, MAX_CLIP = 2.0, 12.0
DEMUCS_BLOCK_S = 300  # separa em blocos de 5 min para não esgotar a memória

Progress = Callable[[float, str], None]


@dataclass
class Source:
    kind: str            # "url" | "ficheiro"
    value: str
    start: float | None = None
    end: float | None = None

    @property
    def label(self) -> str:
        return self.value if self.kind == "url" else Path(self.value).name


# ------------------------------------------------------------------ links

_RANGE = re.compile(r"\s+(\d{1,2}(?::\d{2}){0,2})\s*-\s*(\d{1,2}(?::\d{2}){0,2})\s*$")


def _to_seconds(t: str) -> float:
    secs = 0.0
    for part in t.split(":"):
        secs = secs * 60 + float(part)
    return secs


def parse_links(text: str) -> list[Source]:
    """Uma linha por link. Opcional: intervalo no fim, ex. 'https://... 1:30-12:45'."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        start = end = None
        if m := _RANGE.search(line):
            start, end = _to_seconds(m.group(1)), _to_seconds(m.group(2))
            line = line[: m.start()].strip()
        if not re.match(r"https?://", line):
            raise ValueError(f"Isto não parece um link: {line}")
        out.append(Source("url", line, start, end))
    return out


def download(url: str, dest: Path, cookies_browser: str | None = None) -> Path:
    from yt_dlp import YoutubeDL

    dest.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(dest / "%(extractor)s_%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "ffmpeg_location": str(Path(paths.ffmpeg()).parent),
    }
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return Path(ydl.prepare_filename(info))
    except Exception as e:  # yt-dlp levanta vários tipos
        raise RuntimeError(
            f"Não consegui descarregar {url}: {e}\n"
            "Se o vídeo for privado, escolhe o browser onde tens sessão iniciada. "
            "Se a plataforma mudou, corre 'atualizar.bat' para atualizar o yt-dlp."
        ) from e


# ------------------------------------------------------------------ áudio

def to_wav(src: Path, dst: Path, *, sr: int = SR, channels: int = 2,
           start: float | None = None, end: float | None = None) -> Path:
    cmd = [paths.ffmpeg(), "-y", "-v", "error", "-i", str(src)]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    cmd += ["-vn", "-ac", str(channels), "-ar", str(sr), "-c:a", "pcm_s16le", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg não conseguiu ler {src.name}: {r.stderr.strip()[-400:]}")
    return dst


def separate_vocals(wav_path: Path, progress: Progress | None = None) -> np.ndarray:
    """Devolve só a voz (mono, 44.1 kHz), sem música nem ruído de fundo."""
    import soundfile as sf
    import torch
    from demucs.api import Separator

    sep = Separator(model="htdemucs", segment=7)
    info = sf.info(str(wav_path))
    block = DEMUCS_BLOCK_S * info.samplerate
    out = []
    try:
        for i, chunk in enumerate(sf.blocks(str(wav_path), blocksize=block, dtype="float32", always_2d=True)):
            if progress:
                progress(min(0.99, i * block / max(1, info.frames)), "A retirar música e ruído de fundo")
            wav = torch.from_numpy(chunk.T.copy())
            _, stems = sep.separate_tensor(wav, info.samplerate)
            vocals = stems["vocals"].mean(0)
            if sep.samplerate != SR:
                import torchaudio.functional as AF

                vocals = AF.resample(vocals, sep.samplerate, SR)
            out.append(vocals.cpu().numpy().astype(np.float32))
    finally:
        del sep
        from .tts import free_gpu

        free_gpu()
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


def speech_clips(audio: np.ndarray, sr: int = SR) -> list[tuple[int, int]]:
    """Intervalos (amostras) com fala, entre MIN_CLIP e MAX_CLIP segundos."""
    import torch
    import torchaudio.functional as AF
    from silero_vad import get_speech_timestamps, load_silero_vad

    model = load_silero_vad()
    a16 = AF.resample(torch.from_numpy(audio), sr, VAD_SR)
    ts = get_speech_timestamps(
        a16, model, sampling_rate=VAD_SR, threshold=0.5,
        min_speech_duration_ms=int(MIN_CLIP * 1000), max_speech_duration_s=MAX_CLIP,
        min_silence_duration_ms=300, speech_pad_ms=120,
    )
    k = sr / VAD_SR
    clips = []
    for t in ts:
        a, b = int(t["start"] * k), min(len(audio), int(t["end"] * k))
        if MIN_CLIP <= (b - a) / sr <= MAX_CLIP + 0.5:
            clips.append((a, b))
    return clips


def _quality_ok(clip: np.ndarray) -> bool:
    peak = float(np.max(np.abs(clip))) if clip.size else 0.0
    rms = float(np.sqrt(np.mean(clip ** 2))) if clip.size else 0.0
    clipped = float(np.mean(np.abs(clip) > 0.99)) if clip.size else 1.0
    return peak > 0.05 and rms > 0.005 and clipped < 0.001


def _embeddings(clips: list[np.ndarray], encoder) -> np.ndarray:
    return encoder.embeds_from_wavs(clips, sample_rate=SR, batch_size=16)


def main_speaker_filter(embeds: np.ndarray, threshold: float,
                        anchor: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Devolve (máscara dos excertos a manter, semelhança de cada um).

    Sem âncora, assume que a voz principal é a que aparece mais: começa na média de
    todos e refina 3 vezes só com os excertos parecidos.
    """
    def norm(v):
        return v / (np.linalg.norm(v) + 1e-9)

    center = norm(anchor) if anchor is not None else norm(embeds.mean(0))
    sims = embeds @ center
    for _ in range(3 if anchor is None else 0):
        keep = sims >= threshold
        if keep.sum() < 3:
            break
        center = norm(embeds[keep].mean(0))
        sims = embeds @ center
    return sims >= threshold, sims


# ------------------------------------------------------------------ pipeline

def import_sources(
    sources: list[Source],
    clips_dir: Path,
    work_dir: Path,
    *,
    encoder_factory: Callable[[], object],
    remove_music: bool = True,
    filter_speaker: bool = True,
    threshold: float = 0.75,
    anchor_wav: Path | None = None,
    cookies_browser: str | None = None,
    progress: Progress | None = None,
) -> str:
    import soundfile as sf

    clips_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    meta_file = clips_dir.parent / "excertos.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else []
    report = []
    encoder = None

    def step(i: int, frac: float, msg: str):
        if progress:
            progress((i + frac) / len(sources), f"[{i + 1}/{len(sources)}] {msg}")

    for i, src in enumerate(sources):
        try:
            step(i, 0.0, f"A obter {src.label}")
            raw = Path(src.value) if src.kind == "ficheiro" else download(src.value, work_dir, cookies_browser)
            wav = to_wav(raw, work_dir / f"fonte_{int(time.time())}_{i}.wav", start=src.start, end=src.end)

            if remove_music:
                audio = separate_vocals(wav, lambda f, m: step(i, 0.1 + 0.5 * f, m))
            else:
                data, _ = sf.read(str(wav), dtype="float32", always_2d=True)
                audio = data.mean(1)
            total_min = len(audio) / SR / 60

            step(i, 0.65, "A detetar a fala")
            spans = [(a, b) for a, b in speech_clips(audio) if _quality_ok(audio[a:b])]
            clips = [audio[a:b] for a, b in spans]
            if not clips:
                report.append(f"• {src.label}: não encontrei fala utilizável.")
                continue

            sims = np.ones(len(clips))
            keep = np.ones(len(clips), dtype=bool)
            if filter_speaker and len(clips) >= 3:
                step(i, 0.8, "A separar a tua voz das outras")
                encoder = encoder or encoder_factory()
                anchor = None
                if anchor_wav is not None and anchor_wav.exists():
                    a, a_sr = sf.read(str(anchor_wav), dtype="float32", always_2d=True)
                    anchor = encoder.embeds_from_wavs([a.mean(1)], sample_rate=a_sr, as_spk=True)
                keep, sims = main_speaker_filter(_embeddings(clips, encoder), threshold, anchor)

            stem = re.sub(r"[^\w-]+", "_", Path(src.label).stem)[:40]
            stamp = int(time.time())
            kept_secs = 0.0
            for n, (clip, ok, sim, (a, b)) in enumerate(zip(clips, keep, sims, spans)):
                if not ok:
                    continue
                name = f"{stem}_{stamp}_{n:04d}.wav"
                peak = float(np.max(np.abs(clip)))
                sf.write(str(clips_dir / name), (clip * (0.9 / peak)).astype(np.float32), SR, subtype="PCM_16")
                meta.append({"ficheiro": name, "fonte": src.value, "inicio": a / SR, "fim": b / SR,
                             "semelhanca": round(float(sim), 3)})
                kept_secs += len(clip) / SR
            dropped = int((~keep).sum())
            report.append(
                f"• {src.label}: {total_min:.1f} min de áudio → {kept_secs / 60:.1f} min de fala tua "
                f"({int(keep.sum())} excertos" + (f", {dropped} descartados por serem outra voz" if dropped else "") + ")."
            )
        except Exception as e:  # noqa: BLE001  (uma fonte com erro não pára as outras)
            report.append(f"• {src.label}: ERRO — {e}")
        finally:
            for f in work_dir.glob("fonte_*.wav"):
                f.unlink(missing_ok=True)
            if src.kind == "url":
                shutil.rmtree(work_dir, ignore_errors=True)
                work_dir.mkdir(parents=True, exist_ok=True)

    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if progress:
        progress(1.0, "Concluído")
    return "\n".join(report)


def build_reference(clips_dir: Path, dest: Path, target_s: float = 10.0) -> Path | None:
    """Cria a amostra de referência (até 10 s) juntando os excertos mais típicos da voz."""
    import soundfile as sf

    meta_file = clips_dir.parent / "excertos.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else []
    ranked = sorted(meta, key=lambda m: -m.get("semelhanca", 0))
    files = [clips_dir / m["ficheiro"] for m in ranked if (clips_dir / m["ficheiro"]).exists()]
    files = files or sorted(clips_dir.glob("*.wav"))
    parts, total = [], 0.0
    for f in files:
        a, sr = sf.read(str(f), dtype="float32")
        if sr != SR or not 3.0 <= len(a) / sr <= MAX_CLIP + 0.5:
            continue
        parts += [a, np.zeros(int(0.25 * SR), dtype=np.float32)]
        total += len(a) / sr + 0.25
        if total >= target_s:
            break
    if not parts:
        return None
    audio = np.concatenate(parts)[: int(target_s * SR)]
    sf.write(str(dest), audio, SR, subtype="PCM_16")
    return dest
