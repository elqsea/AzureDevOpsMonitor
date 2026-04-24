@echo off
title ServiceNow - Obtener Cookies SSO
color 0B
echo Obteniendo cookies SSO de ServiceNow...
echo.
"%~dp0python\python.exe" "%~dp0get_snow_cookies.py"
echo.
pause
