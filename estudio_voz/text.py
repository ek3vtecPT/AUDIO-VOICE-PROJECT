"""Preparação do texto: pronúncias, números, pausas e divisão em frases."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHARS = 250            # o modelo perde qualidade com blocos muito longos
DEFAULT_PAUSE_TAG = 0.8    # [pausa] sem duração

_PAUSE_TAG = re.compile(r"\[\s*pausa(?:\s+(\d+(?:[.,]\d+)?)\s*s?)?\s*\]", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


@dataclass
class Segment:
    text: str
    pause_after: float  # segundos de silêncio depois deste bloco


# ------------------------------------------------------------------ pronúncia

def load_pronunciations(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items() if str(k).strip()}


def save_pronunciations(path: Path, mapping: dict[str, str]) -> None:
    clean = {k.strip(): v.strip() for k, v in mapping.items() if k and k.strip() and v and v.strip()}
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_pronunciations(text: str, mapping: dict[str, str]) -> str:
    # termos mais longos primeiro, para "Banco XPTO" ganhar a "XPTO"
    for word in sorted(mapping, key=len, reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.IGNORECASE)
        text = pattern.sub(mapping[word], text)
    return text


# ------------------------------------------------------------------ números

def _num_to_words(n: str) -> str:
    try:
        from num2words import num2words
    except ImportError:
        return n
    try:
        if "," not in n:
            return num2words(int(n), lang="pt")
        inteiro, dec = n.split(",", 1)
        if dec.startswith("0"):   # 2,05 -> dois vírgula zero cinco
            dec_words = " ".join(num2words(int(d), lang="pt") for d in dec)
        else:
            dec_words = num2words(int(dec), lang="pt")
        return f"{num2words(int(inteiro), lang='pt')} vírgula {dec_words}"
    except (ValueError, NotImplementedError, OverflowError):
        return n


def expand_numbers(text: str) -> str:
    """Escreve números por extenso (pt-PT). Ex.: '25%' -> 'vinte e cinco por cento'."""
    text = re.sub(r"(\d)\.(?=\d{3}\b)", r"\1", text)  # 1.000 -> 1000
    text = re.sub(r"(\d+(?:,\d+)?)\s*%", lambda m: f"{_num_to_words(m.group(1))} por cento", text)
    text = re.sub(r"(\d+(?:,\d+)?)\s*€", lambda m: f"{_num_to_words(m.group(1))} euros", text)
    text = re.sub(r"€\s*(\d+(?:,\d+)?)", lambda m: f"{_num_to_words(m.group(1))} euros", text)
    text = re.sub(r"\b(\d{1,2})h(\d{2})\b", lambda m: f"{_num_to_words(m.group(1))} e {_num_to_words(m.group(2))}", text)
    text = re.sub(r"\b(\d{1,2})h\b", lambda m: f"{_num_to_words(m.group(1))} horas", text)
    text = re.sub(r"\d+(?:,\d+)?", lambda m: _num_to_words(m.group(0)), text)
    return text


# ------------------------------------------------------------------ divisão

def _clean(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"https?://\S+", "", text)        # links não se leem
    text = re.sub(r"(?<!\w)#(\w+)", r"\1", text)    # #hashtag -> hashtag
    text = re.sub(r"(?<!\w)@(\w+)", r"\1", text)    # @conta -> conta
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _break_long(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    out: list[str] = []
    rest = sentence
    while len(rest) > max_chars:
        window = rest[:max_chars]
        cut = max(window.rfind(", "), window.rfind("; "), window.rfind(": "))
        cut = cut + 1 if cut > max_chars // 3 else window.rfind(" ")
        if cut <= 0:
            cut = max_chars
        out.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        out.append(rest)
    return out


def split_text(
    text: str,
    *,
    sentence_pause: float = 0.25,
    paragraph_pause: float = 0.6,
    max_chars: int = MAX_CHARS,
) -> list[Segment]:
    """Divide em blocos para o modelo. Linhas em branco = parágrafo; [pausa 1.5] = pausa extra."""
    segments: list[Segment] = []
    text = _clean(text)
    paragraphs = re.split(r"\n\s*\n", text)
    for p_idx, para in enumerate(paragraphs):
        para = para.replace("\n", " ").strip()
        if not para:
            continue
        # separa as marcas de pausa do resto do texto
        pos = 0
        pieces: list[tuple[str, float | None]] = []
        for m in _PAUSE_TAG.finditer(para):
            pieces.append((para[pos:m.start()], None))
            dur = float(m.group(1).replace(",", ".")) if m.group(1) else DEFAULT_PAUSE_TAG
            pieces.append(("", dur))
            pos = m.end()
        pieces.append((para[pos:], None))

        for chunk, pause in pieces:
            if pause is not None:
                if segments:
                    segments[-1].pause_after += pause
                else:
                    segments.append(Segment("", pause))
                continue
            for sentence in _SENTENCE_END.split(chunk):
                sentence = sentence.strip()
                if not sentence or not re.search(r"\w", sentence):
                    continue
                for part in _break_long(sentence, max_chars):
                    segments.append(Segment(part, sentence_pause))
        if segments and p_idx < len(paragraphs) - 1:
            segments[-1].pause_after = max(segments[-1].pause_after, paragraph_pause)
    if segments:
        segments[-1].pause_after = 0.0 if segments[-1].text else segments[-1].pause_after
    return segments


def prepare(text: str, pronunciations: dict[str, str], **kwargs) -> list[Segment]:
    return split_text(expand_numbers(apply_pronunciations(text, pronunciations)), **kwargs)
