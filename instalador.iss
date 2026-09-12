; instalador.iss
; Rutas relativas al propio .iss ({#SourcePath} incluye la barra final),
; de modo que el build funciona desde cualquier carpeta del repositorio.
#define AppName "Gestorex"
#define AppVersion "1.2.9"
#define AppPublisher "Nexus"
#define AppURL "https://importadora-cruz-966268191098.europe-west1.run.app/"
#define AppExeName "run.exe"

[Setup]
AppId={{F4A2B3C1-1234-5678-ABCD-000000000001}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir={#SourcePath}instalador_output
OutputBaseFilename=Installer_Gestorex_v1.2.9
SetupIconFile={#SourcePath}UI\assets\Logo_app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
; El ejecutable principal
Source: "{#SourcePath}dist\run.exe"; DestDir: "{app}"; Flags: ignoreversion

; El archivo .env - se instala solo si NO existe ya uno
; Asi no sobreescribe configuraciones del usuario en actualizaciones
Source: "{#SourcePath}dist\.env"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

; El icono para accesos directos
Source: "{#SourcePath}UI\assets\Logo_app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Acceso directo en el menu inicio
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\Logo_app.ico"; IconIndex: 0;

; Acceso directo en escritorio (opcional, el usuario elige)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\Logo_app.ico"; IconIndex: 0; Tasks: desktopicon

; Desinstalar desde el menu inicio
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

[Run]
; Ejecutar la app automaticamente al terminar (sin preguntar)
Filename: "{app}\{#AppExeName}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "taskkill"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden; RunOnceId: "KillApp"

[Registry]
; Registrar la app para que /RESTARTAPPLICATIONS sepa que reiniciar
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{#AppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName}"; Flags: uninsdeletekey
