; Inno Setup script for hamrlog.
;
; Wraps the PyInstaller executable in a graphical Windows installer that
; installs, upgrades and uninstalls:
;
; - Upgrade: running the installer of a newer version over an installed one
;   keeps its folder and options, closes a running hamrlog and says which
;   version it replaces. The same version offers a repair; an older one asks
;   before going back (and refuses when silent).
; - Uninstall: from "Add or remove programs" or the start menu. Takes hamrlog
;   out of PATH and asks before deleting the log and settings.
;
; Built by CI on a Windows runner, since Inno Setup only runs there.
; Expects HamrlogVersion and the executable at ..\..\dist\hamrlog.exe
;
; Silent use, as the release workflow tests it:
;   hamrlog-X.Y.Z-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /TASKS=addtopath
;   unins000.exe /VERYSILENT /SUPPRESSMSGBOXES     (keeps the log)
;
; hamrlog upgrades itself by running the new setup with /SILENT /RELAUNCH
; (see hamrlog/updater.py): a progress bar only, and hamrlog opens again at
; the end.

#define AppName "hamrlog"
#define AppPublisher "Manuel Alcocer"
#define AppURL "https://github.com/manuel-alcocer/hamrlog"
#define AppExeName "hamrlog.exe"

; No default: semantic-release bumps the version everywhere else, and a
; number written here would fall behind.
#ifndef HamrlogVersion
  #error Pass the version: iscc /DHamrlogVersion=X.Y.Z hamrlog.iss
#endif

