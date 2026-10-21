; ===============================================================================
; HEART Framework - Environmental Perturbation Engine Studio Setup Script
; Inno Setup 6.x Script
; ===============================================================================

#define MyAppName "HEART Studio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "HEART Research Team (SLIIT J26-SE-334)"
#define MyAppURL "https://github.com/luqmanbooso/J26-SE-334"
#define MyAppExeName "HEART_Studio.exe"

[Setup]
AppId={{E68A9F20-8BC2-4E38-9B1D-66D26815FA29}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\HEART_Studio
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\dist_installer
OutputBaseFilename=HEART_Studio_Setup_v1.0
SetupIconFile=..\heart_app.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Standalone Application Binaries & Python Runtime
Source: "..\dist\HEART_Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Bundled Standalone ADB Platform-Tools (if present)
Source: "..\platform-tools\*"; DestDir: "{app}\platform-tools"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; Standalone Desktop App Icon
Source: "..\heart_app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\heart_app.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\heart_app.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
