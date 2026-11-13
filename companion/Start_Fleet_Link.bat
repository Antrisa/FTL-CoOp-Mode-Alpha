@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 fleet_link.py
) else (
  python fleet_link.py
)
if errorlevel 1 (
  echo.
  echo Python 3.10+ was not found, or the utility exited with an error.
  echo Install Python 3 from python.org and enable the py launcher.
  pause
)
