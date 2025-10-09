@echo off
REM Activa el entorno virtual del proyecto (.venv, venv o env)
REM Ubicacion: raiz del proyecto

set "ROOT=%~dp0"

if exist "%ROOT%.venv\Scripts\activate.bat" (
  echo Activando entorno virtual: .venv
  cmd /k "%ROOT%.venv\Scripts\activate.bat"
  goto :eof
)

if exist "%ROOT%venv\Scripts\activate.bat" (
  echo Activando entorno virtual: venv
  cmd /k "%ROOT%venv\Scripts\activate.bat"
  goto :eof
)

if exist "%ROOT%env\Scripts\activate.bat" (
  echo Activando entorno virtual: env
  cmd /k "%ROOT%env\Scripts\activate.bat"
  goto :eof
)

echo No se encontro un entorno virtual en: .venv, venv o env
echo Para crearlo, ejecute:
echo    python -m venv .venv
pause
