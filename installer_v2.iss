; Script de Geracao de Instalador Inno Setup 7
; Mix de Ofertas & Encartes 2.0 (Aplicativo Desktop Nativo)
; Supermercados Opcao

#define MyAppName "Mix de Ofertas"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Supermercados Opcao"
#define MyAppExeName "Mix_Ofertas_v2.exe"

[Setup]
AppId={{D8A13B44-59E2-4C10-8E14-72DF901C9A02}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Mix de Ofertas 2.0
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=Mix_Ofertas_Setup_v2.0
SetupIconFile=app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist_bin_v2\Mix_Ofertas_v2\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
