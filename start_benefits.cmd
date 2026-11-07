@echo off
cd /d "%~dp0"
python scripts\launch_benefits_demo.py
if errorlevel 1 pause
