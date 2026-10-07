; Inno Setup script for the MUNCH Windows installer.
;
; Packages the PyInstaller folder build (dist\MUNCH\, from munch.spec) into a
; single setup .exe. Installs per-user (no admin/UAC prompt) into
; %LOCALAPPDATA%\Programs\MUNCH, with a Start Menu shortcut, an optional
; desktop shortcut, and a regular entry in Windows "Installed apps".
;
; Build (after PyInstaller):
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
; Output: dist\MUNCH-Setup-<version>.exe
;
; The version comes from munch\version.py (the app's single source of truth),
; so bump it there, not here. MyAppName / MyAppId / MyAppVersion can be
; overridden on the command line (/DMyAppName=...) to build isolated test
; installers that never touch a real MUNCH install.

#ifndef MyAppVersion
  ; Pull "1.0.0" out of line 1 of munch\version.py:  VERSION = "1.0.0"
  #define VersionFile FileOpen(AddBackslash(SourcePath) + "munch\version.py")
  #define VersionLine FileRead(VersionFile)
  #expr FileClose(VersionFile)
  #define VersionQuoted Copy(VersionLine, Pos('"', VersionLine) + 1)
  #define MyAppVersion Copy(VersionQuoted, 1, Pos('"', VersionQuoted) - 1)
#endif
#ifndef MyAppName
  #define MyAppName "MUNCH"
#endif
#ifndef MyAppId
  ; Identifies MUNCH to Windows across versions — never change it, or
  ; upgrades will install side by side instead of replacing the old copy.
  #define MyAppId "78659045-1A60-46FE-A37F-F12EF3C10589"
#endif
#define MyAppPublisher "Nicholas Januar"
#pragma message "Building " + MyAppName + " " + MyAppVersion
#define MyAppURL "https://github.com/kallui/munch"
#define MyAppExeName "MUNCH.exe"

[Setup]
AppId={{{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Re-running setup (e.g. an update) while MUNCH is open asks to close it first.
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; On an upgrade, clear out the previous version's bundled libraries first.
; Their file names carry version hashes (e.g. avcodec-63-<hash>.dll), so
; plain overwriting would leave every old copy behind forever. Safe: user
; settings live in %APPDATA%\MUNCH, never in here.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\MUNCH\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; License texts travel with every installed copy (MIT for MUNCH itself, plus
; the notices for the bundled third-party components).
Source: "LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\icons\NOTICE.md"; DestDir: "{app}"; DestName: "ICONS_NOTICE.md"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

; User settings (%APPDATA%\MUNCH) and the downloaded speech model are
; deliberately left on uninstall, the usual Windows convention — so a
; reinstall or upgrade keeps the user's setup and doesn't re-download.
