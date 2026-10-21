; 由 build-installer.ps1 傳入 AppVersion、SourceDir、OutputDir
[Setup]
AppId={{6F1C2B7E-4D58-4A1B-9C3E-5A7D2E8B1F40}
AppName=Pinakes
AppVersion={#AppVersion}
AppPublisher=Pinakes
DefaultDirName={localappdata}\Programs\Pinakes
DefaultGroupName=Pinakes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=Pinakes-Setup
SetupIconFile={#SourceDir}\pinakes.ico
UninstallDisplayIcon={app}\pinakes.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start Pinakes when I sign in"; GroupDescription: "Startup:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Pinakes"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\tray.py"""; WorkingDir: "{app}"; IconFilename: "{app}\pinakes.ico"
Name: "{autodesktop}\Pinakes"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\tray.py"""; WorkingDir: "{app}"; IconFilename: "{app}\pinakes.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Pinakes"; ValueData: """{app}\python\pythonw.exe"" ""{app}\tray.py"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\tray.py"""; WorkingDir: "{app}"; Description: "Launch Pinakes"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure StopApp();
var
  code: Integer;
  cmd: String;
begin
  cmd := '-NoProfile -Command "Get-Process | Where-Object { $_.Name -match ''^(pythonw?|ffmpeg|ffprobe)$'' -and $_.Path -like ''' +
    ExpandConstant('{app}') + '\*'' } | Stop-Process -Force"';
  Exec('powershell.exe', cmd, '', SW_HIDE, ewWaitUntilTerminated, code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopApp();
  Result := True;
end;
