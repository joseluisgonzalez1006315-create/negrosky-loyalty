@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (python APLICAR_SIN_SUCURSAL.py) else (py -3 APLICAR_SIN_SUCURSAL.py)
pause
