@echo off
REM ============================================
REM BluRay Calendar Scraper - EXE Build Script
REM ============================================
pushd "%~dp0"

echo [1/4] Beende laufende Instanzen...
taskkill /F /IM "BluRay-Calendar-Scraper.exe" >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/4] Raeume alte Build-Ordner auf...
if exist build (
    rmdir /s /q build >nul 2>&1
    if exist build (
        echo WARNUNG: build-Ordner konnte nicht geloescht werden.
        echo Bitte schliesse alle Programme die darauf zugreifen und versuche es erneut.
        pause
        exit /b 1
    )
)
if exist dist (
    rmdir /s /q dist >nul 2>&1
)

echo [3/4] Installiere Abhaengigkeiten...
pip install requests beautifulsoup4 icalendar flask pyinstaller
if errorlevel 1 (
    echo FEHLER: pip install fehlgeschlagen!
    pause
    exit /b 1
)

echo.
echo [4/4] Baue EXE mit PyInstaller...
pyinstaller --noconfirm BluRay-Calendar-Scraper.spec
if errorlevel 1 (
    echo FEHLER: PyInstaller Build fehlgeschlagen!
    pause
    exit /b 1
)

echo.
echo ============================================
echo FERTIG! Die EXE liegt in: dist\BluRay-Calendar-Scraper.exe
echo ============================================
popd
pause
