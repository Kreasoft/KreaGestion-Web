@echo off
echo ======================================================
echo   INICIANDO GESTION-CLOUD PARA EL CELULAR
echo ======================================================
echo.

echo 1. Verificando entorno virtual...
if exist ".venv\Scripts\activate.bat" (
    echo [OK] Activando .venv...
    call ".venv\Scripts\activate.bat"
) else (
    if exist "venv\Scripts\activate.bat" (
        echo [OK] Activando venv...
        call "venv\Scripts\activate.bat"
    )
)

echo.
echo 2. Iniciando servidor...
echo.
echo ------------------------------------------------------
echo    TU IP ES: 192.168.1.2
echo    DESDE EL CELULAR ENTRA A: http://192.168.1.2:8000/ventas/movil/
echo ------------------------------------------------------
echo.

python manage.py runserver 0.0.0.0:8000

echo.
echo El servidor se ha detenido.
pause

