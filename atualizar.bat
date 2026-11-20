@echo off
cd /d "%~dp0"
if exist ".git" git pull
set "UV=%~dp0tools\uv\uv.exe"
set "UV_CACHE_DIR=%~dp0tools\uv-cache"
"%UV%" pip install --python ".venv\Scripts\python.exe" -r requirements-windows.txt
"%UV%" pip install --python ".venv\Scripts\python.exe" -U "yt-dlp[default]"
"%UV%" pip install --python ".venv\Scripts\python.exe" --no-deps -e .
echo.
echo Atualizado.
pause
