@echo off
setlocal
cd /d "%~dp0web"
if not exist node_modules\vite\bin\vite.js (
  call npm.cmd ci
  if errorlevel 1 exit /b 1
)
echo K:LINK HR portal: http://127.0.0.1:8825/hr
echo Checking the updated HR service on 127.0.0.1:8828.
python ..\scripts\launch_hr_domain.py --port 8828 --no-open
if errorlevel 1 exit /b 1
call npm.cmd run dev:hr
