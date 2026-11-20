"""Interface Gradio do Estúdio de Voz."""
from __future__ import annotations

import time
from pathlib import Path

import gradio as gr

from . import captions, dataset, paths, video
from . import text as T
from .effects import PRESETS, VoiceSettings, process
from .tts import ENGINE, gpu_info
from .voices import DEFAULT_VOICE, VoiceLibrary

LIB = VoiceLibrary(paths.VOICES_DIR)

READ_PROMPTS = """Lê estas frases com calma, no teu tom normal. Varia a entoação: umas neutras, umas entusiasmadas, umas em pergunta.

1. Bom dia! Hoje trago-vos uma novidade que vai mudar a forma como trabalham.
2. Sabiam que a maioria das pessoas decide em menos de três segundos se continua a ver um vídeo?
3. O segredo não está na quantidade, está na consistência.
4. Vamos por partes: primeiro o problema, depois a solução e, no fim, os resultados.
5. Isto é mesmo incrível. A sério, nunca pensei que fosse tão simples!
6. Se gostaram, já sabem: partilhem com quem precisa de ouvir isto.
7. A equipa trabalhou durante meses neste projeto e o resultado está à vista.
8. Qual é a vossa opinião? Deixem nos comentários.
9. Os números falam por si: mais vendas, mais clientes e mais tempo livre.
10. Hoje está um daqueles dias em que apetece fazer tudo de uma vez.
11. Atenção a este pormenor, porque é aqui que quase toda a gente se engana.
12. Obrigado por estarem desse lado. Até ao próximo vídeo!

Dica: grava várias sessões curtas (3 a 5 minutos cada), sempre com o mesmo microfone e à mesma distância."""

ABOUT = """### Sobre
- **Modelos:** Chatterbox Multilingue (síntese e conversão de voz, MIT), Piper pt_PT-tugão (voz base de Portugal, GPL-3.0), Demucs (separação de voz, MIT), Silero VAD (deteção de fala, MIT).
- **Pasta de dados:** `{data}` — vozes, material de treino, modelos e locuções ficam só neste computador.
- **Marca de água:** o Chatterbox inclui uma marca de água inaudível em todo o áudio gerado.
- **Obrigação legal (AI Act, art. 50):** indica nas publicações que a locução foi gerada por IA.
- **Treino profundo da voz (RVC):** chega na fase 2. Até lá, a clonagem usa a amostra de referência,
  e o material que preparares agora já fica pronto para esse treino.
"""


# ------------------------------------------------------------------ utilitários

def _voice_choices(include_default: bool = True):
    return [(v.name, v.slug) for v in LIB.list() if include_default or not v.builtin]


def _settings_from(*vals) -> VoiceSettings:
    accent, speed, pitch, timbre, exag, cfg, temp, seed, preset, loud, s_pause, p_pause = vals
    return VoiceSettings(float(speed), float(pitch), float(timbre), float(exag), float(cfg), float(temp),
                         int(seed or 0), preset, float(loud), float(s_pause), float(p_pause), accent)


def _settings_values(s: VoiceSettings):
    return [s.accent, s.speed, s.pitch, s.timbre, s.exaggeration, s.cfg_weight, s.temperature, s.seed,
            s.preset, s.loudness, s.sentence_pause, s.paragraph_pause]


def _voice_summary(slug: str | None) -> str:
    if not slug or slug == DEFAULT_VOICE:
        return "Escolhe ou cria uma voz."
    v = LIB.get(slug)
    n, mins = LIB.dataset_stats(slug)
    ref = LIB.reference_path(v)
    lines = [f"**{v.name}**",
             f"- Material de treino: **{mins:.1f} min** em {n} excertos"
             + (" — ótimo para treino." if mins >= 20 else " — para treino profundo convém chegar aos 20–30 min."),
             f"- Amostra de referência: {'definida ✔' if ref else '**em falta** — processa material ou carrega uma amostra.'}"]
    return "\n".join(lines)


# ------------------------------------------------------------------ locução

