; Script Inno Setup d'EduPaie. La version vient de edupaie/version.py (via outils/construire.py).
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
; Identité de l'application : ne la change JAMAIS, elle permet les mises à jour par-dessus.
AppId={{B6D3C1A4-7E52-4F0B-9A38-2C5D81E94F07}
AppName=EduPaie
AppVersion={#AppVersion}
AppVerName=EduPaie {#AppVersion}
AppPublisher=VOTRE NOM OU VOTRE ENTREPRISE
DefaultDirName={autopf}\EduPaie
DefaultGroupName=EduPaie
DisableProgramGroupPage=yes
OutputDir=installateur
OutputBaseFilename=EduPaie_Setup_{#AppVersion}
SetupIconFile=assets\EduPaie.ico
UninstallDisplayIcon={app}\EduPaie.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\EduPaie\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\EduPaie"; Filename: "{app}\EduPaie.exe"
Name: "{group}\Désinstaller EduPaie"; Filename: "{uninstallexe}"
Name: "{autodesktop}\EduPaie"; Filename: "{app}\EduPaie.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EduPaie.exe"; Description: "{cm:LaunchProgram,EduPaie}"; Flags: nowait postinstall skipifsilent

[Code]
// Les données (élèves, paiements, sauvegardes) sont dans %LOCALAPPDATA%\EduPaie :
// ce script ne les supprime jamais, ni à l'installation, ni à la désinstallation.

function TableurInstalle: Boolean;
var
  ProgId: String;
begin
  // Si les fichiers .xlsx ont un programme associé (Excel, LibreOffice, WPS...), c'est bon.
  Result := RegQueryStringValue(HKEY_CLASSES_ROOT, '.xlsx', '', ProgId) and (ProgId <> '');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WizardSilent) and (not TableurInstalle) then
    MsgBox('Aucun tableur (Excel, LibreOffice...) n''a été détecté sur cet ordinateur.' + #13#10 + #13#10 +
           'EduPaie fonctionne sans, mais les exports Excel ne pourront pas s''ouvrir directement. ' +
           'Installez LibreOffice (gratuit) ou Excel pour les consulter.', mbInformation, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox('EduPaie a été désinstallé.' + #13#10 + #13#10 +
           'Les données de l''école (élèves, paiements, sauvegardes) ont été conservées dans le ' +
           'dossier %LOCALAPPDATA%\EduPaie. Ne les supprimez pas : elles servent si le logiciel ' +
           'est réinstallé.', mbInformation, MB_OK);
end;