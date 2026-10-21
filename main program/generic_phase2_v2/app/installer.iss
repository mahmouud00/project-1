; =====================================================================
;  ملف التثبيت - Inno Setup 6
;  build.bat بيشغّله أوتوماتيك. الإصدار بيتاخد من app_info.py (APP_VERSION).
; =====================================================================

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#define MyAppName "نظام إدارة الورش"
#define MyAppExeName "WorkshopManager.exe"

[Setup]
; ⚠️ متغيّرش AppId أبدًا: هو اللى بيخلّى النسخة الجديدة تتثبت فوق القديمة
AppId={{9B2A39AB-C41D-4F97-A236-D6DCB176E3AD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Workshop Manager
DefaultDirName={autopf}\Workshop Manager
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; بيتثبت للمستخدم الحالى من غير ما يطلب صلاحيات Administrator
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=WorkshopManager_Setup_{#MyAppVersion}
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\WorkshopManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Open the program now"; Flags: nowait postinstall skipifsilent
