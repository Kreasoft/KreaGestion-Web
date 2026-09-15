@echo off
echo ============================================
echo Iniciando GestionCloud desde entorno virtual (.venv)
echo ============================================
echo.
call .venv\Scripts\activate.bat
python manage.py runserver 8001
pause
