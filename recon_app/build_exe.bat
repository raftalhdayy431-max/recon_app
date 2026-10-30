@echo off
chcp 65001 >nul
call .venv\Scripts\activate 2>nul || ( python -m venv .venv & call .venv\Scripts\activate )
pip install -q -r requirements.txt pyinstaller
pyinstaller --noconfirm --windowed --name "المطابقة_المالية" main.py
echo.
echo الملف التنفيذي في: dist\المطابقة_المالية\
pause
