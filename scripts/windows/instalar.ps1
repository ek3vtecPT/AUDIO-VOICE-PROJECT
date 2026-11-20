# Instalador do Estúdio de Voz para Windows 10/11.
# Instala tudo dentro da pasta do programa (Python, PyTorch, ffmpeg, deno), sem mexer no resto do PC.
#   -CPU         PyTorch sem CUDA (para PCs sem placa NVIDIA / testes)
#   -SemModelos  não descarregar já os modelos (são descarregados na primeira utilização)
#   -SemAtalho   não criar o atalho no ambiente de trabalho
param([switch]$CPU, [switch]$SemModelos, [switch]$SemAtalho)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # torna os downloads muito mais rápidos
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root  = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Tools = Join-Path $Root "tools"
New-Item -ItemType Directory -Force -Path $Tools | Out-Null

function Passo([string]$t) { Write-Host ""; Write-Host "==> $t" -ForegroundColor Cyan }
function Verificar([string]$o) { if ($LASTEXITCODE -ne 0) { throw "Falhou: $o (código $LASTEXITCODE)" } }

function Extrair-Zip([string]$url, [string]$nome) {
    $zip = Join-Path $env:TEMP "$nome.zip"
    $dir = Join-Path $env:TEMP "$nome-extraido"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
    Expand-Archive -Path $zip -DestinationPath $dir -Force
    Remove-Item $zip -Force
    return $dir
}

# ---------------------------------------------------------------- 1. uv (gestor de Python)
$UvDir = Join-Path $Tools "uv"
$Uv = Join-Path $UvDir "uv.exe"
if (-not (Test-Path $Uv)) {
    Passo "A descarregar o uv (gestor de Python)"
    $x = Extrair-Zip "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" "uv"
    New-Item -ItemType Directory -Force -Path $UvDir | Out-Null
    Get-ChildItem -Path $x -Recurse -Filter "uv*.exe" | Copy-Item -Destination $UvDir -Force
    Remove-Item -Recurse -Force $x
}

$env:UV_CACHE_DIR = Join-Path $Tools "uv-cache"
$env:UV_LINK_MODE = "copy"

# ---------------------------------------------------------------- 2. Python 3.11 portátil
# Descarregado e extraído diretamente para tools\python: não precisa de Python no PC e
# não cria ligações de pastas (junctions), que alguns Windows bloqueiam (erro 448).
$PyHome = Join-Path $Tools "python311"   # pasta nova: ignora restos de tentativas anteriores
$PyBase = Join-Path $PyHome "python.exe"
if (-not (Test-Path $PyBase)) {
    Passo "A descarregar o Python 3.11 (portátil, só para este programa)"
    $url = $null
    try {
        $lista = & $Uv python list 3.11 --all-platforms --only-downloads --output-format json 2>$null | ConvertFrom-Json
        $url = ($lista | Where-Object { $_.implementation -eq "cpython" -and $_.os -eq "windows" -and
                 $_.arch -eq "x86_64" -and $_.variant -eq "default" -and $_.url -like "*.tar.gz" } |
                Select-Object -First 1).url
    } catch { $url = $null }
    if (-not $url) {
        $url = "https://releases.astral.sh/github/python-build-standalone/releases/download/20260718/cpython-3.11.15%2B20260718-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
    }
    $tgz = Join-Path $env:TEMP "python-portatil.tar.gz"
    $tmp = Join-Path $env:TEMP "python-portatil"
    Invoke-WebRequest -Uri $url -OutFile $tgz -UseBasicParsing
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    & tar.exe -xzf $tgz -C $tmp; Verificar "extrair o Python"
    if (Test-Path $PyHome) { Remove-Item -Recurse -Force $PyHome }
    Move-Item -Path (Join-Path $tmp "python") -Destination $PyHome
    Remove-Item -Recurse -Force $tmp, $tgz
}
& $PyBase -c "import sys; print('Python', sys.version.split()[0])"; Verificar "testar o Python"
$env:UV_PYTHON_DOWNLOADS = "never"   # daqui em diante o uv usa só este Python

$Venv = Join-Path $Root ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Passo "A criar o ambiente do programa"
    & $PyBase -m venv --without-pip $Venv; Verificar "criar ambiente Python"
}

# ---------------------------------------------------------------- 3. PyTorch
if ($CPU) { $TorchIndex = "https://download.pytorch.org/whl/cpu" }
else      { $TorchIndex = "https://download.pytorch.org/whl/cu124" }
Passo "A instalar o PyTorch ($(if ($CPU) {'CPU'} else {'NVIDIA CUDA 12.4'})) - cerca de 2,5 GB, pode demorar"
& $Uv pip install --python $Py "torch==2.6.0" "torchaudio==2.6.0" --index-url $TorchIndex; Verificar "instalar PyTorch"

# ---------------------------------------------------------------- 4. Restantes bibliotecas
Passo "A instalar as bibliotecas do programa"
& $Uv pip install --python $Py -r (Join-Path $Root "requirements-windows.txt"); Verificar "instalar bibliotecas"
& $Uv pip install --python $Py --no-deps -e $Root; Verificar "instalar o Estúdio de Voz"

if (-not $CPU) {
    $cuda = & $Py -c "import torch; print(torch.version.cuda or '')"
    if (-not $cuda) {
        Passo "O PyTorch ficou sem CUDA; a reinstalar a versão para NVIDIA"
        & $Uv pip install --python $Py --reinstall-package torch --reinstall-package torchaudio `
            "torch==2.6.0" "torchaudio==2.6.0" --index-url $TorchIndex; Verificar "reinstalar PyTorch"
    }
}

# ---------------------------------------------------------------- 5. ffmpeg
$FfBin = Join-Path $Tools "ffmpeg\bin"
if (-not (Test-Path (Join-Path $FfBin "ffmpeg.exe"))) {
    Passo "A descarregar o ffmpeg"
    $x = Extrair-Zip "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" "ffmpeg"
    New-Item -ItemType Directory -Force -Path $FfBin | Out-Null
    Get-ChildItem -Path $x -Recurse -Include "ffmpeg.exe", "ffprobe.exe" | Copy-Item -Destination $FfBin -Force
    Remove-Item -Recurse -Force $x
}

# ---------------------------------------------------------------- 6. deno (o yt-dlp precisa dele para o YouTube)
$DenoDir = Join-Path $Tools "deno"
if (-not (Test-Path (Join-Path $DenoDir "deno.exe"))) {
    Passo "A descarregar o deno (usado pelo yt-dlp)"
    $x = Extrair-Zip "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip" "deno"
    New-Item -ItemType Directory -Force -Path $DenoDir | Out-Null
    Get-ChildItem -Path $x -Recurse -Filter "deno.exe" | Copy-Item -Destination $DenoDir -Force
    Remove-Item -Recurse -Force $x
}

$env:PATH = "$FfBin;$DenoDir;$env:PATH"
$env:PYTHONUTF8 = "1"

# ---------------------------------------------------------------- 7. Modelos
if (-not $SemModelos) {
    Passo "A descarregar os modelos de voz (cerca de 3 GB, só desta vez)"
    & $Py -m estudio_voz --descarregar-modelos; Verificar "descarregar modelos"
}

# ---------------------------------------------------------------- 8. Atalho
if (-not $SemAtalho) {
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Estúdio de Voz.lnk"))
    $lnk.TargetPath = Join-Path $Root "iniciar.bat"
    $lnk.WorkingDirectory = $Root
    $lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,103"
    $lnk.Save()
}

Passo "Concluído"
& $Py -c "from estudio_voz.tts import gpu_info; print(gpu_info())"