[Setup]
; Never change it: upgrades find the installed copy through it.
AppId={{9B2F1A54-6C3D-4E7A-9F81-3C5D2B7E4A16}
AppName={#AppName}
AppVersion={#HamrlogVersion}
AppVerName={#AppName} {#HamrlogVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#HamrlogVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AlwaysShowDirOnReadyPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=hamrlog-{#HamrlogVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=auto
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
; Per-user install by default, so no administrator prompt is needed.
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; A running hamrlog locks its executable: close it before replacing it.
CloseApplications=yes
RestartApplications=no
; PATH changes reach new consoles without logging out.
ChangesEnvironment=yes
; The demo folder lives in the user's profile even for a machine-wide install.
UsedUserAreasWarning=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.Options=Options:
spanish.Options=Opciones:
english.AddToPath=Add hamrlog to PATH (run it from any console)
spanish.AddToPath=Añadir hamrlog al PATH (permite ejecutarlo desde cualquier consola)
english.BuildingDemo=Preparing the demo database...
spanish.BuildingDemo=Preparando la base de datos de demostración...
english.UpgradeCaption=Upgrade hamrlog %1 to %2
spanish.UpgradeCaption=Actualizar hamrlog %1 a %2
english.ReadyUpgrade=hamrlog %1 will be upgraded to %2. Your log and settings are kept.
spanish.ReadyUpgrade=Se actualizará hamrlog %1 a %2. Tu diario y tu configuración se conservan.
english.SameVersion=hamrlog %1 is already installed.%n%nInstall it again to repair it?
spanish.SameVersion=hamrlog %1 ya está instalado.%n%n¿Instalarlo de nuevo para repararlo?
english.Downgrade=hamrlog %1 is installed, newer than this installer (%2).%n%nGo back to the older version anyway?
spanish.Downgrade=Está instalado hamrlog %1, más nuevo que este instalador (%2).%n%n¿Volver de todos modos a la versión anterior?
english.DeleteUserData=Also delete your log and settings?%n%n%1%n%nEvery QSO in it will be lost. Choose No to keep them for a later install.
spanish.DeleteUserData=¿Borrar también tu diario y tu configuración?%n%n%1%n%nSe perderán todos los QSO que contiene. Elige No para conservarlos para otra instalación.

[Tasks]
Name: "addtopath"; Description: "{cm:AddToPath}"; GroupDescription: "{cm:Options}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:Options}"; Flags: unchecked

[Files]
Source: "..\..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Rebuilt on every install and upgrade, so the demo matches the new version.
Filename: "{app}\{#AppExeName}"; Parameters: "build-demo"; StatusMsg: "{cm:BuildingDemo}"; \
    Flags: runhidden runasoriginaluser
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: postinstall nowait skipifsilent
; After an upgrade started from hamrlog itself, which closed to let it run.
Filename: "{app}\{#AppExeName}"; Flags: nowait runasoriginaluser; Check: WantsRelaunch

[UninstallDelete]
; The demo template is derived data; the log next to it is left to the user.
Type: filesandordirs; Name: "{userappdata}\{#AppName}\demo"

[Code]
const
  { Where Inno Setup records an install: AppId plus "_is1". }
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{9B2F1A54-6C3D-4E7A-9F81-3C5D2B7E4A16}_is1';
  NewVersion = '{#HamrlogVersion}';

var
  { The version this installer replaces; empty on a fresh install. }
  PreviousVersion: String;

{ The installed version, per user or machine-wide; empty when there is none. }
function InstalledVersion(): String;
begin
  if not RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', Result) then
    if not RegQueryStringValue(HKLM, UninstallKey, 'DisplayVersion', Result) then
      Result := '';
end;

{ Takes the next dot-separated number off the front of S; 0 once S is empty. }
function NextVersionPart(var S: String): Integer;
var
  Dot: Integer;
begin
  Dot := Pos('.', S);
  if Dot = 0 then
  begin
    Result := StrToIntDef(S, 0);
    S := '';
  end
  else
  begin
    Result := StrToIntDef(Copy(S, 1, Dot - 1), 0);
    S := Copy(S, Dot + 1, Length(S));
  end;
end;

{ Negative, zero or positive as A is older than, equal to or newer than B. }
function CompareVersions(A, B: String): Integer;
begin
  Result := 0;
  while (Result = 0) and ((A <> '') or (B <> '')) do
    Result := NextVersionPart(A) - NextVersionPart(B);
end;

{ /RELAUNCH: hamrlog started this setup and closed; open it again at the end. }
function WantsRelaunch(): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/RELAUNCH') = 0 then
      Result := True;
end;

function IsUpgrade(): Boolean;
begin
  Result := (PreviousVersion <> '') and (CompareVersions(NewVersion, PreviousVersion) > 0);
end;

function InitializeSetup(): Boolean;
var
  Order: Integer;
begin
  Result := True;
  PreviousVersion := InstalledVersion();
  if PreviousVersion = '' then
    exit;

  Order := CompareVersions(NewVersion, PreviousVersion);
  if Order = 0 then
    Result := SuppressibleMsgBox(FmtMessage(CustomMessage('SameVersion'), [PreviousVersion]),
      mbConfirmation, MB_YESNO, IDYES) = IDYES
  else if Order < 0 then
    { Silent installs take the default, No: they never downgrade. }
    Result := SuppressibleMsgBox(
      FmtMessage(CustomMessage('Downgrade'), [PreviousVersion, NewVersion]),
      mbError, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
end;

procedure InitializeWizard();
begin
  if IsUpgrade() then
    WizardForm.Caption := FmtMessage(CustomMessage('UpgradeCaption'), [PreviousVersion, NewVersion]);
end;

{ The licence was accepted on the first install. }
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpLicense) and (PreviousVersion <> '');
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := '';
  if IsUpgrade() then
    Result := FmtMessage(CustomMessage('ReadyUpgrade'), [PreviousVersion, NewVersion])
      + NewLine + NewLine;
  Result := Result + MemoDirInfo;
  if MemoTasksInfo <> '' then
    Result := Result + NewLine + NewLine + MemoTasksInfo;
end;

{ The user's PATH for a per-user install, the system's for a machine-wide one. }
function EnvironmentRoot(): Integer;
begin
  if IsAdminInstallMode() then
    Result := HKLM
  else
    Result := HKCU;
end;

function EnvironmentKey(): String;
begin
  if IsAdminInstallMode() then
    Result := 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
  else
    Result := 'Environment';
end;

{ PathValue without Dir, ignoring case and a trailing backslash. }
function PathWithout(PathValue, Dir: String): String;
var
  Entry: String;
  Separator: Integer;
begin
  Result := '';
  Dir := RemoveBackslashUnlessRoot(Uppercase(Dir));
  while PathValue <> '' do
  begin
    Separator := Pos(';', PathValue);
    if Separator = 0 then
    begin
      Entry := PathValue;
      PathValue := '';
    end
    else
    begin
      Entry := Copy(PathValue, 1, Separator - 1);
      PathValue := Copy(PathValue, Separator + 1, Length(PathValue));
    end;
    if (Entry <> '') and (RemoveBackslashUnlessRoot(Uppercase(Entry)) <> Dir) then
    begin
      if Result <> '' then
        Result := Result + ';';
      Result := Result + Entry;
    end;
  end;
end;

{ Adds Dir to PATH or takes it out, once, leaving every other entry alone. }
procedure SetInPath(Dir: String; Wanted: Boolean);
var
  OldPath, NewPath: String;
begin
  if not RegQueryStringValue(EnvironmentRoot(), EnvironmentKey(), 'Path', OldPath) then
    OldPath := '';
  NewPath := PathWithout(OldPath, Dir);
  if Wanted then
  begin
    if NewPath <> '' then
      NewPath := NewPath + ';';
    NewPath := NewPath + Dir;
  end;
  if NewPath <> OldPath then
    RegWriteExpandStringValue(EnvironmentRoot(), EnvironmentKey(), 'Path', NewPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { Also on upgrades, so unticking the task takes hamrlog out of PATH. }
  if CurStep = ssPostInstall then
    SetInPath(ExpandConstant('{app}'), WizardIsTaskSelected('addtopath'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
    SetInPath(ExpandConstant('{app}'), False);

  { Silent uninstalls keep the data: nobody was asked. }
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent() then
  begin
    DataDir := ExpandConstant('{userappdata}\{#AppName}');
    if DirExists(DataDir) then
      if MsgBox(FmtMessage(CustomMessage('DeleteUserData'), [DataDir]),
          mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
