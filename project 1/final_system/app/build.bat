@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   SUITES - build installer (Nuitka)
echo ================================================

findstr /C:"PUT-YOUR" server\license_key.py >nul
if not errorlevel 1 (
  echo [X] Run the license key generator first:  python ..\license_tool\keygen.py
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

echo [3/4] Compiling SUITES.exe with Nuitka (first time takes 10-20 minutes)...
python -m nuitka main.py --standalone --assume-yes-for-downloads --enable-plugin=pyside6 ^
  --windows-console-mode=disable --windows-icon-from-ico=assets\app.ico ^
  --include-data-dir=assets=assets --include-package=server ^
  --include-module=cryptography.hazmat.primitives.asymmetric.ed25519 ^
  --nofollow-import-to=tkinter --output-dir=build_nuitka --output-filename=SUITES.exe ^
  --company-name="MYTECH Solutions" --product-name="SUITES" --file-description="SUITES" ^
  --file-version=%VER% --product-version=%VER%
if errorlevel 1 (
  echo [X] Nuitka failed. You can still make a setup with build_quick.bat
  goto :error
)
echo     Testing: open build_nuitka\main.dist\SUITES.exe yourself before sharing the setup.

echo [4/4] Building the setup file...
call :find_iscc
if not defined ISCC goto :error
"%ISCC%" /DMyAppVersion=%VER% /DSourceDir=build_nuitka\main.dist installer.iss
if errorlevel 1 goto :error

echo.
echo [OK] Done! Your installer is in: installer_output\SUITES_Setup_%VER%.exe
explorer installer_output
pause
exit /b 0

:find_iscc
set "ISCC="
for %%P in ("%ProgramFiles(x86)%" "%ProgramFiles%" "%LocalAppData%\Programs") do (
  for %%V in (7 6) do (
    if not defined ISCC if exist "%%~P\Inno Setup %%V\ISCC.exe" set "ISCC=%%~P\Inno Setup %%V\ISCC.exe"
  )
)
if not defined ISCC for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
if not defined ISCC (
  echo [X] Inno Setup is not installed. Download it from https://jrsoftware.org/isdl.php
)
exit /b 0

:error
echo.
echo [X] Build failed - send a screenshot of the messages above.
pause
exit /b 1
