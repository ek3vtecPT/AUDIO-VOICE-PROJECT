@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\instalar.ps1" %*
if errorlevel 1 (
  echo.
  echo A instalacao falhou. Ve a mensagem acima, corrige e volta a correr instalar.bat.
  pause
  exit /b 1
)
echo.
echo Instalacao concluida. Abre o programa pelo atalho "Estudio de Voz".
pause
