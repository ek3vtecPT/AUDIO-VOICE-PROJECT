"""Síntese de voz com Chatterbox Multilingue (licença MIT), em português."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import numpy as np

from . import paths  # noqa: F401  (define HF_HOME antes de importar o modelo)
from .effects import VoiceSettings
from .text import Segment

LANGUAGE = "pt"


def gpu_info() -> str:
    try:
        import torch
    except ImportError:
        return "PyTorch não instalado"
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        return f"GPU: {p.name} ({p.total_memory / 1024**3:.0f} GB)"
    return "Sem GPU NVIDIA: vai funcionar, mas muito devagar"


def free_gpu() -> None:
    try:
        import gc

        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _trim_silence(wav: np.ndarray, sr: int, threshold: float = 0.01, pad: float = 0.03) -> np.ndarray:
    loud = np.flatnonzero(np.abs(wav) > threshold)
    if loud.size == 0:
        return wav[:0]
    p = int(pad * sr)
    return wav[max(0, loud[0] - p): loud[-1] + p]


class TTSEngine:
    """Carrega o modelo só quando é preciso e serializa o acesso à GPU."""

    def __init__(self):
        self._model = None
        self._ref: str | None = None
        self._builtin_conds = None
        self.lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        if self._model is None:
            import torch
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = ChatterboxMultilingualTTS.from_pretrained(device=device)
            self._builtin_conds = self._model.conds
        return self._model

    def unload(self) -> None:
        self._model = None
        self._builtin_conds = None
        self._ref = None
        free_gpu()

    def voice_encoder(self):
        """Codificador de voz do Chatterbox (para comparar vozes ao preparar o material de treino)."""
        if self._model is not None:
            return self._model.ve
        import torch
        from chatterbox.models.voice_encoder import VoiceEncoder
        from huggingface_hub import hf_hub_download

        device = "cuda" if torch.cuda.is_available() else "cpu"
        ve = VoiceEncoder()
        ve.load_state_dict(torch.load(hf_hub_download("ResembleAI/chatterbox", "ve.pt"),
                                      map_location="cpu", weights_only=True))
        return ve.to(device).eval()

    def synthesize(
        self,
        segments: list[Segment],
        reference: Path | None,
        s: VoiceSettings,
        progress: Callable[[float, str], None] | None = None,
    ) -> tuple[np.ndarray, int, list[tuple[float, float, str]]]:
        """Gera o áudio bruto (sem efeitos). Devolve (áudio, taxa, [(início, fim, texto)])."""
        import torch

        with self.lock:
            model = self._load()
            sr = model.sr
            ref = str(reference) if reference else None
            if ref != self._ref:
                if ref:
                    model.prepare_conditionals(ref, exaggeration=s.exaggeration)
                else:
                    model.conds = self._builtin_conds
                self._ref = ref
            if s.seed:
                torch.manual_seed(int(s.seed))

            parts: list[np.ndarray] = []
            timings: list[tuple[float, float, str]] = []
            pos = 0
            todo = [seg for seg in segments if seg.text]
            done = 0
            for seg in segments:
                if seg.text:
                    if progress:
                        progress(done / max(1, len(todo)), f"A gerar frase {done + 1} de {len(todo)}")
                    wav = model.generate(
                        seg.text,
                        language_id=LANGUAGE,
                        exaggeration=s.exaggeration,
                        cfg_weight=s.cfg_weight,
                        temperature=s.temperature,
                    )
                    wav = _trim_silence(wav.squeeze(0).cpu().numpy().astype(np.float32), sr)
                    timings.append((pos / sr, (pos + len(wav)) / sr, seg.text))
                    parts.append(wav)
                    pos += len(wav)
                    done += 1
                if seg.pause_after > 0:
                    gap = np.zeros(int(seg.pause_after * sr), dtype=np.float32)
                    parts.append(gap)
                    pos += len(gap)
            audio = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
            return audio, sr, timings


ENGINE = TTSEngine()
