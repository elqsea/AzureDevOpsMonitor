@echo off
title Azure DevOps Monitor - Ejecucion unica
color 0A
echo Ejecutando una sola vez...
echo.
pip install -r "%~dp0requirements.txt" -q
python -c "import monitor_devops; monitor_devops.run_once()"
echo.
echo Listo. Abre output\dashboard.html en tu navegador.
pause
