"""Pastas de dados e ferramentas externas (ffmpeg, deno).

Tem de ser importado antes de qualquer biblioteca do Hugging Face / PyTorch,
para que os modelos fiquem guardados na pasta de dados do programa.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"


def _default_data_dir() -> Path:
    if env := os.environ.get("ESTUDIO_VOZ_DADOS"):
        return Path(env)
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "EstudioVoz"
    return Path.home() / ".estudio-voz"


DATA_DIR = _default_data_dir()
VOICES_DIR = DATA_DIR / "vozes"
OUTPUT_DIR = DATA_DIR / "saidas"
MODELS_DIR = DATA_DIR / "modelos"
TMP_DIR = DATA_DIR / "tmp"
PRONUNCIATION_FILE = DATA_DIR / "pronuncia.json"

for _d in (VOICES_DIR, OUTPUT_DIR, MODELS_DIR, TMP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Modelos do Hugging Face (Chatterbox) e do torch.hub (Demucs, Silero) na pasta do programa
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
os.environ.setdefault("TORCH_HOME", str(MODELS_DIR / "torch"))

# Ferramentas instaladas pelo instalador ficam em tools/; põe-nas no PATH
for _sub in ("ffmpeg/bin", "deno"):
    _p = TOOLS_DIR / _sub
    if _p.is_dir() and str(_p) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(_p) + os.pathsep + os.environ.get("PATH", "")


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg não encontrado. Corre o instalador outra vez ou instala o ffmpeg.")
    return exe


def ffprobe() -> str:
    exe = shutil.which("ffprobe")
    if not exe:
        raise RuntimeError("ffprobe não encontrado. Corre o instalador outra vez ou instala o ffmpeg.")
    return exe
