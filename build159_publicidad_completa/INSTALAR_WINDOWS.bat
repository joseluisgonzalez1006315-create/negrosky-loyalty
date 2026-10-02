@echo off
setlocal
cd /d "%~dp0"
echo.
echo ==============================================
echo   NEGROSKY LOYALTY V3 BUILD 055 - INSTALACION
echo ==============================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python no esta instalado o el comando py no esta disponible.
  pause
  exit /b 1
)
if not exist "venv\Scripts\python.exe" (
  echo [1/2] Creando entorno virtual...
  py -m venv venv
  if errorlevel 1 goto :error
) else (
  echo [1/2] Entorno virtual existente.
)
echo [2/2] Instalando dependencias...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error
echo.
echo [OK] Instalacion completada.
echo Ahora abra ABRIR_NEGROSKY_CONTROL.vbs.
pause
exit /b 0
:error
echo.
echo [ERROR] La instalacion no pudo completarse.
pause
exit /b 1
