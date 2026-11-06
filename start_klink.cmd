@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "scripts\launch_local_demo.py"
) else (
  python "scripts\launch_local_demo.py"
)
if errorlevel 1 (
  echo.
  echo The original RAG app did not start. Check .demo-logs in this directory.
  echo You can run: py scripts\launch_local_demo.py --inspect-only
  pause
  exit /b 1
)
echo.
echo K-LINK demo window was requested from your default browser.
echo Keep the demo servers running. Press any key to close this launcher window.
pause >nul
