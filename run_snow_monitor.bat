@echo off
title Monitor en Vivo — ServiceNow
color 0E

echo.
echo ====================================================
echo   ServiceNow Monitor en Vivo
echo ====================================================
echo.

:: 1. Python portable local
if exist "%~dp0python\python.exe" (
    set PYTHON_CMD=%~dp0python\python.exe
    goto :found_python
)

:: 2. Python del sistema
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python & goto :found_python )

py --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=py & goto :found_python )

python3 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=python3 & goto :found_python )

echo [ERROR] Python no encontrado.
echo   Ejecuta primero: setup.bat
echo.
pause
exit /b 1

:found_python
for /f "delims=" %%v in ('"%PYTHON_CMD%" --version 2^>^&1') do echo   Python: %%v
echo.

:: Leer puerto desde config.json via archivo temporal
"%PYTHON_CMD%" -c "import json; d=json.load(open('config.json')); print(d.get('servicenow',{}).get('server_port',8765))" > "%TEMP%\snow_port.tmp" 2>nul
set PORT=8765
if exist "%TEMP%\snow_port.tmp" (
    set /p PORT=<"%TEMP%\snow_port.tmp"
    del "%TEMP%\snow_port.tmp" >nul 2>&1
)

echo   Dashboard  : http://localhost:%PORT%
echo   Datos SNOW : http://localhost:%PORT%/snow
echo.
echo   Abriendo navegador en 3 segundos...
timeout /t 3 /nobreak >nul
start "" "http://localhost:%PORT%"

echo.
echo   Presiona Ctrl+C para detener.
echo.

"%PYTHON_CMD%" "%~dp0snow_monitor.py"
pause
