"""Legendas SRT a partir dos tempos de cada frase gerada (o texto é exato, não transcrito)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAX_CUE_CHARS = 42  # uma linha curta, legível no telemóvel


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _pieces(text: str, max_chars: int) -> list[str]:
    words, out, line = text.split(), [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > max_chars:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def build_cues(timings: list[tuple[float, float, str]], *, time_scale: float = 1.0,
               offset: float = 0.0, max_chars: int = MAX_CUE_CHARS) -> list[Cue]:
    """timings = [(início, fim, texto)] em segundos do áudio original.

    time_scale converte para o áudio final (1/velocidade); o tempo de cada frase é
    repartido pelos pedaços em proporção ao número de caracteres.
    """
    cues: list[Cue] = []
    for start, end, text in timings:
        parts = _pieces(text, max_chars)
        if not parts:
            continue
        start, end = start * time_scale + offset, end * time_scale + offset
        total = sum(len(p) for p in parts)
        t = start
        for p in parts:
            dur = (end - start) * len(p) / total
            cues.append(Cue(t, t + dur, p))
            t += dur
    return cues


def _fmt(t: float) -> str:
    ms = max(0, int(round(t * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    blocks = [f"{i}\n{_fmt(c.start)} --> {_fmt(c.end)}\n{c.text}\n" for i, c in enumerate(cues, 1)]
    return "\n".join(blocks)


def write_srt(cues: list[Cue], path: Path) -> Path:
    path.write_text(to_srt(cues), encoding="utf-8")
    return path
