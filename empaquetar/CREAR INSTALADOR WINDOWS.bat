@echo off
rem Crea en CATAGOLO COMPLETO\INSTALADOR:
rem   - Instalar Catalogo Cinema (Windows) X.exe
rem Requisitos: Python con PySide6, PySide6-Fluent-Widgets, Pillow y PyInstaller.
rem El instalador es propio (igual que el de Comprobantes): windows\instalador_windows.cs, se compila con el
rem csc.exe de .NET Framework que ya trae Windows.
cd /d "%~dp0"
set "SALIDA=..\..\INSTALADOR"

echo [1/2] Empaquetando el programa...
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build catalogo.spec || goto error

echo [2/2] Creando el instalador...
set "PS=powershell"
where pwsh >nul 2>nul && set "PS=pwsh"
%PS% -NoProfile -ExecutionPolicy Bypass -File "windows\construir_instalador.ps1" -Dist "dist\Catalogo Cinema" -Salida "%SALIDA%" || goto error

rd /s /q build dist 2>nul
echo.
echo Listo: el instalador quedo en CATAGOLO COMPLETO\INSTALADOR.
if not "%1"=="/sinpausa" pause
exit /b 0

:error
echo.
echo *** Hubo un error. Revisa los mensajes de arriba. ***
if not "%1"=="/sinpausa" pause
exit /b 1
