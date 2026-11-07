@echo off
setlocal
cd /d "%~dp0web"
if not exist node_modules\vite\bin\vite.js (
  call npm.cmd ci
  if errorlevel 1 exit /b 1
)
echo K:LINK alternative preview: http://127.0.0.1:8824/workspace
call npm.cmd run dev:alternative
