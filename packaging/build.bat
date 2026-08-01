@echo off
setlocal
cd /d "%~dp0"

set PYTHON=%~dp0venv\Scripts\python.exe
set PYINSTALLER=%~dp0venv\Scripts\pyinstaller.exe
set SEVENZIP=D:\Program Files\7-Zip\7z.exe
set ISCC=F:\InnoSetup7\ISCC.exe
set APP_VERSION=0.1.0

if not exist "%PYTHON%" (
    echo [1/4] Creating venv...
    "D:\Program Files\Python312\python.exe" -m venv "%~dp0venv"
    "%PYTHON%" -m pip install -q pyinstaller "%~dp0.."
)

echo [2/4] Building with PyInstaller...
"%PYINSTALLER%" verba.spec --distpath dist --workpath work
if errorlevel 1 exit /b 1

echo [3/4] Packing portable zip...
"%SEVENZIP%" a -tzip -mx=9 "output\verba-%APP_VERSION%-win64.zip" "dist\Verba\*"
if errorlevel 1 exit /b 1

echo [4/4] Building installer...
"%ISCC%" verba.iss
if errorlevel 1 exit /b 1

echo.
echo Done: output\verba-%APP_VERSION%-win64.zip, output\verba-%APP_VERSION%-setup.exe
endlocal
