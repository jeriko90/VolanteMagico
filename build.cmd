@echo off
setlocal
echo Compilando Volante...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0source\build.ps1"
set "code=%ERRORLEVEL%"
echo.
if not "%code%"=="0" (
  echo FALLO el build. Codigo %code%. Revisa el mensaje de arriba.
) else (
  echo Build correcto. El .exe esta en dist\Volante.exe
)
echo.
pause
