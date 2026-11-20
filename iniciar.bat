@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo O programa ainda nao esta instalado. Corre primeiro instalar.bat.
  pause
  exit /b 1
)
set "PATH=%~dp0tools\ffmpeg\bin;%~dp0tools\deno;%PATH%"
set PYTHONUTF8=1
".venv\Scripts\python.exe" -m estudio_voz %*
if errorlevel 1 pause
