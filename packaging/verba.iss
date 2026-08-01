#define MyAppName "Verba"
#define MyAppVersion "0.1.0"
#define MyAppExeName "Verba.exe"
#define MyAppPublisher "HuberttFox"

[Setup]
AppId={{DDB92E15-C5AF-4352-B2B8-3C790DFE3BAC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Verba
DefaultGroupName=Verba
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#SourcePath}output
OutputBaseFilename=verba-0.1.0-setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Verba.exe
WizardStyle=modern

[Tasks]
Name: "autostart"; Description: "Start Verba automatically at logon"; GroupDescription: "Additional tasks:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional tasks:"

[Files]
Source: "{#SourcePath}dist\Verba\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Verba"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall Verba"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Verba"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Verba"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Verba"; Flags: nowait postinstall skipifsilent
