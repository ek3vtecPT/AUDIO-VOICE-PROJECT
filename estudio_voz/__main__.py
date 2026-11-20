"""Arranque: python -m estudio_voz [--rede] [--porta 7860] [--utilizador X --senha Y]"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser

from . import paths  # noqa: F401  (tem de vir primeiro)


def _open_window(url: str) -> None:
    """No Windows abre o Edge em modo aplicação (janela própria, sem barra de endereços)."""
    if sys.platform == "win32":
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "msedge", f"--app={url}"], shell=False)
            return
        except OSError:
            pass
    webbrowser.open(url)


def download_models() -> None:
    print("A descarregar os modelos (só na primeira vez; alguns GB)…")
    from .tts import ENGINE

    ENGINE._load()
    from demucs.api import Separator

    Separator(model="htdemucs")
    from silero_vad import load_silero_vad

    load_silero_vad()
    from .ptpt import download_voice

    download_voice()
    print("Modelos prontos.")


def main() -> None:
    ap = argparse.ArgumentParser(prog="estudio_voz", description="Estúdio de Voz")
    ap.add_argument("--rede", action="store_true", help="aceitar ligações de outros PCs da rede local")
    ap.add_argument("--porta", type=int, default=int(os.environ.get("ESTUDIO_VOZ_PORTA", 7860)))
    ap.add_argument("--utilizador", default=os.environ.get("ESTUDIO_VOZ_UTILIZADOR"))
    ap.add_argument("--senha", default=os.environ.get("ESTUDIO_VOZ_SENHA"))
    ap.add_argument("--sem-janela", action="store_true", help="não abrir o browser")
    ap.add_argument("--descarregar-modelos", action="store_true", help="só descarregar os modelos e sair")
    args = ap.parse_args()

    if args.descarregar_modelos:
        download_models()
        return

    import gradio as gr

    from .ui import build

    auth = (args.utilizador, args.senha) if args.utilizador and args.senha else None
    if args.rede and not auth:
        print("AVISO: modo rede sem senha — qualquer pessoa na rede local pode usar o programa.\n"
              "       Usa --utilizador e --senha para proteger o acesso.")
    demo = build()
    demo.queue(default_concurrency_limit=1)
    demo.launch(
        server_name="0.0.0.0" if args.rede else "127.0.0.1",
        server_port=args.porta,
        auth=auth,
        allowed_paths=[str(paths.DATA_DIR)],
        theme=gr.themes.Soft(),
        prevent_thread_lock=True,
    )
    if not args.sem_janela:
        _open_window(f"http://127.0.0.1:{args.porta}")
    print(f"Estúdio de Voz a correr em http://127.0.0.1:{args.porta}  (fecha esta janela para sair)")
    demo.block_thread()


if __name__ == "__main__":
    main()
