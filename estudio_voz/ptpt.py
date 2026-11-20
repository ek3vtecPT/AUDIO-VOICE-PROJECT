"""Voz base com sotaque de Portugal (Piper, pt_PT).

No modo "Português de Portugal" a locução é dita primeiro por esta voz e depois
convertida para o timbre da voz escolhida (conversor do Chatterbox). A conversão
mantém a pronúncia e o ritmo do áudio de origem, por isso o sotaque fica português.
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from . import paths

VOICE_REPO = "rhasspy/piper-voices"
VOICE_NAME = "pt_PT-tugão-medium"
VOICE_FILE = f"pt/pt_PT/tugão/medium/{VOICE_NAME}.onnx"


def download_voice() -> Path:
    """Descarrega o modelo (~60 MB) para a pasta de modelos e devolve o caminho do .onnx."""
    from huggingface_hub import hf_hub_download

    model = hf_hub_download(VOICE_REPO, VOICE_FILE)
    hf_hub_download(VOICE_REPO, VOICE_FILE + ".json")
    return Path(model)


class PtPtVoice:
    def __init__(self):
        self._voice = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._voice is None:
                from piper import PiperVoice

                self._voice = PiperVoice.load(download_voice())
            return self._voice

    def speak(self, text: str) -> tuple[np.ndarray, int]:
        """Diz o texto com sotaque de Portugal. Devolve (áudio float32 mono, taxa)."""
        from piper import SynthesisConfig

        voice = self._load()
        chunks = list(voice.synthesize(text, SynthesisConfig(normalize_audio=True)))
        if not chunks:
            return np.zeros(0, dtype=np.float32), voice.config.sample_rate
        audio = np.concatenate([c.audio_float_array.reshape(-1) for c in chunks]).astype(np.float32)
        return audio, chunks[0].sample_rate


PTPT = PtPtVoice()
_ = paths  # garante HF_HOME na pasta de modelos antes de descarregar
