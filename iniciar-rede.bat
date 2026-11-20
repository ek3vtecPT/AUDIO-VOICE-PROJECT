@echo off
rem Permite aos colegas usarem o programa pelo browser: http://NOME-DESTE-PC:7860
cd /d "%~dp0"
set /p SENHA=Escolhe uma senha para os colegas (utilizador: marketing): 
call "%~dp0iniciar.bat" --rede --utilizador marketing --senha "%SENHA%"
