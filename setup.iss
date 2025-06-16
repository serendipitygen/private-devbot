#define MyAppName        "Private Devbot"
#define MyAppVersion     "0.2.0"
#define MyAppPublisher   "Samsung Electronics Visual Display"
#define MyAppExeName     "private_devbot.bat"

[Setup]
AppId={{A1B2C3D4-E5F6-47AF-A111-22B3C4D5E6F7}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={code:GetInstallDir}
DisableProgramGroupPage=yes
OutputBaseFilename=private_devbot_setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
DiskSpanning=yes
DiskSliceSize=1992000000

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: desktopicon; Description: "바탕화면에 실행 아이콘 만들기"; \
    Flags: unchecked
Name: scheduler; Description: "작업 스케줄러에 등록"; \
    Flags: unchecked

[Files]
Source: "files\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
; 추가 파일 (zip, 아이콘)
Source: "files\embedding_model.zip"; DestDir: "{app}"; Flags: ignoreversion
Source: "files\private_devbot_conda.zip"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\private_devbot.ico"; DestDir: "{app}"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\private_devbot_silent.vbs"; \
    IconFilename: "{app}\private_devbot.ico"; Tasks: desktopicon

[Run]
; 3-2-1. 작업 스케줄러 등록 (체크한 경우만)
Filename: "{app}\register_scheduler.bat"; Flags: runhidden; Tasks: scheduler
; 3-2-2. 설치 후 "지금 실행" (FinishPageRun)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: shellexec postinstall skipifsilent

[Code]
// PascalScript
function GetInstallDir(Default: string): string;
begin
  Result := 'C:\private_devbot';
end;

procedure ExtractZip(const ZipName, TargetDir: string);
var
  ResultCode: Integer;
  PSExe, Cmd: string;
begin
  // 진행 표시 설정 (Indeterminate 스타일)
  WizardForm.StatusLabel.Caption := Format('%%s 압축 해제 중...', [ExtractFileName(ZipName)]);
  WizardForm.ProgressGauge.Style := npbstMarquee;
  WizardForm.ProgressGauge.Visible := True;

  PSExe := ExpandConstant('{sys}\\WindowsPowerShell\\v1.0\\powershell.exe');
  Cmd := '-NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath ''%s'' -DestinationPath ''%s'' -Force"';
  Exec(PSExe, Format(Cmd, [ZipName, TargetDir]), '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 진행 완료 표시
  WizardForm.ProgressGauge.Style := npbstNormal;
  WizardForm.ProgressGauge.Position := WizardForm.ProgressGauge.Max;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Zip1, Zip2, Dest1, Dest2: string;
begin
  if CurStep = ssPostInstall then
  begin
    Zip1 := ExpandConstant('{app}\embedding_model.zip');
    Zip2 := ExpandConstant('{app}\private_devbot_conda.zip');
    Dest1 := ExpandConstant('{app}');
    Dest2 := ExpandConstant('{app}');
    ExtractZip(Zip1, Dest1);
    ExtractZip(Zip2, Dest2);
    DeleteFile(Zip1);
    DeleteFile(Zip2);
  end;
end;