@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-media-maxing-vercel-local.ps1"
if errorlevel 1 (
  echo.
  echo Media Maxing local companion did not start successfully.
  echo Check data\logs\media-maxing-8000.err.log for details.
  pause
)
endlocal
