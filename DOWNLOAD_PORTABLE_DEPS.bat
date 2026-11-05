@echo off
setlocal
cd /d "%~dp0"
title SortView - Download portable dependencies
chcp 65001 >nul 2>&1

echo This downloads/copies the pinned portable runtime tool into the local bin\ folder:
echo   ffmpeg.exe (video thumbnails; its GPL license text ships next to it)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_deps.ps1" -Staging "bin"
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to download portable dependencies.
  pause
  exit /b 1
)
echo.
echo DONE. Portable dependencies are now in bin\.
echo You can now run BUILD.bat to create SortView-win64-portable.zip.
pause
endlocal