def generate(text, slug, *rest, progress=gr.Progress()):
    *vals, state = rest
    if not text or not text.strip():
        raise gr.Error("Escreve ou cola o texto da publicação.")
    import soundfile as sf

    v = LIB.get(slug or DEFAULT_VOICE)
    ref = LIB.reference_path(v)
    if not v.builtin and ref is None:
        raise gr.Error("Esta voz ainda não tem amostra de referência. Vai ao separador Vozes.")
    s = _settings_from(*vals)
    segs = T.prepare(text, T.load_pronunciations(paths.PRONUNCIATION_FILE),
                     sentence_pause=s.sentence_pause, paragraph_pause=s.paragraph_pause)
    if not any(seg.text for seg in segs):
        raise gr.Error("Não encontrei texto para ler.")

    progress(0.02, desc="A carregar o modelo de voz (a primeira vez demora)…" if not ENGINE.loaded else "A gerar")
    t0 = time.time()
    raw, sr, timings = ENGINE.synthesize(segs, ref, s, progress=lambda f, m: progress(0.05 + 0.85 * f, desc=m))
    progress(0.92, desc="A afinar e masterizar")
    final = process(raw, sr, s)

    base = paths.OUTPUT_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}_{v.slug}"
    wav = base.with_suffix(".wav")
    sf.write(str(wav), final, sr, subtype="PCM_16")
    mp3 = video.to_mp3(wav, base.with_suffix(".mp3"), title=text.strip()[:60])
    scale = 1.0 / s.speed
    srt = captions.write_srt(captions.build_cues(timings, time_scale=scale), base.with_suffix(".srt"))

    dur = len(final) / sr
    status = f"✔ {dur:.1f} s de áudio em {time.time() - t0:.0f} s · {len(timings)} frases · ficheiros em `{paths.OUTPUT_DIR}`"
    state = {"wav": str(wav), "timings": timings, "scale": scale}
    return str(wav), [str(wav), str(mp3), str(srt)], status, state


def save_voice_settings(slug, *vals):
    if not slug or slug == DEFAULT_VOICE:
        raise gr.Error("A voz padrão não guarda afinação. Escolhe uma voz tua.")
    v = LIB.get(slug)
    LIB.save_settings(v, _settings_from(*vals))
    gr.Info(f"Afinação guardada em \"{v.name}\".")


def load_voice_settings(slug):
    v = LIB.get(slug or DEFAULT_VOICE)
    return _settings_values(LIB.settings(v) if not v.builtin else VoiceSettings())


# ------------------------------------------------------------------ vídeo

def make_video(video_file, source, uploaded_audio, state, offset, orig_vol, ducking, subs, progress=gr.Progress()):
    if not video_file:
        raise gr.Error("Carrega o vídeo.")
    if source == "Última locução gerada":
        if not state or not state.get("wav"):
            raise gr.Error("Ainda não geraste nenhuma locução nesta sessão.")
        voice = Path(state["wav"])
    else:
        if not uploaded_audio:
            raise gr.Error("Carrega o ficheiro de áudio.")
        voice = Path(uploaded_audio)

    srt = None
    if subs != "nenhuma":
        if source != "Última locução gerada":
            raise gr.Error("As legendas automáticas só existem para locuções geradas aqui.")
        cues = captions.build_cues(state["timings"], time_scale=state["scale"], offset=float(offset))
        srt = captions.write_srt(cues, paths.TMP_DIR / "legendas.srt")

    progress(0.1, desc="A juntar a voz ao vídeo")
    out = paths.OUTPUT_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}_video.mp4"
    out, warning = video.mix(Path(video_file), voice, out, offset=float(offset), original_volume=float(orig_vol),
                             ducking=bool(ducking), srt=srt, subtitles=subs)
    msg = f"✔ Vídeo pronto: `{out}`" + (f"\n\n⚠ {warning}" if warning else "")
    return str(out), str(out), msg


# ------------------------------------------------------------------ vozes

def create_voice(name):
    try:
        v = LIB.create(name)
    except ValueError as e:
        raise gr.Error(str(e)) from e
    return (gr.Dropdown(choices=_voice_choices(False), value=v.slug),
            gr.Dropdown(choices=_voice_choices(True), value=v.slug), "")


def show_voice(slug):
    if not slug:
        return "Escolhe ou cria uma voz.", None
    ref = LIB.reference_path(LIB.get(slug))
    return _voice_summary(slug), (str(ref) if ref else None)


