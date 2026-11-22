; Run Build_Windows_EXE.bat, then open this script in Inno Setup and compile it.
; Use /DPayloadDir=<folder> to package a prepared Windows release folder.
#ifndef PayloadDir
  #define PayloadDir SourcePath + "dist\Krampuslauf"
#endif

#if !FileExists(PayloadDir + "\Krampuslauf.exe") || !FileExists(PayloadDir + "\VERSION.txt")
  #error Build Krampuslauf first or point PayloadDir at the extracted Windows release.
#endif

#define VersionFile FileOpen(PayloadDir + "\VERSION.txt")
#define AppVersion Trim(FileRead(VersionFile))
#expr FileClose(VersionFile)
#if AppVersion == ""
  #error The Windows package has an empty VERSION.txt.
#endif

#define SuffixStart Pos("-", AppVersion)
#if SuffixStart > 0
  #define WindowsVersion Copy(AppVersion, 1, SuffixStart - 1)
#else
  #define WindowsVersion AppVersion
#endif

[Setup]
AppId={{B4BE5839-FA1A-42CF-A614-6E4280701F27}
AppName=Krampuslauf
AppVersion={#AppVersion}
AppPublisher=Mystic Llama
AppPublisherURL=https://github.com/mystic-llama/krampuslauf
AppSupportURL=https://github.com/mystic-llama/krampuslauf/issues
AppUpdatesURL=https://github.com/mystic-llama/krampuslauf/releases/latest
DefaultDirName={autopf}\Krampuslauf
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Krampuslauf.exe
CloseApplications=yes
RestartApplications=no
OutputDir=dist\installer
OutputBaseFilename=Krampuslauf_{#AppVersion}_Windows_x64_Setup
SetupIconFile=assets\Krampuslauf.ico
VersionInfoVersion={#WindowsVersion}
VersionInfoTextVersion={#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
; Only install the application payload. Krampuslauf stores user data separately.
Source: "{#PayloadDir}\Krampuslauf.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\krampuslauf_bridge.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\CONFIGURATION.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\VERSION.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\assets\*"; DestDir: "{app}\assets"; Excludes: "*.bak.png,*.png.before-*,desktop.ini,Thumbs.db"; Flags: ignoreversion recursesubdirs
Source: "{#PayloadDir}\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs
Source: "{#PayloadDir}\third-party-notices\*"; DestDir: "{app}\third-party-notices"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\Krampuslauf"; Filename: "{app}\Krampuslauf.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Krampuslauf"; Filename: "{app}\Krampuslauf.exe"; WorkingDir: "{app}"; Tasks: desktopicon
