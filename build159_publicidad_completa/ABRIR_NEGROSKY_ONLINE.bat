@echo off
cd /d "%~dp0"
title NEGROSKY - Acceso online beta

echo.
echo ================================================
echo       NEGROSKY - TUNEL ONLINE GRATUITO
echo ================================================
echo.
echo Verifica que NEGROSKY este iniciado en el puerto 8030.
echo La URL publica aparecera debajo y cambiara cada vez.
echo No cierres esta ventana mientras uses el enlace.
echo.

where cloudflared.exe >nul 2>nul
if %errorlevel%==0 (
  cloudflared.exe tunnel --url http://127.0.0.1:8030
  pause
  exit /b
)

if exist "%~dp0cloudflared.exe" (
  "%~dp0cloudflared.exe" tunnel --url http://127.0.0.1:8030
  pause
  exit /b
)

echo No se encontro cloudflared.exe.
echo.
echo Descargalo desde:
echo https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/
echo Guarda cloudflared.exe en esta misma carpeta y vuelve a ejecutar este archivo.
echo.
pause
