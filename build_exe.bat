@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo joy2midi Windows EXE builder
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
    echo No supported Python launcher version found.
    echo Please install Python 3.12 64-bit from python.org.
    pause
    exit /b 1
)

echo Using Python:
%PYTHON_CMD% --version
if errorlevel 1 (
    echo Python check failed.
    pause
    exit /b 1
)

echo.
echo Removing old virtual environment if present...
if exist .venv rmdir /s /q .venv

echo.
echo Creating local virtual environment...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo.
echo Upgrading pip, setuptools, and wheel...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Failed to upgrade Python packaging tools.
    pause
    exit /b 1
)

echo.
echo Installing wheel-only dependencies...
python -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements as prebuilt wheels.
    echo Install Python 3.12 64-bit, delete .venv, then run this again.
    pause
    exit /b 1
)

echo.
echo Creating app icon files...
python make_icon.py
if errorlevel 1 (
    echo Icon generation failed.
    pause
    exit /b 1
)

echo.
echo Testing MIDI backend inside the virtual environment...
python -c "import mido, rtmidi, mido.backends.rtmidi; mido.set_backend('mido.backends.rtmidi'); print('MIDI outputs visible to Python:', mido.get_output_names())"
if errorlevel 1 (
    echo MIDI backend test failed before compiling.
    pause
    exit /b 1
)

echo.
echo Building joy2midi.exe...
python -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name joy2midi ^
    --icon=app_icon.ico ^
    --add-data "app_icon.ico;." ^
    --add-data "app_icon.png;." ^
    --runtime-hook=pyinstaller_runtime_hook.py ^
    --hidden-import=mido.backends.rtmidi ^
    --hidden-import=rtmidi ^
    --hidden-import=pystray._win32 ^
    --collect-submodules=mido.backends ^
    --collect-submodules=rtmidi ^
    --collect-submodules=pystray ^
    --collect-binaries=rtmidi ^
    joy2midi.py

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete.
echo EXE location: dist\joy2midi.exe
echo.
pause
