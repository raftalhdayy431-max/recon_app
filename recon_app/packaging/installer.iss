; Inno Setup — يصنع ملف تثبيت واحد: ReconPro-Setup-<الإصدار>.exe
#define AppName "المطابقة والتسوية المالية"
#define AppVer "1.0.0"
#define AppExe "ReconPro.exe"

[Setup]
AppId={{6B1D2C5E-3F0A-4C8E-9C57-5A7E1D4B9A21}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=Reconciliation Pro
DefaultDirName={autopf}\ReconPro
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=ReconPro-Setup-{#AppVer}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب / Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\ReconPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "تشغيل البرنامج الآن / Launch now"; Flags: nowait postinstall skipifsilent
