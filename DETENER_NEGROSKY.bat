@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$f='.negrosky-server.pid'; if(Test-Path $f){$idServidor=[int](Get-Content $f); Stop-Process -Id $idServidor -Force -ErrorAction SilentlyContinue; Remove-Item $f -Force; Write-Host '[OK] Servidor NEGROSKY detenido.' -ForegroundColor Green}else{Write-Host 'El servidor de esta version no estaba iniciado.' -ForegroundColor Yellow}"
pause

