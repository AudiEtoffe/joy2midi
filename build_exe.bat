@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo joy2midi Windows EXE builder
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set PYTHON_CMD=py -3
) else (
    set PYTHON_CMD=python
)

echo Checking Python...
%PYTHON_CMD% --version
if errorlevel 1 (
    echo.
    echo Python was not found. Install Python 3.10 or newer from python.org.
    echo Make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

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
echo Installing joy2midi dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo Building joy2midi.exe...
python -m PyInstaller --clean --noconfirm --onefile --windowed --name joy2midi joy2midi.py
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
