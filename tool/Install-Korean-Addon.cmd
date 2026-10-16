@echo off
setlocal
chcp 65001 >nul
set "LUNA_PYTHON=%~dp0runtime\python.exe"
if not exist "%LUNA_PYTHON%" (
  echo Missing runtime\python.exe. Extract the complete tool folder and try again.
  pause
  exit /b 1
)
set "PYTHONHOME="
set "PYTHONPATH="
"%LUNA_PYTHON%" "%~dp0install_addon.py"
set "LUNA_EXIT=%ERRORLEVEL%"
pause
exit /b %LUNA_EXIT%