def process_material(slug, links, files, mic, remove_music, filter_speaker, threshold, cookies,
                     progress=gr.Progress()):
    if not slug:
        raise gr.Error("Escolhe ou cria primeiro uma voz.")
    try:
        sources = dataset.parse_links(links)
    except ValueError as e:
        raise gr.Error(str(e)) from e
    for f in files or []:
        sources.append(dataset.Source("ficheiro", str(f)))
    if mic:
        sources.append(dataset.Source("ficheiro", str(mic)))
    if not sources:
        raise gr.Error("Cola um link, carrega um ficheiro ou grava a tua voz.")

    v = LIB.get(slug)
    with ENGINE.lock:
        if remove_music:
            ENGINE.unload()   # liberta a GPU para o Demucs (8 GB não chegam para os dois)
        report = dataset.import_sources(
            sources, LIB.clips_dir(slug), paths.TMP_DIR / "download",
            encoder_factory=ENGINE.voice_encoder, remove_music=bool(remove_music),
            filter_speaker=bool(filter_speaker), threshold=float(threshold),
            anchor_wav=LIB.reference_path(v), cookies_browser=None if cookies == "nenhum" else cookies,
            progress=lambda f, m: progress(f, desc=m),
        )
    if LIB.reference_path(v) is None:
        ref = dataset.build_reference(LIB.clips_dir(slug), LIB.dir(slug) / "referencia.wav")
        if ref:
            LIB.set_reference(v, ref)
            report += "\n\nCriei automaticamente a amostra de referência a partir dos melhores excertos."
    summary, ref_audio = show_voice(slug)
    return report, summary, ref_audio, "", None, None


def auto_reference(slug):
    if not slug:
        raise gr.Error("Escolhe uma voz.")
    v = LIB.get(slug)
    ref = dataset.build_reference(LIB.clips_dir(slug), paths.TMP_DIR / "ref_nova.wav")
    if not ref:
        raise gr.Error("Ainda não há material processado para esta voz.")
    LIB.set_reference(v, ref)
    return show_voice(slug)


def upload_reference(slug, audio):
    if not slug:
        raise gr.Error("Escolhe uma voz.")
    if not audio:
        raise gr.Error("Carrega ou grava a amostra (5 a 15 s, só a tua voz, sem música).")
    v = LIB.get(slug)
    wav = dataset.to_wav(Path(audio), paths.TMP_DIR / "ref_upload.wav", channels=1, end=15.0)
    LIB.set_reference(v, wav)
    return show_voice(slug)


def export_material(slug):
    if not slug:
        raise gr.Error("Escolhe uma voz.")
    n, _ = LIB.dataset_stats(slug)
    if not n:
        raise gr.Error("Esta voz ainda não tem material processado.")
    return str(LIB.export_dataset(slug, paths.OUTPUT_DIR / f"material_{slug}.zip"))


def delete_voice(slug, confirm):
    if not slug:
        raise gr.Error("Escolhe uma voz.")
    if not confirm:
        raise gr.Error("Marca a confirmação primeiro.")
    LIB.delete(slug)
    return (gr.Dropdown(choices=_voice_choices(False), value=None),
            gr.Dropdown(choices=_voice_choices(True), value=DEFAULT_VOICE), False, "Escolhe ou cria uma voz.", None)


# ------------------------------------------------------------------ pronúncia

def _rows():
    return [[k, v] for k, v in T.load_pronunciations(paths.PRONUNCIATION_FILE).items()] or [["", ""]]


def save_pron(table):
    rows = table.values.tolist() if hasattr(table, "values") else (table or [])
    T.save_pronunciations(paths.PRONUNCIATION_FILE, {str(r[0]): str(r[1]) for r in rows if len(r) >= 2 and r[0]})
    gr.Info("Pronúncias guardadas.")
    return _rows()


def preview_text(text):
    segs = T.prepare(text or "", T.load_pronunciations(paths.PRONUNCIATION_FILE))
    return "\n".join(f"{i}. {s.text}" + (f"   ⏸ {s.pause_after:.2f}s" if s.pause_after else "")
                     for i, s in enumerate(segs, 1) if s.text) or "(vazio)"


# ------------------------------------------------------------------ layout

