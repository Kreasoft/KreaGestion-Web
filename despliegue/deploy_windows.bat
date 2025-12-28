@echo off
REM ============================================
REM SCRIPT DE DESPLIEGUE PARA WINDOWS
REM GestionCloud - Sistema de Gestión
REM ============================================

setlocal enabledelayedexpansion

echo ============================================
echo DESPLIEGUE DE GestionCloud - WINDOWS
echo ============================================
echo.

REM Verificar que estamos en el directorio correcto
if not exist "manage.py" (
    echo ERROR: No se encuentra manage.py. Ejecuta este script desde la raiz del proyecto.
    pause
    exit /b 1
)

REM Activar entorno virtual
if exist ".venv\Scripts\activate.bat" (
    echo Activando entorno virtual...
    call .venv\Scripts\activate.bat
) else (
    echo ADVERTENCIA: No se encuentra el entorno virtual. Creando uno nuevo...
    python -m venv .venv
    call .venv\Scripts\activate.bat
)

REM Actualizar pip
echo.
echo Actualizando pip...
python -m pip install --upgrade pip

REM Instalar dependencias
echo.
echo Instalando dependencias...
pip install -r requirements.txt

REM Verificar archivo .env
if not exist ".env" (
    echo.
    echo ADVERTENCIA: No se encuentra archivo .env
    echo Copiando ejemplo de configuración...
    if exist "despliegue\.env.production.example" (
        copy "despliegue\.env.production.example" ".env"
        echo Por favor, edita el archivo .env con tus configuraciones antes de continuar.
        pause
        exit /b 1
    )
)

REM Aplicar migraciones
echo.
echo Aplicando migraciones de base de datos...
python manage.py migrate --no-input

REM Crear superusuario si no existe
echo.
echo Verificando superusuario...
python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(is_superuser=True).exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')" 2>nul
if errorlevel 1 (
    echo ADVERTENCIA: No se pudo crear superusuario automáticamente.
    echo Puedes crearlo manualmente con: python manage.py createsuperuser
)

REM Recolectar archivos estáticos
echo.
echo Recolectando archivos estáticos...
python manage.py collectstatic --no-input --clear

REM Verificar configuración
echo.
echo Verificando configuración de Django...
python manage.py check --deploy

echo.
echo ============================================
echo DESPLIEGUE COMPLETADO
echo ============================================
echo.
echo Para iniciar el servidor en modo desarrollo:
echo   python manage.py runserver
echo.
echo Para producción, configura un servidor WSGI como Gunicorn o IIS.
echo.
pause








