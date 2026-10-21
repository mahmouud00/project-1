; =====================================================================
;  ملف التثبيت - Inno Setup 6
;  build.bat بيشغّله أوتوماتيك. الإصدار بيتاخد من app_info.py (APP_VERSION).
; =====================================================================

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "build_nuitka\main.dist"
#endif
#define MyAppName "SUITES"
#define MyAppExeName "SUITES.exe"

[Setup]
; ⚠️ متغيّرش AppId أبدًا: هو اللى بيخلّى النسخة الجديدة تتثبت فوق القديمة
AppId={{795C76A3-41A5-4B19-8877-FC330AA5E26C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=MYTECH Solutions
DefaultDirName={autopf}\SUITES
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; بيتثبت للمستخدم الحالى من غير ما يطلب صلاحيات Administrator
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=SUITES_Setup_{#MyAppVersion}
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
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Open the program now"; Flags: nowait postinstall skipifsilent

; البيانات (قاعدة البيانات والنسخ الاحتياطية) فى %LOCALAPPDATA%\TailorMaster
; وإلغاء التثبيت مش بيمسحها، عشان التحديث أو إعادة التثبيت ميضيعش حاجة.
