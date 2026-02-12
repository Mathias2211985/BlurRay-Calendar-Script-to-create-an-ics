@echo off
REM start_web.bat
REM Startet die BluRay Calendar Scraper Web-UI und oeffnet den Browser.
REM Doppelklick genuegt!

pushd "%~dp0"
pip install -r requirements.txt >nul 2>&1
python web_ui.py
popd
pause
