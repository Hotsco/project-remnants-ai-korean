@echo off
setlocal
chcp 65001 >nul
set "LUNA_PYTHON=%~dp0runtime\python.exe"
if not exist "%LUNA_PYTHON%" (
  echo Missing runtime\python.exe. Extract the complete tool folder.
  pause
  exit /b 1
)
set "PYTHONHOME="
set "PYTHONPATH="
"%LUNA_PYTHON%" "%~dp0npc_settings.py" start
if errorlevel 1 pause
