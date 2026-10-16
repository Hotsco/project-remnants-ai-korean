@echo off
setlocal
set "PYTHONHOME="
set "PYTHONPATH="
"%~dp0runtime\python.exe" "%~dp0create_shortcut.py"
if errorlevel 1 pause
