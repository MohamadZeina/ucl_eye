@echo off
REM Molecular Plus Plus Installation Script for Blender 4.5 (Windows)
REM Usage: Run this script from the molecular-plus directory

setlocal

set ADDON_NAME=molecular_plus
set SOURCE_DIR=%~dp0
set BLENDER_ADDONS=%APPDATA%\Blender Foundation\Blender\4.5\scripts\addons
set BLENDER_SITE_PACKAGES=C:\Program Files\Blender Foundation\Blender 4.5\4.5\python\lib\site-packages

echo ========================================
echo Molecular Plus Plus Installer (Windows)
echo ========================================
echo.
echo Source directory: %SOURCE_DIR%
echo Addon destination: %BLENDER_ADDONS%\%ADDON_NAME%
echo Core module destination: %BLENDER_SITE_PACKAGES%\molecular_core
echo.

REM Check if Blender exists
if not exist "C:\Program Files\Blender Foundation\Blender 4.5" (
    echo ERROR: Blender 4.5 not found at C:\Program Files\Blender Foundation\Blender 4.5
    echo Please install Blender 4.5 or modify BLENDER_SITE_PACKAGES in this script.
    pause
    exit /b 1
)

REM Check if compiled core module exists
if not exist "%SOURCE_DIR%c_sources\molecular_core" (
    echo ERROR: Compiled core module not found at %SOURCE_DIR%c_sources\molecular_core
    echo.
    echo Please compile first:
    echo   1. Open "x64 Native Tools Command Prompt for VS 2022"
    echo   2. cd %SOURCE_DIR%c_sources
    echo   3. python setup.py build_ext --inplace
    pause
    exit /b 1
)

REM Create addon directory
echo Creating addon directory...
if not exist "%BLENDER_ADDONS%\%ADDON_NAME%" mkdir "%BLENDER_ADDONS%\%ADDON_NAME%"

REM Copy Python files
echo Copying Python addon files...
copy /Y "%SOURCE_DIR%*.py" "%BLENDER_ADDONS%\%ADDON_NAME%\" >nul

REM Copy compiled core module (may need admin rights)
echo Copying compiled core module...
echo NOTE: If this fails, run this script as Administrator
xcopy /E /I /Y "%SOURCE_DIR%c_sources\molecular_core" "%BLENDER_SITE_PACKAGES%\molecular_core\" >nul

if errorlevel 1 (
    echo.
    echo ERROR: Failed to copy core module. Try running as Administrator.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
echo Next steps:
echo 1. Open Blender 4.5
echo 2. Go to Edit ^> Preferences ^> Add-ons
echo 3. Search for "Molecular"
echo 4. Enable "Molecular Plus"
echo.
pause
