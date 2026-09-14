@echo off
rem ============================================================
rem  Build Windows desktop app - MUST run ON a Windows PC.
rem  Output: dist\SlopeAnalysis\SlopeAnalysis.exe
rem  Ship it: zip the whole dist\SlopeAnalysis folder.
rem  End users unzip and double-click the exe - no Python needed.
rem ============================================================
setlocal
cd /d "%~dp0"

rem ---- Build machine needs 64-bit Python 3.10-3.12 ----
where py >nul 2>nul
if %errorlevel%==0 (set PYCMD=py -3) else (set PYCMD=python)
%PYCMD% --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install 64-bit Python 3.10-3.12,
  echo         check "Add Python to PATH" during setup, then rerun this script:
  echo         https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

echo [1/3] Creating venv and installing dependencies - first run takes 2-5 min...
if not exist .venv (
  %PYCMD% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt pywebview pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
  echo [ERROR] Dependency install failed. Check network and rerun.
  pause
  exit /b 1
)

echo [2/3] Running PyInstaller - about 1-3 min...
".venv\Scripts\pyinstaller.exe" desktop.py --name SlopeAnalysis --windowed --onedir --add-data "static;static" --collect-submodules rasterio --collect-all certifi --exclude-module tkinter --icon icon.ico
if errorlevel 1 (
  echo [ERROR] PyInstaller build failed.
  pause
  exit /b 1
)

echo [3/3] Build finished.
echo.
echo   Output folder : dist\SlopeAnalysis
echo   Main program  : dist\SlopeAnalysis\SlopeAnalysis.exe
echo   How to ship   : zip the whole dist\SlopeAnalysis folder and send it.
echo.
echo   First-run notes for end users:
echo   - SmartScreen may warn "Windows protected your PC" because the exe is
echo     unsigned. Click "More info" then "Run anyway".
echo   - If the window shows up blank, install Microsoft WebView2 Runtime once:
echo     https://developer.microsoft.com/microsoft-edge/webview2/
echo   - The first analysis of a new area downloads DEM tiles - about 20-50 MB
echo     each - into the user data folder under LOCALAPPDATA. Downloaded once,
echo     reused for every later run of the same area.
echo.
pause
