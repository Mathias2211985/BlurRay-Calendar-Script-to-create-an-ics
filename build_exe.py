"""
Build-Script: Erzeugt eine standalone .exe aus der Web-UI.
Ausfuehren: python build_exe.py
Ergebnis: dist/BluRay-Calendar-Scraper.exe

Hinweis: Der Build-Ordner wird in %TEMP% angelegt, um Konflikte
mit OneDrive-Dateisperren zu vermeiden.
"""
import os
import sys
import tempfile
import PyInstaller.__main__

# Build-Verzeichnis in TEMP anlegen (OneDrive sperrt lokale build/-Ordner)
work_dir = os.path.join(tempfile.gettempdir(), "pyinstaller_bluray_build")
script_dir = os.path.dirname(os.path.abspath(__file__))
dist_dir = os.path.join(script_dir, "dist")

PyInstaller.__main__.run([
    "web_ui.py",
    "--onefile",
    "--name=BluRay-Calendar-Scraper",
    "--add-data=scraper.py;.",
    "--hidden-import=flask",
    "--hidden-import=icalendar",
    "--hidden-import=requests",
    "--hidden-import=bs4",
    "--console",
    "--noconfirm",
    "--clean",
    f"--workpath={work_dir}",
    f"--distpath={dist_dir}",
    f"--specpath={script_dir}",
])
