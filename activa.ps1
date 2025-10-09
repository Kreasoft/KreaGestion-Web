# Activa el entorno virtual del proyecto (.venv, venv o env)
# Ubicacion: raiz del proyecto

$ROOT = $PSScriptRoot

$venvPaths = @('.venv', 'venv', 'env')

foreach ($venvName in $venvPaths) {
    $activatePath = Join-Path $ROOT "$venvName\Scripts\Activate.ps1"
    
    if (Test-Path $activatePath) {
        Write-Host "Activando entorno virtual: $venvName" -ForegroundColor Green
        & $activatePath
        return
    }
}

Write-Host "No se encontro un entorno virtual en: .venv, venv o env" -ForegroundColor Yellow
Write-Host "Para crearlo, ejecute:" -ForegroundColor Yellow
Write-Host "   python -m venv .venv" -ForegroundColor Cyan
