@echo off
title Azure DevOps Monitor
color 0B
echo ================================================
echo   Azure DevOps Monitor
echo ================================================
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python desde python.org
    pause
    exit /b 1
)

:: Instalar dependencias si faltan
echo Verificando dependencias...
pip install -r "%~dp0requirements.txt" -q

echo.
echo Iniciando monitor...
echo Presiona Ctrl+C para detener.
echo.

python "%~dp0monitor_devops.py"
pause
