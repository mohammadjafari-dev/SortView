@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title SortView - Build fully portable package
chcp 65001 >nul 2>&1

REM ============================================================================
REM  SortView - BUILD.bat
REM
REM  Builds a fully portable Windows package with PyInstaller:
REM
REM      dist\SortView\SortView.exe   (+ _internal runtime files)
REM      SortView-win64-portable.zip
REM
REM  End-user target: Windows 10/11 x64 with NOTHING installed.
REM  The package bundles Python runtime, PyQt6 (its Qt Multimedia engine plays
REM  video and audio), Pillow, PyMuPDF and ffmpeg.exe (video thumbnails).
REM
REM  Build-time requirements only:
REM    - Python 3.10+ x64 on PATH, or the "py" launcher
REM    - Internet the first time, for pip + the pinned ffmpeg download
REM
REM  Usage:
REM      BUILD.bat            -> one-dir portable build, recommended
REM      BUILD.bat /onefile   -> single exe build, slower startup
REM ============================================================================

set "APPNAME=SortView"
set "ENTRY=main.py"
set "VENV=.build-venv"
set "STAGING=build\_bin_staging"
set "MODE=--onedir"
if /i "%~1"=="/onefile" set "MODE=--onefile"

echo.
echo === [1/7] Finding Python 3.10+ x64 ===
set "PY="
set "PYVER=0"
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%V in ('python -c "import sys;print(sys.version_info.major*100+sys.version_info.minor)" 2^>nul') do set "PYVER=%%V"
)
if !PYVER! GEQ 310 (
    set "PY=python"
) else (
    py -3.13 -c "import sys" >nul 2>&1 && set "PY=py -3.13"
    if not defined PY py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
    if not defined PY py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11"
    if not defined PY py -3.10 -c "import sys" >nul 2>&1 && set "PY=py -3.10"
)
if not defined PY (
    echo [ERROR] Python 3.10+ not found. Install Python from https://www.python.org
    echo         End users do NOT need Python; this is only for building.
    pause
    exit /b 1
)
for /f "delims=" %%V in ('%PY% -c "import sys,platform;print(sys.version.split()[0], platform.architecture()[0])"') do echo Using Python %%V

echo.
echo === [2/7] Preparing clean build venv: %VENV% ===
if exist "%VENV%" rmdir /s /q "%VENV%"
%PY% -m venv "%VENV%" || (echo [ERROR] venv creation failed & pause & exit /b 1)
set "PYP=%VENV%\Scripts\python.exe"
"%PYP%" -m pip install --upgrade pip --quiet
if exist "requirements-lock.txt" (
    "%PYP%" -m pip install --quiet -r requirements-lock.txt
    if errorlevel 1 ( echo [ERROR] installing requirements-lock.txt failed & pause & exit /b 1 )
) else (
    "%PYP%" -m pip install --quiet -r requirements.txt
    if errorlevel 1 ( echo [ERROR] installing requirements.txt failed & pause & exit /b 1 )
)
"%PYP%" -m pip install --quiet "pyinstaller==6.22.3"
if errorlevel 1 ( echo [ERROR] installing PyInstaller failed & pause & exit /b 1 )
REM Built-in video playback needs PyQt6.QtMultimedia. Modern PyQt6 wheels
REM include it; very old ones do not. Verify and self-heal if possible.
"%PYP%" -c "import PyQt6.QtMultimedia" >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyQt6.QtMultimedia not importable - installing PyQt6-Multimedia wheel...
    "%PYP%" -m pip install --quiet PyQt6-Multimedia
    "%PYP%" -c "import PyQt6.QtMultimedia" >nul 2>&1
    if errorlevel 1 (
echo [WARN] Built-in video player unavailable - videos will show thumbnails
echo         but not play. Build with a current PyQt6 6.9 or newer.
    )
)
echo Build venv ready.

echo.
echo === [3/7] Generating icon build\icon.ico ===
if not exist build mkdir build
if exist "assets\icon.png" (
    "%PYP%" -c "from PIL import Image; im=Image.open('assets/icon.png').convert('RGBA'); im.save('build/icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    if errorlevel 1 ( echo [ERROR] icon generation failed & pause & exit /b 1 )
) else (
    echo [WARN] assets\icon.png not found. Building without custom icon.
)

