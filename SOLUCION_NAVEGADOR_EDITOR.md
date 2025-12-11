# 🔧 Solución: Navegador se abre dentro del editor

## Problema
El navegador se está ejecutando dentro del editor Cursor en lugar de abrirse en una ventana externa.

## Soluciones implementadas

### 1. Archivo de configuración `.vscode/settings.json`
Se creó un archivo de configuración que desactiva el navegador integrado y fuerza que las URLs se abran en el navegador externo del sistema.

### 2. Scripts para ejecutar el servidor

#### Opción A: Ejecutar sin abrir navegador automáticamente
```bash
runserver.bat
```
Este script ejecuta el servidor sin intentar abrir el navegador automáticamente. Luego puedes abrir manualmente `http://127.0.0.1:8000/` en tu navegador externo.

#### Opción B: Ejecutar y abrir navegador externo automáticamente
```bash
runserver_abrir.bat
```
Este script ejecuta el servidor y abre automáticamente el navegador externo del sistema (no el integrado).

### 3. Solución manual (si persiste el problema)

1. **Cerrar Cursor completamente** y volver a abrirlo para que los cambios de configuración surtan efecto.

2. **Verificar extensiones**: Si tienes alguna extensión de "Browser Preview" o "Simple Browser" instalada, desactívala temporalmente:
   - Ve a Extensiones (Ctrl+Shift+X)
   - Busca "Browser Preview" o "Simple Browser"
   - Desactívala o desinstálala

3. **Configuración global de Cursor**:
   - Presiona `Ctrl+,` para abrir configuración
   - Busca "simple browser" o "browser preview"
   - Desactiva cualquier opción relacionada

4. **Usar el navegador externo manualmente**:
   - Ejecuta el servidor con `runserver.bat`
   - Abre tu navegador (Chrome, Firefox, Edge, etc.)
   - Ve a `http://127.0.0.1:8000/`

## Verificación

Para verificar que funciona correctamente:

1. Ejecuta `runserver_abrir.bat`
2. Debería abrirse una ventana nueva de tu navegador predeterminado (Chrome, Firefox, Edge, etc.)
3. Si se abre dentro del editor, sigue los pasos de "Solución manual"

## Notas

- Los cambios en `.vscode/settings.json` solo afectan a este proyecto
- Si el problema persiste, puede ser una configuración global de Cursor
- Siempre puedes usar `runserver.bat` y abrir el navegador manualmente como solución alternativa


