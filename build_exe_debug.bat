@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo joy2midi DEBUG Windows EXE builder
echo ========================================
echo.

set PYTHON_CMD=
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 --version >nul 2>nul
    if %errorlevel%==0 set PYTHON_CMD=py -3.12
    if not defined PYTHON_CMD (
        py -3.11 --version >nul 2>nul
        if %errorlevel%==0 set PYTHON_CMD=py -3.11
    )
    if not defined PYTHON_CMD (
        py -3.10 --version >nul 2>nul
        if %errorlevel%==0 set PYTHON_CMD=py -3.10
    )
)

if not defined PYTHON_CMD (
    echo Install Python 3.12 64-bit from python.org first.
    pause
    exit /b 1
)

if exist .venv rmdir /s /q .venv
%PYTHON_CMD% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install --only-binary=:all: -r requirements.txt

echo.
echo Python MIDI backend test:
python -c "import mido, rtmidi, mido.backends.rtmidi; mido.set_backend('mido.backends.rtmidi'); print('Backend:', mido.backend); print('Outputs:', mido.get_output_names())"

echo.
echo Building console/debug EXE...
python -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --console ^
    --name joy2midi_debug ^
    --runtime-hook=pyinstaller_runtime_hook.py ^
    --hidden-import=mido.backends.rtmidi ^
    --hidden-import=rtmidi ^
    --collect-submodules=mido.backends ^
    --collect-submodules=rtmidi ^
    --collect-binaries=rtmidi ^
    joy2midi.py

echo.
echo Debug EXE location: dist\joy2midi_debug.exe
echo Run it from this console to see MIDI backend errors.
echo.
pause