echo.
echo === [4/7] Downloading/staging portable runtime tools ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_deps.ps1" -Staging "%STAGING%"
if errorlevel 1 (
    echo [ERROR] Runtime dependency staging failed.
    echo         Check your internet connection or the messages above.
    pause
    exit /b 1
)

echo.
echo === [5/7] Running PyInstaller %MODE% ===
set "ICON_ARG="
if exist "build\icon.ico" set "ICON_ARG=--icon build\icon.ico"

"%PYP%" -m PyInstaller --noconfirm --clean %MODE% --windowed ^
  --name %APPNAME% ^
  %ICON_ARG% ^
  --add-data "assets;assets" ^
  --add-data "%STAGING%;bin" ^
  --add-data "README.md;." ^
  --add-data "LICENSE;." ^
  --add-data "THIRD_PARTY_NOTICES.md;." ^
  --hidden-import pymupdf ^
  --hidden-import PyQt6.QtMultimedia ^
  --hidden-import PyQt6.QtMultimediaWidgets ^
  --hidden-import py7zr ^
  --hidden-import rarfile ^
  --collect-all PyQt6 ^
  --collect-all pymupdf ^
  --exclude-module PySide6 ^
  --exclude-module PyQt5 ^
  --exclude-module tkinter ^
  "%ENTRY%"
if errorlevel 1 ( echo [ERROR] PyInstaller failed. Scroll up for the reason. & pause & exit /b 1 )

if /i "%MODE%"=="--onedir" (
    echo.
    echo === Verifying bundled runtime files ===
    set "RUNDIR=dist\%APPNAME%\_internal\bin"
    if not exist "!RUNDIR!\ffmpeg.exe" ( echo [ERROR] Missing !RUNDIR!\ffmpeg.exe & pause & exit /b 1 )
    if not exist "!RUNDIR!\ffmpeg-LICENSE.txt" ( echo [ERROR] Missing !RUNDIR!\ffmpeg-LICENSE.txt & pause & exit /b 1 )
    if not exist "!RUNDIR!\ffmpeg-README.txt" ( echo [ERROR] Missing !RUNDIR!\ffmpeg-README.txt & pause & exit /b 1 )
    echo Runtime files verified.
)

echo.
echo === [6/7] Portable layout notes ===
if /i "%MODE%"=="--onefile" (
    echo One-file mode: dist\%APPNAME%.exe
    echo User data is created next to the exe in user_data\
) else (
    echo One-dir mode: dist\%APPNAME%\%APPNAME%.exe
    echo User data is created next to the exe in user_data\
)

echo.
echo === [7/7] Creating zip package ===
set "ZIPNAME=%APPNAME%-win64-portable.zip"
if exist "%ZIPNAME%" del /q "%ZIPNAME%"
if /i "%MODE%"=="--onefile" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\%APPNAME%.exe' -DestinationPath '%ZIPNAME%' -Force"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\%APPNAME%' -DestinationPath '%ZIPNAME%' -Force"
)
if errorlevel 1 (
    echo [WARN] PowerShell zip failed. You can zip dist manually.
) else (
    echo Created: %ZIPNAME%
    echo Writing SHA-256 checksum...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$h = (Get-FileHash '%ZIPNAME%' -Algorithm SHA256).Hash; Set-Content -Path '%ZIPNAME%.sha256' -Value \"$h  %ZIPNAME%\"; Write-Output $h"
    if exist "%ZIPNAME%.sha256" (
        echo Checksum written to: %ZIPNAME%.sha256
        echo Publish the zip and this .sha256 file together in a GitHub Release.
    ) else (
        echo [WARN] Could not write the checksum file.
    )
)

echo.
echo ============================================================================
echo DONE.
echo Distribute: %ZIPNAME%
echo Users unzip it and run SortView\SortView.exe
echo No Python, ffmpeg or codec-pack installation should be required on target PC.
echo To uninstall: delete the folder. App settings/cache are inside user_data\
echo ============================================================================
pause
endlocal
