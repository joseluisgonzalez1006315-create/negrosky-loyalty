@echo off
cd /d "%~dp0"
echo.
echo Cierra primero NEGROSKY si esta abierto.
pause
if exist "%~dp0venv\Scripts\python.exe" (
  "%~dp0venv\Scripts\python.exe" -m app.reset_admin
) else (
  python -m app.reset_admin
)
echo.
echo Usuario: admin
echo Contraseña: ChangeMe123!
pause
