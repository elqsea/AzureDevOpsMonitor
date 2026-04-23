@echo off
title Setup — Monitor en Vivo
color 0B

echo.
echo ====================================================
echo   Setup — Descargando Python portable
echo ====================================================
echo.

:: Si ya existe python portable, no hacer nada
if exist "%~dp0python\python.exe" (
    echo   Python portable ya instalado.
    for /f "delims=" %%v in ('"%~dp0python\python.exe" --version 2^>^&1') do echo   Version: %%v
    echo.
    echo   Listo para usar run_snow_monitor.bat
    goto :done
)

:: Verificar conexion a internet con PowerShell
powershell -Command "try { (New-Object Net.WebClient).DownloadString('https://www.python.org') | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Sin conexion a internet. Descarga manualmente:
    echo.
    echo   1. Ve a: https://www.python.org/downloads/windows/
    echo   2. Descarga "Windows embeddable package (64-bit)"
    echo      Ejemplo: python-3.12.9-embed-amd64.zip
    echo   3. Extrae el contenido en la carpeta: %~dp0python\
    echo.
    pause
    exit /b 1
)

:: Crear carpeta python\
if not exist "%~dp0python" mkdir "%~dp0python"

:: Descargar Python embebido con PowerShell
set PY_VER=3.12.9
set PY_ZIP=python-%PY_VER%-embed-amd64.zip
set PY_URL=https://www.python.org/ftp/python/%PY_VER%/%PY_ZIP%
set PY_TMP=%~dp0python\%PY_ZIP%

echo   Descargando Python %PY_VER% portable (~12 MB)...
echo   Fuente: %PY_URL%
echo.

powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_TMP%' }"
if errorlevel 1 (
    echo [ERROR] Fallo la descarga. Verifica tu conexion a internet.
    pause
    exit /b 1
)

:: Extraer ZIP
echo   Extrayendo...
powershell -Command "Expand-Archive -Path '%PY_TMP%' -DestinationPath '%~dp0python' -Force"
if errorlevel 1 (
    echo [ERROR] Fallo la extraccion del ZIP.
    pause
    exit /b 1
)

:: Limpiar ZIP
del "%PY_TMP%" >nul 2>&1

:: Verificar
if not exist "%~dp0python\python.exe" (
    echo [ERROR] python.exe no encontrado tras la extraccion.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('"%~dp0python\python.exe" --version 2^>^&1') do echo   Instalado: %%v
echo.
echo   Python portable listo en: %~dp0python\
echo.

:done
echo   Ejecuta run_snow_monitor.bat para iniciar el monitor.
echo.
pause
