@echo off
setlocal
set "PYTHONHOME="
set "PYTHONPATH="
"%~dp0runtime\python.exe" "%~dp0configure_paths.py"
pause
