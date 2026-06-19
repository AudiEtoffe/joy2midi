@echo off
cd /d "%~dp0"
py -3.12 make_icon.py
py -3.12 joy2midi.py
if errorlevel 1 python joy2midi.py
pause
