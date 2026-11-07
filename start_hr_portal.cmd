@echo off
setlocal
cd /d "%~dp0web"
if not exist node_modules\vite\bin\vite.js (
  call npm.cmd ci
  if errorlevel 1 exit /b 1
)
echo K:LINK HR portal: http://127.0.0.1:8825/hr
echo Checking the local query encoder and HR service on 127.0.0.1:8833.
python ..\scripts\launch_hr_vector_chat.py
if errorlevel 1 exit /b 1
call npm.cmd run dev:hr
