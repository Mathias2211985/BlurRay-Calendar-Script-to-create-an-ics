@echo off
REM run_scraper_doubleclick.bat
REM Launches run_scraper.ps1 in a new PowerShell window so you can double-click this .bat
REM Keeps the window open after the script finishes so you can see prompts and output.

pushd "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0run_scraper.ps1"
popd
