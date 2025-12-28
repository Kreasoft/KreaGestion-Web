# 📦 Carpeta de Despliegue - GestionCloud

Esta carpeta contiene todos los archivos necesarios para desplegar GestionCloud en producción.

## 📁 Estructura de Archivos

### 📖 Documentación
- **`README_DESPLIEGUE.md`** - Guía completa paso a paso para desplegar la aplicación
- **`INDICE.md`** - Este archivo, índice de contenidos

### ⚙️ Configuración
- **`.env.production.example`** - Archivo de ejemplo con todas las variables de entorno necesarias
- **`gunicorn_config.py`** - Configuración de Gunicorn (servidor WSGI)
- **`nginx.conf.example`** - Configuración de ejemplo para Nginx (servidor web)
- **`gestioncloud.service`** - Archivo de servicio systemd para Linux
- **`requirements_production.txt`** - Dependencias optimizadas para producción

### 🚀 Scripts de Despliegue
- **`deploy_linux.sh`** - Script automatizado de despliegue para Linux/Ubuntu
- **`deploy_windows.bat`** - Script automatizado de despliegue para Windows Server
- **`start_gunicorn.sh`** - Script para iniciar Gunicorn manualmente

### 🔄 Scripts de Mantenimiento
- **`update.sh`** - Script para actualizar la aplicación (pull, migraciones, etc.)
- **`backup_database.sh`** - Script para hacer backup de la base de datos
- **`restore_database.sh`** - Script para restaurar un backup de la base de datos

## 🚀 Inicio Rápido

### Linux/Ubuntu
```bash
# 1. Dar permisos de ejecución
chmod +x despliegue/*.sh

# 2. Ejecutar despliegue
./despliegue/deploy_linux.sh

# 3. Configurar Nginx
sudo cp despliegue/nginx.conf.example /etc/nginx/sites-available/gestioncloud
sudo ln -s /etc/nginx/sites-available/gestioncloud /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 4. Configurar como servicio
sudo cp despliegue/gestioncloud.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gestioncloud
sudo systemctl start gestioncloud
```

### Windows Server
```cmd
REM Ejecutar script de despliegue
despliegue\deploy_windows.bat

REM Configurar IIS con módulo WSGI según documentación
```

## 📋 Checklist de Despliegue

Antes de poner en producción, asegúrate de:

- [ ] Configurar archivo `.env` con valores de producción
- [ ] Cambiar `SECRET_KEY` por una clave única y segura
- [ ] Configurar `DEBUG=False`
- [ ] Configurar `ALLOWED_HOSTS` con tu dominio/IP
- [ ] Configurar base de datos PostgreSQL
- [ ] Ejecutar migraciones: `python manage.py migrate`
- [ ] Recolectar archivos estáticos: `python manage.py collectstatic`
- [ ] Crear superusuario: `python manage.py createsuperuser`
- [ ] Configurar Nginx (Linux) o IIS (Windows)
- [ ] Configurar SSL/HTTPS (recomendado)
- [ ] Configurar firewall
- [ ] Configurar backups automáticos
- [ ] Probar acceso a la aplicación

## 🔧 Configuración de Variables de Entorno

Copia el archivo de ejemplo y edítalo:
```bash
cp despliegue/.env.production.example .env
nano .env  # o tu editor preferido
```

Variables críticas a configurar:
- `SECRET_KEY` - Clave secreta de Django
- `DEBUG=False` - Siempre False en producción
- `ALLOWED_HOSTS` - Tu dominio o IP
- `DB_*` - Configuración de PostgreSQL
- `SII_*` - Credenciales de facturación electrónica (si aplica)

## 📚 Más Información

Para instrucciones detalladas, consulta:
- **`README_DESPLIEGUE.md`** - Guía completa de despliegue
- **`README.md`** - Documentación general del proyecto

## 🆘 Soporte

Si encuentras problemas durante el despliegue:
1. Revisa los logs: `logs/gestioncloud.log`
2. Verifica la configuración: `python manage.py check --deploy`
3. Consulta la sección de solución de problemas en `README_DESPLIEGUE.md`








