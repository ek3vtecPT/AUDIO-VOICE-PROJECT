# Estúdio de Voz

Programa para Windows que transforma o texto das publicações em **locuções em português** para os vídeos,
com **a tua própria voz**. Funciona no teu PC (placa NVIDIA), sem serviços pagos e sem enviar a voz para fora.

## O que faz

| Separador | Para quê |
|---|---|
| **Locução** | Cola o texto → escolhe a voz → afina velocidade, tom, timbre, expressividade e acabamento → WAV, MP3 e legendas SRT. |
| **Vídeo** | Junta a locução ao vídeo, baixa a música original enquanto falas e grava as legendas na imagem. |
| **Vozes** | Cria vozes a partir de **links dos teus vídeos** (YouTube, Vimeo, Facebook, Instagram…), ficheiros ou gravações no microfone. Retira a música, corta a fala e descarta outras pessoas automaticamente. |
| **Pronúncia** | Ensina como se dizem marcas, siglas e estrangeirismos. |

## Instalar (Windows 10/11 com placa NVIDIA)

**Opção A — Setup.exe:** no GitHub, *Actions → Testes e instalador →* última execução → *Artifacts →*
`EstudioVoz-Setup`. Corre o `Setup.exe` (não pede administrador). Demora 20 a 40 min porque descarrega
Python, PyTorch (~2,5 GB), ffmpeg e os modelos (~3 GB).

**Opção B — a partir do código:** descarrega/clona o repositório e faz duplo clique em `instalar.bat`.

Depois abre pelo atalho **Estúdio de Voz** (abre uma janela própria do Edge).

- `iniciar-rede.bat` — os colegas do marketing usam o programa pelo browser em `http://NOME-DO-PC:7860`,
  com utilizador `marketing` e a senha que escolheres. Só o teu PC precisa da placa gráfica.
- `atualizar.bat` — atualiza o programa e o yt-dlp (necessário quando uma plataforma muda).

Requisitos: Windows 10/11, driver NVIDIA recente, ~20 GB livres. Sem NVIDIA funciona, mas muito devagar.

## Criar a tua voz

1. Separador **Vozes** → escreve um nome → **Criar**.
2. Cola os links dos teus vídeos (um por linha). Podes indicar só um troço: `https://youtu.be/xxxx 1:30-12:45`.
3. **Processar material.** O programa descarrega, retira a música (Demucs), corta a fala (Silero VAD) e mantém
   só a tua voz (compara com a voz que aparece mais). No fim cria a **amostra de referência** automaticamente.
4. No separador **Locução**, escolhe a voz, afina e carrega em **Guardar afinação nesta voz**.

Quanto material: 1 minuto já chega para clonar; **20 a 30 minutos** de fala limpa preparam o treino profundo (fase 2).

## Os teus dados

Tudo fica em `%LOCALAPPDATA%\EstudioVoz` (vozes, material, modelos, locuções). **Nada disto vai para o GitHub.**
Desinstalar o programa não apaga esta pasta.

## Avisos legais

- Usa só a tua voz, ou vozes de quem te deu autorização por escrito.
- **AI Act (art. 50):** indica nas publicações que a locução foi gerada por IA.
  O áudio gerado tem uma marca de água inaudível (Chatterbox/Perth) e os ficheiros levam essa indicação nos metadados.
- Descarrega apenas vídeos teus ou com autorização (os termos das plataformas podem limitar downloads).

## Arquitetura

```
Texto → pronúncias/números → frases ─► Chatterbox (pt) ─► timbre/tom/velocidade ─► EQ/compressão ─► −16 LUFS
                                         ▲ amostra de referência                                (pedalboard, pyloudnorm)
Links/ficheiros ─► yt-dlp/ffmpeg ─► Demucs (voz) ─► Silero VAD ─► filtro de orador ─► excertos 2–12 s
```

| Módulo | Função |
|---|---|
| `estudio_voz/text.py` | limpeza do texto, `[pausa 1.5]`, números por extenso (pt-PT), dicionário de pronúncia |
| `estudio_voz/tts.py` | Chatterbox Multilingue (MIT), carregado só quando é preciso |
| `estudio_voz/effects.py` | velocidade, tom, timbre (formantes), acabamentos, volume |
| `estudio_voz/dataset.py` | material de treino a partir de links, ficheiros e microfone |
| `estudio_voz/video.py` | mistura com ffmpeg, *ducking*, legendas |
| `estudio_voz/captions.py` | SRT com o texto exato e tempos de cada frase |
| `estudio_voz/ui.py` | interface Gradio |

Desenvolvimento (Linux/macOS): `pip install -r requirements-teste.txt && python -m pytest`.
Os testes usam um motor de voz falso; o CI do Windows corre o instalador real em modo CPU.

## Fases

- [x] **Fase 1:** locução em português, afinação, acabamentos, vídeo com legendas, vozes a partir de links/ficheiros/microfone.
- [ ] **Fase 2:** treino profundo da voz (RVC) com o material já preparado, para ficar ainda mais parecida.
- [ ] **Fase 3:** geração em lote a partir de CSV, regenerar só uma frase, legendas palavra a palavra.

## Licenças

Chatterbox, Demucs, Silero VAD: MIT · yt-dlp: Unlicense · pedalboard: GPL-3.0 · ffmpeg (build GPL) · Gradio: Apache-2.0.
Todos permitem uso comercial; a pedalboard e o ffmpeg GPL obrigam a disponibilizar o código se o programa for distribuído a terceiros.
