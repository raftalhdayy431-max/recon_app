@echo off
setlocal
cd /d "%~dp0.."

echo [1/4] Preparing environment...
if not exist .venv ( python -m venv .venv )
if not exist .venv\Scripts\activate.bat (
  echo Python was not found. Install Python 3.11 or 3.12 from python.org and tick "Add Python to PATH".
  goto :err
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :err
python -m pip install -r requirements.txt pyinstaller pillow
if errorlevel 1 goto :err

echo [2/4] Generating icon...
python packaging\make_icon.py
if errorlevel 1 goto :err

echo [3/4] Building the program (a few minutes)...
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\recon.spec
if errorlevel 1 goto :err

echo [4/4] Creating the installer...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if defined ISCC goto :inno
echo.
echo DONE. The program was built in dist\ReconPro\  (run ReconPro.exe directly).
echo To also create a setup file, install Inno Setup 6 from https://jrsoftware.org/isdl.php and run this file again.
goto :end

:inno
"%ISCC%" packaging\installer.iss
if errorlevel 1 goto :err
echo.
echo DONE. Installer: dist_installer\ReconPro-Setup-1.0.0.exe
goto :end

:err
echo.
echo BUILD FAILED - see the messages above.
pause
exit /b 1

:end
pause
exit /b 0
