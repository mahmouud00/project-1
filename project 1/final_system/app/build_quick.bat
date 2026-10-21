@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   SUITES - quick build (PyInstaller)
echo   (faster to build, but easier to decompile than build.bat)
echo ================================================

findstr /C:"PUT-YOUR" server\license_key.py >nul
if not errorlevel 1 (
  echo [X] Run the license key generator first:  python ..\license_tool\keygen.py
  goto :error
)

python -m pip install --upgrade -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto :error
for /f "delims=" %%v in ('python -c "import app_info; print(app_info.APP_VERSION)"') do set VER=%%v
python make_icon.py
if errorlevel 1 goto :error
python -m PyInstaller tailor.spec --noconfirm --clean
if errorlevel 1 goto :error

set "ISCC="
for %%P in ("%ProgramFiles(x86)%" "%ProgramFiles%" "%LocalAppData%\Programs") do (
  for %%V in (7 6) do (
    if not defined ISCC if exist "%%~P\Inno Setup %%V\ISCC.exe" set "ISCC=%%~P\Inno Setup %%V\ISCC.exe"
  )
)
if not defined ISCC for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
if not defined ISCC (
  echo [X] Inno Setup is not installed. Download it from https://jrsoftware.org/isdl.php
  goto :error
)
"%ISCC%" /DMyAppVersion=%VER% /DSourceDir=dist\SUITES installer.iss
if errorlevel 1 goto :error
echo [OK] Done! installer_output\SUITES_Setup_%VER%.exe
explorer installer_output
pause
exit /b 0

:error
echo [X] Build failed - send a screenshot of the messages above.
pause
exit /b 1
