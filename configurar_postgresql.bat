@echo off
echo ========================================
echo Configuracion de PostgreSQL para GestionCloud
echo ========================================
echo.

echo Verificando si PostgreSQL esta instalado...
psql --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PostgreSQL no esta instalado o no esta en el PATH
    echo Por favor instala PostgreSQL desde: https://www.postgresql.org/download/windows/
    pause
    exit /b 1
)

echo PostgreSQL encontrado!
echo.

set /p DB_NAME="Nombre de la base de datos [gestioncloud]: "
if "%DB_NAME%"=="" set DB_NAME=gestioncloud

set /p DB_USER="Usuario de PostgreSQL [postgres]: "
if "%DB_USER%"=="" set DB_USER=postgres

set /p DB_PASSWORD="Contrasena de PostgreSQL: "
if "%DB_PASSWORD%"=="" (
    echo ERROR: Debes ingresar una contrasena
    pause
    exit /b 1
)

set /p DB_HOST="Host [localhost]: "
if "%DB_HOST%"=="" set DB_HOST=localhost

set /p DB_PORT="Puerto [5432]: "
if "%DB_PORT%"=="" set DB_PORT=5432

echo.
echo Creando archivo .env...
(
echo # Configuracion de Base de Datos PostgreSQL
echo DB_ENGINE=django.db.backends.postgresql
echo DB_NAME=%DB_NAME%
echo DB_USER=%DB_USER%
echo DB_PASSWORD=%DB_PASSWORD%
echo DB_HOST=%DB_HOST%
echo DB_PORT=%DB_PORT%
echo.
echo # Configuracion de Django
echo SECRET_KEY=django-insecure-change-me-in-production
echo DEBUG=True
) > .env

echo Archivo .env creado exitosamente!
echo.
echo Ahora necesitas crear la base de datos en PostgreSQL.
echo Ejecuta estos comandos en psql o pgAdmin:
echo.
echo CREATE DATABASE %DB_NAME% OWNER %DB_USER%;
echo GRANT ALL PRIVILEGES ON DATABASE %DB_NAME% TO %DB_USER%;
echo.
echo Luego ejecuta las migraciones:
echo python manage.py migrate
echo.
pause










