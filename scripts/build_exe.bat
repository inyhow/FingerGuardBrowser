@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: Build script for FingerGuard Browser standalone Windows distribution.
:: Run this from the project root in a terminal with Git Bash / WSL paths.
::
:: Requirements (already present in the managed Python environment):
::   - Python 3.11+ with pywebview, selenium, undetected-chromedriver, loguru, ...
::   - PyInstaller

set "PYTHON=C:\Users\Administrator\.workbuddy\binaries\python\envs\fingerguard\Scripts\python.exe"
set "SPEC=FingerGuardBrowser.spec"
set "DIST=dist\FingerGuardBrowser"
set "OUTPUT=dist\FingerGuardBrowser-Windows"

echo [1/4] Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [2/4] Running test suite...
"%PYTHON%" -m pytest tests/ -q
if %errorlevel% neq 0 (
    echo Tests failed, aborting build.
    exit /b 1
)

echo [3/4] Building with PyInstaller...
"%PYTHON%" -m PyInstaller "%SPEC%" --noconfirm --clean
if %errorlevel% neq 0 (
    echo PyInstaller build failed.
    exit /b 1
)

echo [4/4] Packaging portable directory...
if exist "%OUTPUT%" rmdir /s /q "%OUTPUT%"
move "%DIST%" "%OUTPUT%"

:: Create a convenience launcher that hides the console window for end users.
(
echo @echo off
echo start "" "%%~dp0FingerGuardBrowser.exe"
) > "%OUTPUT%\FingerGuardBrowser-quiet.bat"

echo Build complete: %OUTPUT%
echo To create an installer, run scripts\build_installer.iss with Inno Setup.
