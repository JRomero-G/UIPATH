; instalador.iss
#define AppName "Gestorex"
#define AppVersion "1.0.7"
#define AppPublisher "Nexus"
#define AppURL "https://gestorex-desarrollo.onrender.com/"
#define AppExeName "run.exe"

[Setup]
AppId={{F4A2B3C1-1234-5678-ABCD-000000000001}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=D:\WEB\UIPATH\instalador_output
OutputBaseFilename=Installer_Gestorex_v1.0.7
SetupIconFile=D:\WEB\UIPATH\UI\assets\Logo_app.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
; El ejecutable principal
Source: "D:\WEB\UIPATH\dist\run.exe"; DestDir: "{app}"; Flags: ignoreversion

; El archivo .env — se instala solo si NO existe ya uno
; Así no sobreescribe configuraciones del usuario en actualizaciones
Source: "D:\WEB\UIPATH\dist\.env"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

; El ícono para accesos directos
Source: "D:\WEB\UIPATH\UI\assets\Logo_app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Acceso directo en el menú inicio
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\Logo_app.ico"

; Acceso directo en escritorio (opcional, el usuario elige)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\Logo_app.ico"; Tasks: desktopicon

; Desinstalar desde el menú inicio
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

[Run]
; Ofrecer ejecutar la app al terminar la instalación
Filename: "{app}\{#AppExeName}"; Description: "Ejecutar {#AppName} ahora"; Flags: nowait postinstall skipifsilent