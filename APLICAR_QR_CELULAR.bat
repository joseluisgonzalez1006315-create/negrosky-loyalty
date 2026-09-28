@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (python APLICAR_QR_CELULAR.py) else (py -3 APLICAR_QR_CELULAR.py)
pause
