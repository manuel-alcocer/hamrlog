; Inno Setup script for hamrlog.
;
; Wraps the PyInstaller executable in a Windows installer: start menu entry,
; uninstaller and an "Add or remove programs" record. Built by CI on a Windows
; runner, since Inno Setup only runs there.
;
; Expects HamrlogVersion and the executable at ..\..\dist\hamrlog.exe

#define AppName "hamrlog"
#define AppPublisher "Manuel Alcocer"
#define AppURL "https://github.com/manuel-alcocer/hamrlog"
#define AppExeName "hamrlog.exe"

#ifndef HamrlogVersion
  #define HamrlogVersion "0.1.0"
#endif

[Setup]
AppId={{9B2F1A54-6C3D-4E7A-9F81-3C5D2B7E4A16}
AppName={#AppName}
AppVersion={#HamrlogVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=hamrlog-{#HamrlogVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Per-user install by default, so no administrator prompt is needed.
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "addtopath"; Description: "Añadir hamrlog al PATH (permite ejecutarlo desde cualquier consola)"; GroupDescription: "Opciones:"
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Opciones:"; Flags: unchecked

[Files]
Source: "..\..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Appends the install directory to the user's PATH when the task is selected.
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
    ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}')); Tasks: addtopath

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir {#AppName} ahora"; Flags: postinstall nowait skipifsilent

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  { Avoid adding the directory twice on reinstall. }
  Result := Pos(';' + Uppercase(Param) + ';', ';' + Uppercase(OrigPath) + ';') = 0;
end;
