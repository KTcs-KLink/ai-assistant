@echo off
cd /d "%~dp0"
python scripts\launch_uiux_preview.py
if errorlevel 1 pause
