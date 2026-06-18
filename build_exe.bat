@echo off
cd /d "%~dp0"
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name joy2midi joy2midi.py
echo.
echo Build complete. Check the dist folder.
pause
