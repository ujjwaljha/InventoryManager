@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 scripts\launch.py
  if errorlevel 1 pause
  exit /b %errorlevel%
)

where python >nul 2>&1
if %errorlevel%==0 (
  python scripts\launch.py
  if errorlevel 1 pause
  exit /b %errorlevel%
)

echo.
echo Install Python 3 from https://www.python.org/downloads/
echo On the installer, tick "Add python.exe to PATH".
echo Then double-click this file again.
echo.
echo Pasang Python 3 dari python.org, centang "Add python.exe to PATH",
echo lalu klik dua kali berkas ini lagi.
echo.
pause
start https://www.python.org/downloads/
exit /b 1
