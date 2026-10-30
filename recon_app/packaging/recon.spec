# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — يبني مجلد البرنامج (onedir) بدون نافذة سوداء.
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = str(ROOT / "packaging" / "icon.ico") if sys.platform == "win32" else None

EXCLUDES = [
    "tkinter", "matplotlib", "scipy", "IPython", "pytest",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtLocation", "PySide6.QtNetworkAuth",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=["rapidfuzz", "rapidfuzz.fuzz", "xlsxwriter", "xlrd", "openpyxl", "pandas"],
    hookspath=[], runtime_hooks=[], excludes=EXCLUDES, noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="ReconPro", console=False, icon=ICON,
    debug=False, strip=False, upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ReconPro")
