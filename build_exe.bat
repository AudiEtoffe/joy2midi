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
    echo.
    echo Please install Python 3.12 64-bit from python.org.
    echo During install, check "Add python.exe to PATH".
    echo.
    echo This project intentionally avoids Python 3.13+ for now because some
    echo Windows MIDI/gamepad dependencies may try to compile from source.
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
echo This prevents pygame from trying to compile from source.
python -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 (
    echo.
    echo Failed to install requirements as prebuilt wheels.
    echo.
    echo Most likely fix:
    echo   1. Install Python 3.12 64-bit from python.org
    echo   2. Delete the .venv folder if it exists
    echo   3. Run build_exe.bat again
    echo.
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
echo Building joy2midi.exe with explicit RtMidi backend packaging...
python -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name joy2midi ^
    --runtime-hook=pyinstaller_runtime_hook.py ^
    --hidden-import=mido.backends.rtmidi ^
    --hidden-import=rtmidi ^
    --collect-submodules=mido.backends ^
    --collect-submodules=rtmidi ^
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
echo If the Python backend test saw MIDI ports but the EXE still does not,
echo try build_exe_debug.bat so the console can show the backend error.
echo.
pause
