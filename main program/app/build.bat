@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   Workshop Manager - build installer
echo ================================================

findstr /C:"PUT-YOUR" app_config.py >nul
if not errorlevel 1 (
  echo [X] Put your Supabase URL and publishable key in app_config.py first.
  goto :error
)

echo [1/4] Installing libraries...
python -m pip install --upgrade -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto :error

for /f "delims=" %%v in ('python -c "import app_info; print(app_info.APP_VERSION)"') do set VER=%%v
echo     Version: %VER%

echo [2/4] Making the icon...
python make_icon.py
if errorlevel 1 goto :error

echo [3/4] Building WorkshopManager.exe (takes a few minutes)...
python -m PyInstaller workshop.spec --noconfirm --clean
if errorlevel 1 goto :error

if not exist "dist\WorkshopManager\_internal\python3.dll" echo     [!] Warning: python3.dll was not bundled
echo     Testing: open dist\WorkshopManager\WorkshopManager.exe yourself before sharing the setup.
echo [4/4] Building the setup file...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%" "%ProgramFiles%" "%LocalAppData%\Programs") do (
  for %%V in (7 6) do (
    if not defined ISCC if exist "%%~P\Inno Setup %%V\ISCC.exe" set "ISCC=%%~P\Inno Setup %%V\ISCC.exe"
  )
)
if not defined ISCC for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
if not defined ISCC (
  echo [X] Inno Setup is not installed. Download it from https://jrsoftware.org/isdl.php
  echo     If you already installed it, tell me the folder where ISCC.exe is.
  goto :error
)
echo     Using: %ISCC%
"%ISCC%" /DMyAppVersion=%VER% installer.iss
if errorlevel 1 goto :error

echo.
echo [OK] Done! Your installer is in: installer_output\WorkshopManager_Setup_%VER%.exe
explorer installer_output
pause
exit /b 0

:error
echo.
echo [X] Build failed - send a screenshot of the messages above.
pause
exit /b 1
