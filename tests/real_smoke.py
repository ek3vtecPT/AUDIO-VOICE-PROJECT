"""Teste com os modelos verdadeiros (corre no CI do Windows, em CPU; demora alguns minutos).

Não é recolhido pelo pytest: corre com  python tests/real_smoke.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from estudio_voz import dataset, paths  # noqa: E402
from estudio_voz import text as T  # noqa: E402
from estudio_voz.effects import VoiceSettings, process  # noqa: E402
from estudio_voz.tts import ENGINE, gpu_info  # noqa: E402


def main() -> None:
    print(gpu_info())
    import perth

    assert perth.PerthImplicitWatermarker is not None, "marca de água indisponível (falta pkg_resources?)"

    t0 = time.time()
    segs = T.prepare("Olá a todos! Isto é um teste do Estúdio de Voz. Hoje são 25 de novembro.", {})
    raw, sr, timings = ENGINE.synthesize(segs, None, VoiceSettings(seed=1))
    final = process(raw, sr, VoiceSettings(speed=1.1, pitch=1, timbre=0.5))
    dur = len(final) / sr
    print(f"Síntese: {dur:.1f} s de áudio em {time.time() - t0:.0f} s, {len(timings)} frases")
    assert dur > 2.0, "áudio demasiado curto"
    out = paths.OUTPUT_DIR / "teste_real.wav"
    sf.write(str(out), final, sr)

    # Material de treino: separação de voz, deteção de fala e codificador de voz
    t0 = time.time()
    wav = dataset.to_wav(out, paths.TMP_DIR / "teste_real_44k.wav")
    vocals = dataset.separate_vocals(wav)
    clips = dataset.speech_clips(vocals)
    print(f"Demucs + VAD: {len(vocals) / dataset.SR:.1f} s, {len(clips)} excertos em {time.time() - t0:.0f} s")
    assert len(vocals) > 0
    enc = ENGINE.voice_encoder()
    emb = dataset.embed(enc, [vocals], dataset.SR)
    print("Codificador de voz:", emb.shape)
    assert emb.shape[0] == 1

    # Clonagem a partir de uma amostra de referência (o caminho usado com a voz do utilizador)
    t0 = time.time()
    ref = wav
    raw2, sr2, _ = ENGINE.synthesize(T.prepare("Agora com a voz de referência.", {}), ref, VoiceSettings(seed=2))
    print(f"Clonagem: {len(raw2) / sr2:.1f} s em {time.time() - t0:.0f} s")
    assert len(raw2) / sr2 > 0.8

    # Modo Português de Portugal: voz base Piper pt-PT convertida para o timbre da referência
    t0 = time.time()
    raw3, sr3, t3 = ENGINE.synthesize(T.prepare("Bom dia! Isto é português de Portugal.", {}), ref,
                                       VoiceSettings(accent="ptpt"))
    print(f"Modo PT-PT: {len(raw3) / sr3:.1f} s em {time.time() - t0:.0f} s")
    assert len(raw3) / sr3 > 0.8 and len(t3) == 2
    print("OK")


if __name__ == "__main__":
    main()
