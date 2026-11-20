; Instalador (Setup.exe) do Estúdio de Voz — compilar com Inno Setup 6:
;   ISCC.exe scripts\windows\EstudioVoz.iss
; Copia o programa e corre instalar.bat, que descarrega Python, PyTorch, ffmpeg e modelos.

#define AppVersion "0.1.0"

[Setup]
AppId={{8F3A3C1E-5B7D-4E8A-9C61-2D4B7E0F1A93}
AppName=Estúdio de Voz
AppVersion={#AppVersion}
AppPublisher=ek3vtecPT
DefaultDirName={localappdata}\Programs\EstudioVoz
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\saida_instalador
OutputBaseFilename=EstudioVoz-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Files]
Source: "..\..\estudio_voz\*"; DestDir: "{app}\estudio_voz"; Excludes: "__pycache__"; Flags: ignoreversion recursesubdirs
Source: "..\..\scripts\windows\instalar.ps1"; DestDir: "{app}\scripts\windows"; Flags: ignoreversion
Source: "..\..\instalar.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\iniciar.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\iniciar-rede.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\atualizar.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\requirements-windows.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Estúdio de Voz"; Filename: "{app}\iniciar.bat"; WorkingDir: "{app}"; IconFilename: "{sys}\imageres.dll"; IconIndex: 103
Name: "{autodesktop}\Estúdio de Voz"; Filename: "{app}\iniciar.bat"; WorkingDir: "{app}"; IconFilename: "{sys}\imageres.dll"; IconIndex: 103
Name: "{autoprograms}\Estúdio de Voz (rede local)"; Filename: "{app}\iniciar-rede.bat"; WorkingDir: "{app}"

[Run]
Filename: "{app}\instalar.bat"; Parameters: "-SemAtalho"; WorkingDir: "{app}"; StatusMsg: "A descarregar Python, PyTorch, ffmpeg e modelos (20 a 40 minutos)..."; Flags: waituntilterminated
Filename: "{app}\iniciar.bat"; Description: "Abrir o Estúdio de Voz"; Flags: postinstall nowait skipifsilent shellexec

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\estudio_voz"
