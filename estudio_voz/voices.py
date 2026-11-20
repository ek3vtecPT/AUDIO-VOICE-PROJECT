"""Biblioteca de vozes: amostra de referência, material de treino e afinação guardada."""
from __future__ import annotations

import json
import re
import shutil
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .effects import VoiceSettings

DEFAULT_VOICE = "_padrao"   # voz incluída no modelo, sem referência


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "voz"


@dataclass
class VoiceProfile:
    slug: str
    name: str
    created: float = field(default_factory=time.time)
    reference: str | None = None          # nome do ficheiro dentro da pasta da voz
    settings: dict = field(default_factory=dict)

    @property
    def builtin(self) -> bool:
        return self.slug == DEFAULT_VOICE


class VoiceLibrary:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    # --- pastas
    def dir(self, slug: str) -> Path:
        return self.root / slug

    def clips_dir(self, slug: str) -> Path:
        return self.dir(slug) / "dataset" / "clips"

    def sources_dir(self, slug: str) -> Path:
        return self.dir(slug) / "fontes"

    # --- CRUD
    def list(self) -> list[VoiceProfile]:
        voices = [VoiceProfile(DEFAULT_VOICE, "Voz padrão do modelo")]
        for meta in sorted(self.root.glob("*/voz.json")):
            try:
                voices.append(self._load(meta))
            except (OSError, ValueError, TypeError):
                continue
        return voices

    def _load(self, meta: Path) -> VoiceProfile:
        d = json.loads(meta.read_text(encoding="utf-8"))
        return VoiceProfile(d["slug"], d["name"], d.get("created", 0), d.get("reference"), d.get("settings", {}))

    def get(self, slug: str) -> VoiceProfile:
        if slug == DEFAULT_VOICE:
            return VoiceProfile(DEFAULT_VOICE, "Voz padrão do modelo")
        return self._load(self.dir(slug) / "voz.json")

    def save(self, v: VoiceProfile) -> None:
        if v.builtin:
            return
        self.dir(v.slug).mkdir(parents=True, exist_ok=True)
        data = {"slug": v.slug, "name": v.name, "created": v.created, "reference": v.reference, "settings": v.settings}
        (self.dir(v.slug) / "voz.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, name: str) -> VoiceProfile:
        name = name.strip()
        if not name:
            raise ValueError("Dá um nome à voz.")
        base = slugify(name)
        slug, n = base, 2
        while self.dir(slug).exists():
            slug, n = f"{base}-{n}", n + 1
        v = VoiceProfile(slug, name, settings=VoiceSettings().to_dict())
        self.save(v)
        return v

    def delete(self, slug: str) -> None:
        if slug != DEFAULT_VOICE and self.dir(slug).is_dir():
            shutil.rmtree(self.dir(slug))

    # --- referência e afinação
    def reference_path(self, v: VoiceProfile) -> Path | None:
        if v.reference and (p := self.dir(v.slug) / v.reference).exists():
            return p
        return None

    def set_reference(self, v: VoiceProfile, wav: Path) -> None:
        dest = self.dir(v.slug) / "referencia.wav"
        if wav.resolve() != dest.resolve():
            shutil.copyfile(wav, dest)
        v.reference = dest.name
        self.save(v)

    def settings(self, v: VoiceProfile) -> VoiceSettings:
        return VoiceSettings.from_dict(v.settings)

    def save_settings(self, v: VoiceProfile, s: VoiceSettings) -> None:
        v.settings = s.to_dict()
        self.save(v)

    # --- material de treino
    def dataset_stats(self, slug: str) -> tuple[int, float]:
        """(número de excertos, minutos de fala limpa)"""
        import soundfile as sf

        clips = list(self.clips_dir(slug).glob("*.wav"))
        secs = 0.0
        for c in clips:
            try:
                secs += sf.info(str(c)).duration
            except RuntimeError:
                continue
        return len(clips), secs / 60

    def export_dataset(self, slug: str, dest_zip: Path) -> Path:
        base = dest_zip.with_suffix("")
        return Path(shutil.make_archive(str(base), "zip", self.clips_dir(slug)))
