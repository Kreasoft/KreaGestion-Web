# 🚀 Cómo Ejecutar el Servidor Django (Fuera del Editor)

## ⚠️ IMPORTANTE: El servidor NO se ejecuta automáticamente

Para evitar que la aplicación se ejecute dentro del editor Cursor, el servidor debe iniciarse manualmente desde una terminal externa.

## 📋 Opciones para Ejecutar el Servidor

### Opción 1: Usar los Scripts Batch (Recomendado)

#### Ejecutar sin abrir navegador automáticamente:
```bash
runserver.bat
```
- Ejecuta el servidor en una ventana de terminal externa
- NO abre el navegador automáticamente
- Debes abrir manualmente `http://127.0.0.1:8000/` en tu navegador

#### Ejecutar y abrir navegador externo:
```bash
runserver_abrir.bat
```
- Ejecuta el servidor en una ventana de terminal externa
- Abre automáticamente el navegador externo del sistema

### Opción 2: Ejecutar Manualmente desde PowerShell/CMD

1. **Abre PowerShell o CMD** (fuera del editor Cursor)
2. **Navega al proyecto:**
   ```powershell
   cd C:\PROJECTOS-WEB\GestionCloud
   ```
3. **Activa el entorno virtual:**
   ```powershell
   .venv\Scripts\activate
   ```
4. **Ejecuta el servidor:**
   ```powershell
   python manage.py runserver
   ```
5. **Abre tu navegador** y ve a: `http://127.0.0.1:8000/`

## 🔧 Configuración Aplicada

Se ha configurado `.vscode/settings.json` para:
- ✅ Desactivar el navegador integrado (Simple Browser)
- ✅ Desactivar ejecución automática de tareas
- ✅ Desactivar ejecución automática de debug/launch
- ✅ Forzar que las URLs se abran en navegador externo

## 🛑 Si el Servidor se Ejecuta Automáticamente

Si aún se ejecuta automáticamente dentro del editor:

1. **Cierra Cursor completamente** y vuelve a abrirlo
2. **Verifica extensiones:**
   - Ve a Extensiones (Ctrl+Shift+X)
   - Busca "Browser Preview", "Simple Browser" o "Live Server"
   - Desactívalas o desinstálalas
3. **Verifica configuración global:**
   - Presiona `Ctrl+,` para abrir configuración
   - Busca "simple browser" o "browser preview"
   - Desactiva cualquier opción relacionada

## 📝 Notas

- El servidor debe ejecutarse en una terminal externa para evitar problemas
- Los cambios en `.vscode/settings.json` solo afectan a este proyecto
- Siempre puedes usar `runserver.bat` como solución más simple








