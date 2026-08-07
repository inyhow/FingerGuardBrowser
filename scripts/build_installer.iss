; Inno Setup 6 script for FingerGuard Browser
; Build steps:
;   1. Run scripts\build_exe.bat to produce dist\FingerGuardBrowser-Windows
;   2. Open this .iss file in Inno Setup Compiler and click Build
;   3. Output: dist\FingerGuardBrowser-Setup.exe

#define MyAppName "FingerGuard Browser"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "FingerGuard"
#define MyAppURL "https://github.com/yourusername/FingerGuardBrowser"
#define MyAppExeName "FingerGuardBrowser.exe"

[Setup]
AppId={{FINGERGUARD-BROWSER-1.0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\FingerGuardBrowser
DisableProgramGroupPage=yes
LicenseFile=..
OutputDir=..\dist
OutputBaseFilename=FingerGuardBrowser-Setup
SetupIconFile=
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\FingerGuardBrowser-Windows\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
