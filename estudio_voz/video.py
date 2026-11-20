"""Juntar a locução ao vídeo com ffmpeg: baixa o som original quando há voz e põe legendas."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import paths

SUB_STYLE = ("FontName=Arial,FontSize=13,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=40")


def _run(cmd: list[str], cwd: str | None = None) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou:\n{r.stderr.strip()[-800:]}")
    return r.stdout


def has_audio(path: Path) -> bool:
    out = _run([paths.ffprobe(), "-v", "error", "-select_streams", "a", "-show_entries",
                "stream=index", "-of", "csv=p=0", str(path)])
    return bool(out.strip())


def duration(path: Path) -> float:
    out = _run([paths.ffprobe(), "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip() or 0)


def to_mp3(wav: Path, mp3: Path, title: str = "") -> Path:
    _run([paths.ffmpeg(), "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "192k",
          "-metadata", f"title={title}", "-metadata", "comment=Voz gerada por IA (Estúdio de Voz)", str(mp3)])
    return mp3


def mix(
    video: Path,
    voice: Path,
    out: Path,
    *,
    offset: float = 0.0,
    original_volume: float = 0.35,
    ducking: bool = True,
    srt: Path | None = None,
    subtitles: str = "nenhuma",   # "nenhuma" | "faixa" (pode ser desligada) | "gravadas" (sempre visíveis)
) -> tuple[Path, str]:
    """Devolve (vídeo final, aviso ou "")."""
    warning = ""
    v_dur, a_dur = duration(video), duration(voice)
    if offset + a_dur > v_dur + 0.05:
        warning = (f"A locução ({a_dur:.1f} s + {offset:.1f} s de atraso) é mais longa do que o vídeo "
                   f"({v_dur:.1f} s) e foi cortada no fim.")

    delay = int(round(offset * 1000))
    voice_chain = f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={delay}:all=1,apad"
    if has_audio(video) and original_volume > 0:
        if ducking:
            graph = (f"{voice_chain},asplit=2[vo1][vo2];"
                     f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={original_volume:.3f}[bg];"
                     "[bg][vo1]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350[bgd];"
                     "[bgd][vo2]amix=inputs=2:duration=first:normalize=0[aout]")
        else:
            graph = (f"{voice_chain}[vo];"
                     f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={original_volume:.3f}[bg];"
                     "[bg][vo]amix=inputs=2:duration=first:normalize=0[aout]")
    else:
        graph = f"{voice_chain},atrim=0:{v_dur:.3f}[aout]"

    with tempfile.TemporaryDirectory() as tmp:
        cmd = [paths.ffmpeg(), "-y", "-v", "error", "-i", str(video.resolve()), "-i", str(voice.resolve())]
        burn = subtitles == "gravadas" and srt is not None
        soft = subtitles == "faixa" and srt is not None
        if soft:
            cmd += ["-i", str(srt.resolve())]
        if burn:
            # correr na pasta temporária evita problemas com caminhos do Windows no filtro "subtitles"
            shutil.copyfile(srt, Path(tmp) / "legendas.srt")
            graph += f";[0:v]subtitles=legendas.srt:force_style='{SUB_STYLE}'[vout]"
            cmd += ["-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
        else:
            cmd += ["-filter_complex", graph, "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy"]
        if soft:
            cmd += ["-map", "2:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=por"]
        cmd += ["-c:a", "aac", "-b:a", "192k", "-t", f"{v_dur:.3f}", "-movflags", "+faststart",
                "-metadata", "comment=Locução gerada por IA", str(out.resolve())]
        _run(cmd, cwd=tmp)
    return out, warning
