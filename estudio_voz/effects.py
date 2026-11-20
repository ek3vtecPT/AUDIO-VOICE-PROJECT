"""Afinação e acabamento do áudio: velocidade, tom, timbre, equalização e volume."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

import numpy as np

PRESETS = {
    "natural": "Natural",
    "radio": "Rádio (presença e compressão)",
    "podcast": "Podcast quente",
    "anuncio": "Anúncio (enérgico)",
    "sala": "Sala pequena (reverberação leve)",
    "telefone": "Telefone",
    "nenhum": "Sem efeitos",
}


@dataclass
class VoiceSettings:
    speed: float = 1.0            # 0.7 .. 1.5  (1.2 = 20% mais rápido)
    pitch: float = 0.0            # semitons: tom mais grave (-) ou agudo (+)
    timbre: float = 0.0           # semitons de formantes: voz mais "cheia" (-) ou "fina" (+)
    exaggeration: float = 0.5     # expressividade do modelo (0.25 calmo .. 1.5 muito expressivo)
    cfg_weight: float = 0.5       # aderência à voz de referência / ritmo
    temperature: float = 0.8      # variação entre gerações
    seed: int = 0                 # 0 = aleatório; outro valor repete o mesmo resultado
    preset: str = "natural"
    loudness: float = -16.0       # LUFS alvo (-14 redes sociais, -16 podcast)
    sentence_pause: float = 0.25
    paragraph_pause: float = 0.6

    @classmethod
    def from_dict(cls, d: dict | None) -> "VoiceSettings":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})

    def to_dict(self) -> dict:
        return asdict(self)


def _board(preset: str):
    import pedalboard as pb

    chains = {
        "natural": [pb.HighpassFilter(70), pb.Compressor(threshold_db=-20, ratio=2.5, attack_ms=10, release_ms=120)],
        "radio": [
            pb.HighpassFilter(90),
            pb.LowShelfFilter(cutoff_frequency_hz=160, gain_db=2.5),
            pb.PeakFilter(cutoff_frequency_hz=3500, gain_db=3.0, q=0.9),
            pb.Compressor(threshold_db=-22, ratio=4, attack_ms=5, release_ms=100),
        ],
        "podcast": [
            pb.HighpassFilter(60),
            pb.LowShelfFilter(cutoff_frequency_hz=220, gain_db=2.0),
            pb.HighShelfFilter(cutoff_frequency_hz=8000, gain_db=-1.5),
            pb.Compressor(threshold_db=-20, ratio=3, attack_ms=15, release_ms=150),
        ],
        "anuncio": [
            pb.HighpassFilter(80),
            pb.PeakFilter(cutoff_frequency_hz=2800, gain_db=2.5, q=1.0),
            pb.HighShelfFilter(cutoff_frequency_hz=9000, gain_db=2.0),
            pb.Compressor(threshold_db=-24, ratio=5, attack_ms=3, release_ms=80),
        ],
        "sala": [
            pb.HighpassFilter(70),
            pb.Compressor(threshold_db=-20, ratio=2.5),
            pb.Reverb(room_size=0.18, damping=0.6, wet_level=0.08, dry_level=0.95, width=0.6),
        ],
        "telefone": [pb.HighpassFilter(300), pb.LowpassFilter(3400), pb.Compressor(threshold_db=-18, ratio=4)],
        "nenhum": [],
    }
    return pb.Pedalboard(chains.get(preset, chains["natural"]))


def shift_timbre(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """Desloca os formantes (timbre) sem mudar o tom.

    Sobe tom+formantes juntos e depois repõe só o tom, preservando os formantes já deslocados.
    """
    if abs(semitones) < 1e-3:
        return audio
    from pedalboard import time_stretch

    y = time_stretch(audio, sr, 1.0, float(semitones), preserve_formants=False)
    return time_stretch(y, sr, 1.0, -float(semitones), preserve_formants=True)


def change_speed_pitch(audio: np.ndarray, sr: int, speed: float, pitch: float) -> np.ndarray:
    if abs(speed - 1.0) < 1e-3 and abs(pitch) < 1e-3:
        return audio
    from pedalboard import time_stretch

    return time_stretch(audio, sr, float(speed), float(pitch), preserve_formants=True)


def normalize_loudness(audio: np.ndarray, sr: int, target_lufs: float) -> np.ndarray:
    import pyloudnorm as pyln

    if len(audio) < int(0.5 * sr) or not np.any(audio):
        return audio
    meter = pyln.Meter(sr)
    loud = meter.integrated_loudness(audio.astype(np.float64))
    if not np.isfinite(loud):
        return audio
    return (audio * (10 ** ((target_lufs - loud) / 20))).astype(np.float32)


def limit(audio: np.ndarray, sr: int, ceiling_db: float = -1.0) -> np.ndarray:
    from pedalboard import Limiter, Pedalboard

    y = Pedalboard([Limiter(threshold_db=ceiling_db, release_ms=80)])(audio, sr)
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    ceiling = 10 ** (ceiling_db / 20)
    return (y * (ceiling / peak)).astype(np.float32) if peak > ceiling else y.astype(np.float32)


def process(audio: np.ndarray, sr: int, s: VoiceSettings) -> np.ndarray:
    """Cadeia completa. A duração final = duração original / s.speed."""
    y = np.asarray(audio, dtype=np.float32).reshape(-1)
    y = shift_timbre(y, sr, s.timbre)
    y = change_speed_pitch(y, sr, s.speed, s.pitch)
    y = _board(s.preset)(y, sr).reshape(-1)
    y = normalize_loudness(y, sr, s.loudness)
    return limit(y, sr)
