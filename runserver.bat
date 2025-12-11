@echo off
REM Script para ejecutar el servidor Django sin abrir navegador automáticamente
REM Esto fuerza que el navegador se abra fuera del editor

echo Activando entorno virtual...
call .venv\Scripts\activate.bat

echo.
echo ========================================
echo   Iniciando servidor Django
echo ========================================
echo.
echo El servidor se iniciará en: http://127.0.0.1:8000/
echo.
echo Para abrir en tu navegador externo, presiona Ctrl+C y luego abre:
echo http://127.0.0.1:8000/
echo.
echo ========================================
echo.

REM Desactivar la apertura automática del navegador en Django
set DJANGO_AUTO_BROWSER=0
set BROWSER=

REM Ejecutar servidor sin abrir navegador automáticamente
python manage.py runserver --noreload

pause


