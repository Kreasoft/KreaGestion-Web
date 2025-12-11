@echo off
REM Script para ejecutar el servidor Django y abrir navegador externo

echo Activando entorno virtual...
call .venv\Scripts\activate.bat

echo.
echo ========================================
echo   Iniciando servidor Django
echo ========================================
echo.

REM Configurar para usar navegador del sistema (no integrado)
set BROWSER=start

REM Esperar un momento para que el servidor inicie
start /B python manage.py runserver --noreload

REM Esperar 3 segundos para que el servidor esté listo
timeout /t 3 /nobreak >nul

REM Abrir navegador externo
start http://127.0.0.1:8000/

echo Servidor iniciado en: http://127.0.0.1:8000/
echo Navegador abierto en ventana externa.
echo.
echo Presiona Ctrl+C para detener el servidor.
echo.

REM Mantener la ventana abierta
python manage.py runserver --noreload

pause