def build() -> gr.Blocks:
    with gr.Blocks(title="Estúdio de Voz") as demo:
        gr.Markdown(f"# 🎙️ Estúdio de Voz\n{gpu_info()}")
        last = gr.State({})

        with gr.Tab("Locução"):
            with gr.Row():
                with gr.Column(scale=3):
                    text = gr.Textbox(label="Texto da publicação", lines=10,
                                      placeholder="Cola aqui o texto. Linha em branco = pausa de parágrafo. "
                                                  "Usa [pausa 1.5] para uma pausa à medida.")
                    voice = gr.Dropdown(_voice_choices(True), value=DEFAULT_VOICE, label="Voz")
                    with gr.Row():
                        gen_btn = gr.Button("Gerar locução", variant="primary")
                        save_btn = gr.Button("Guardar afinação nesta voz")
                with gr.Column(scale=2):
                    accent = gr.Radio(
                        [("Português de Portugal (voz base pt-PT convertida para a voz escolhida)", "ptpt"),
                         ("Multilingue (mais expressivo, mas pode soar brasileiro)", "multilingue")],
                        value="ptpt", label="Sotaque")
                    with gr.Accordion("Afinação", open=True):
                        speed = gr.Slider(0.7, 1.5, 1.0, step=0.05, label="Velocidade")
                        pitch = gr.Slider(-6, 6, 0, step=0.5, label="Tom (semitons): grave ↔ agudo")
                        timbre = gr.Slider(-4, 4, 0, step=0.25, label="Timbre: mais cheio ↔ mais fino")
                        exag = gr.Slider(0.25, 1.5, 0.5, step=0.05, label="Expressividade (só multilingue)")
                        preset = gr.Dropdown([(v, k) for k, v in PRESETS.items()], value="natural", label="Acabamento")
                    with gr.Accordion("Avançado", open=False):
                        cfg = gr.Slider(0.0, 1.0, 0.5, step=0.05, label="Fidelidade à referência / ritmo (só multilingue)")
                        temp = gr.Slider(0.3, 1.2, 0.8, step=0.05, label="Variação (só multilingue)")
                        seed = gr.Number(0, precision=0, label="Semente (0 = aleatória; repete o resultado)")
                        loud = gr.Slider(-23, -12, -16, step=1, label="Volume final (LUFS): −14 redes sociais")
                        s_pause = gr.Slider(0.0, 1.0, 0.25, step=0.05, label="Pausa entre frases (s)")
                        p_pause = gr.Slider(0.0, 2.0, 0.6, step=0.1, label="Pausa entre parágrafos (s)")
            out_audio = gr.Audio(label="Resultado", type="filepath", interactive=False)
            out_files = gr.File(label="Descarregar (WAV, MP3, legendas SRT)", file_count="multiple")
            status = gr.Markdown()

            controls = [accent, speed, pitch, timbre, exag, cfg, temp, seed, preset, loud, s_pause, p_pause]
            gen_btn.click(generate, [text, voice, *controls, last], [out_audio, out_files, status, last])
            save_btn.click(save_voice_settings, [voice, *controls], None)
            voice.change(load_voice_settings, voice, controls)

        with gr.Tab("Vídeo"):
            with gr.Row():
                with gr.Column():
                    v_in = gr.Video(label="Vídeo")
                    v_src = gr.Radio(["Última locução gerada", "Outro ficheiro de áudio"],
                                     value="Última locução gerada", label="Locução")
                    v_audio = gr.Audio(label="Ficheiro de áudio", type="filepath", sources=["upload"])
                    v_offset = gr.Slider(0, 30, 0, step=0.1, label="Começar a voz aos (s)")
                    v_vol = gr.Slider(0, 1, 0.35, step=0.05, label="Volume do som original do vídeo")
                    v_duck = gr.Checkbox(True, label="Baixar o som original enquanto a voz fala")
                    v_subs = gr.Radio([("Sem legendas", "nenhuma"), ("Legendas gravadas na imagem", "gravadas"),
                                       ("Faixa de legendas (pode ser desligada)", "faixa")],
                                      value="gravadas", label="Legendas")
                    v_btn = gr.Button("Criar vídeo", variant="primary")
                with gr.Column():
                    v_out = gr.Video(label="Resultado")
                    v_file = gr.File(label="Descarregar")
                    v_msg = gr.Markdown()
            v_btn.click(make_video, [v_in, v_src, v_audio, last, v_offset, v_vol, v_duck, v_subs],
                        [v_out, v_file, v_msg])

        with gr.Tab("Vozes"):
            with gr.Row():
                with gr.Column(scale=2):
                    with gr.Row():
                        new_name = gr.Textbox(label="Nova voz", placeholder="ex.: A minha voz — institucional")
                        new_btn = gr.Button("Criar")
                    sel = gr.Dropdown(_voice_choices(False), label="Voz a editar")
                    summary = gr.Markdown("Escolhe ou cria uma voz.")
                    ref_audio = gr.Audio(label="Amostra de referência atual", type="filepath", interactive=False)
                with gr.Column(scale=3):
                    gr.Markdown("### Adicionar material da tua voz")
                    links = gr.Textbox(label="Links de vídeos (um por linha; opcional: intervalo no fim, ex. 1:30-12:45)",
                                       lines=4, placeholder="https://www.youtube.com/watch?v=...\nhttps://vimeo.com/... 0:45-10:00")
                    files = gr.File(label="Ficheiros de áudio ou vídeo", file_count="multiple", type="filepath")
                    with gr.Accordion("Gravar agora (textos para ler)", open=False):
                        gr.Markdown(READ_PROMPTS)
                        mic = gr.Audio(label="Gravação", sources=["microphone"], type="filepath")
                    with gr.Row():
                        rm_music = gr.Checkbox(True, label="Retirar música e ruído de fundo")
                        spk = gr.Checkbox(True, label="Manter só a minha voz (descarta convidados)")
                    with gr.Row():
                        thr = gr.Slider(0.6, 0.9, 0.75, step=0.01, label="Rigor na comparação de voz")
                        cookies = gr.Dropdown(["nenhum", "firefox", "edge", "chrome"], value="nenhum",
                                              label="Vídeos privados: usar sessão do browser")
                    proc_btn = gr.Button("Processar material", variant="primary")
                    report = gr.Markdown()
            with gr.Accordion("Amostra de referência, exportação e eliminar", open=False):
                with gr.Row():
                    auto_btn = gr.Button("Escolher automaticamente dos melhores excertos")
                    up_ref = gr.Audio(label="Ou usa uma amostra tua (5–15 s)", type="filepath",
                                      sources=["upload", "microphone"])
                    up_btn = gr.Button("Usar esta amostra")
                with gr.Row():
                    exp_btn = gr.Button("Exportar material (ZIP)")
                    exp_file = gr.File(label="Material")
                with gr.Row():
                    confirm = gr.Checkbox(False, label="Confirmo que quero apagar esta voz e todo o material")
                    del_btn = gr.Button("Apagar voz", variant="stop")

            new_btn.click(create_voice, new_name, [sel, voice, new_name])
            sel.change(show_voice, sel, [summary, ref_audio])
            proc_btn.click(process_material, [sel, links, files, mic, rm_music, spk, thr, cookies],
                           [report, summary, ref_audio, links, files, mic])
            auto_btn.click(auto_reference, sel, [summary, ref_audio])
            up_btn.click(upload_reference, [sel, up_ref], [summary, ref_audio])
            exp_btn.click(export_material, sel, exp_file)
            del_btn.click(delete_voice, [sel, confirm], [sel, voice, confirm, summary, ref_audio])

        with gr.Tab("Pronúncia"):
            gr.Markdown("Ensina o modelo a dizer nomes de marcas, siglas e estrangeirismos. "
                        "Ex.: `XPTO` → `xis pê tê ó`, `Netflix` → `nétflics`.")
            table = gr.Dataframe(_rows(), headers=["Palavra", "Dizer como"], column_count=2,
                                 row_count=1, interactive=True)
            pr_save = gr.Button("Guardar pronúncias")
            pr_text = gr.Textbox(label="Testar: como o texto vai ser lido", lines=3)
            pr_out = gr.Textbox(label="Frases que o modelo recebe", lines=6, interactive=False)
            pr_save.click(save_pron, table, table)
            pr_text.change(preview_text, pr_text, pr_out)

        with gr.Tab("Sobre"):
            gr.Markdown(ABOUT.format(data=paths.DATA_DIR))
    return demo
