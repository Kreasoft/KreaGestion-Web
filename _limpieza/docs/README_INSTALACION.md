# Instalación y Configuración - GestionCloud

## 🚀 Inicio Rápido

### 1. Activar el Entorno Virtual
```bash
# Opción 1: Usar el script de activación (Windows)
activar

# Opción 2: Usar el script de PowerShell (Windows)
.\activa

# Opción 3: Activar manualmente
.venv\Scripts\activate
```

### 2. Verificar Instalación
```bash
# Verificar que Django funciona
python manage.py check

# Verificar dependencias
pip list

# Verificar versión de Django
python -c "import django; print('Django version:', django.__version__)"
```

### 3. Ejecutar el Servidor
```bash
# Iniciar servidor de desarrollo
python manage.py runserver

# El servidor estará disponible en: http://127.0.0.1:8000/
```

## 🔄 Solución de Problemas

### Si encuentras el error: "ModuleNotFoundError: No module named 'django.utils.version'"
```bash
# 1. Desactivar el entorno virtual actual
deactivate

# 2. Recrear el entorno virtual
python -m venv .venv

# 3. Instalar dependencias
.venv\Scripts\activate
pip install -r requirements.txt

# 4. Verificar que funciona
python manage.py check
```

## 📋 Dependencias Instaladas

✅ **Django 5.2.7** - Framework web
✅ **PostgreSQL/MySQL/SQLite** - Bases de datos
✅ **Facturación Electrónica** - Módulo SII completo
✅ **REST Framework** - API REST
✅ **Crispy Forms** - Formularios mejorados
✅ **ReportLab** - Generación de PDFs
✅ **Pandas/OpenPyXL** - Procesamiento de datos
✅ **Celery/Redis** - Tareas en segundo plano

## 🔧 Comandos Útiles

```bash
# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Recopilar archivos estáticos
python manage.py collectstatic

# Ejecutar comandos de gestión
python manage.py [comando]
```

## ⚠️ Advertencias

- Solo hay advertencias menores de seguridad (normal en desarrollo)
- Template tags duplicados (`format_filters`) - no afecta funcionalidad
- Configurar variables de entorno para producción

## 🐛 Solución de Problemas

Si encuentras errores:

1. **Verificar entorno virtual**: Asegúrate de que esté activado
2. **Actualizar dependencias**: `pip install -r requirements.txt`
3. **Verificar configuración**: `python manage.py check`
4. **Limpiar cache**: Eliminar archivos `__pycache__` si es necesario

## 📞 Soporte

El proyecto está completamente funcional y listo para usar.
