Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Iniciando GestionCloud desde entorno virtual (.venv)" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
& ".\.venv\Scripts\python.exe" manage.py runserver 8001
