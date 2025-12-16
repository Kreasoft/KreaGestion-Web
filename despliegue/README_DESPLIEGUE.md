# 🚀 Guía de Despliegue - GestionCloud

Esta guía te ayudará a desplegar GestionCloud en un servidor de producción.

## 📋 Requisitos Previos

### Servidor Linux (Ubuntu/Debian recomendado)
- Python 3.10 o superior
- PostgreSQL 12 o superior
- Nginx (opcional pero recomendado)
- Git

### Windows Server
- Python 3.10 o superior
- PostgreSQL 12 o superior
- IIS con módulo WSGI (opcional)

## 🔧 Instalación Paso a Paso

### 1. Preparar el Servidor

#### Linux
```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias del sistema
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx git

# Instalar PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### Windows
- Instalar Python desde [python.org](https://www.python.org/downloads/)
- Instalar PostgreSQL desde [postgresql.org](https://www.postgresql.org/download/windows/)
- Instalar Git desde [git-scm.com](https://git-scm.com/download/win)

### 2. Clonar el Repositorio

```bash
git clone https://github.com/Kreasoft/KreaGestion-Web.git
cd KreaGestion-Web
```

### 3. Configurar Base de Datos PostgreSQL

```bash
# Acceder a PostgreSQL
sudo -u postgres psql

# Crear base de datos y usuario
CREATE DATABASE gestioncloud_prod;
CREATE USER gestioncloud_user WITH PASSWORD 'tu-password-seguro';
ALTER ROLE gestioncloud_user SET client_encoding TO 'utf8';
ALTER ROLE gestioncloud_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE gestioncloud_user SET timezone TO 'America/Santiago';
GRANT ALL PRIVILEGES ON DATABASE gestioncloud_prod TO gestioncloud_user;
\q
```

### 4. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp despliegue/.env.production.example .env

# Editar con tus configuraciones
nano .env  # o usar tu editor preferido
```

**Configuraciones importantes:**
- `SECRET_KEY`: Genera una nueva clave secreta
- `DEBUG=False`: Siempre False en producción
- `ALLOWED_HOSTS`: Tu dominio o IP del servidor
- Configuración de base de datos PostgreSQL
- Credenciales del SII (si usas facturación electrónica)

### 5. Ejecutar Script de Despliegue

#### Linux
```bash
# Dar permisos de ejecución
chmod +x despliegue/deploy_linux.sh
chmod +x despliegue/start_gunicorn.sh

# Ejecutar despliegue
./despliegue/deploy_linux.sh
```

#### Windows
```cmd
despliegue\deploy_windows.bat
```

### 6. Configurar Nginx (Linux)

```bash
# Copiar configuración de ejemplo
sudo cp despliegue/nginx.conf.example /etc/nginx/sites-available/gestioncloud

# Editar configuración
sudo nano /etc/nginx/sites-available/gestioncloud
# Cambiar: tu-dominio.com por tu dominio real

# Crear enlace simbólico
sudo ln -s /etc/nginx/sites-available/gestioncloud /etc/nginx/sites-enabled/

# Verificar configuración
sudo nginx -t

# Recargar Nginx
sudo systemctl reload nginx
```

### 7. Configurar Gunicorn como Servicio (Linux)

```bash
# Editar el archivo de servicio
sudo nano despliegue/gestioncloud.service
# Cambiar las rutas por las rutas reales de tu proyecto

# Copiar a systemd
sudo cp despliegue/gestioncloud.service /etc/systemd/system/

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar y iniciar servicio
sudo systemctl enable gestioncloud
sudo systemctl start gestioncloud

# Verificar estado
sudo systemctl status gestioncloud
```

### 8. Configurar SSL con Let's Encrypt (Opcional pero Recomendado)

```bash
# Instalar Certbot
sudo apt install certbot python3-certbot-nginx

# Obtener certificado
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com

# Renovación automática (ya está configurada por defecto)
sudo certbot renew --dry-run
```

## 🔍 Verificación

### Verificar que el Servicio Está Corriendo

```bash
# Ver estado del servicio
sudo systemctl status gestioncloud

# Ver logs
sudo journalctl -u gestioncloud -f

# Ver logs de Gunicorn
tail -f /var/log/gestioncloud/gunicorn_error.log

# Ver logs de Nginx
tail -f /var/log/nginx/gestioncloud_error.log
```

### Acceder a la Aplicación

Abre tu navegador y visita:
- `http://tu-dominio.com` (o `https://` si configuraste SSL)
- Usuario por defecto: `admin`
- Contraseña por defecto: `admin123` (¡cámbiala inmediatamente!)

## 🔄 Actualización

Para actualizar la aplicación:

```bash
# Detener servicio
sudo systemctl stop gestioncloud

# Hacer backup de la base de datos
pg_dump -U gestioncloud_user gestioncloud_prod > backup_$(date +%Y%m%d).sql

# Actualizar código
git pull origin main

# Activar entorno virtual
source .venv/bin/activate

# Instalar nuevas dependencias
pip install -r requirements.txt

# Aplicar migraciones
python manage.py migrate

# Recolectar archivos estáticos
python manage.py collectstatic --no-input

# Reiniciar servicio
sudo systemctl start gestioncloud
```

## 🛠️ Mantenimiento

### Backup de Base de Datos

```bash
# Backup manual
pg_dump -U gestioncloud_user gestioncloud_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar backup
psql -U gestioncloud_user gestioncloud_prod < backup_20251212_120000.sql
```

### Limpiar Archivos Temporales

```bash
# Limpiar archivos estáticos antiguos
python manage.py collectstatic --clear --no-input

# Limpiar sesiones expiradas
python manage.py clearsessions
```

### Ver Logs

```bash
# Logs de aplicación
tail -f logs/gestioncloud.log

# Logs de Gunicorn
tail -f /var/log/gestioncloud/gunicorn_error.log

# Logs de Nginx
tail -f /var/log/nginx/gestioncloud_error.log
```

## ⚠️ Solución de Problemas

### El servicio no inicia
```bash
# Ver logs detallados
sudo journalctl -u gestioncloud -n 50

# Verificar permisos
ls -la /var/log/gestioncloud/
ls -la /var/run/gestioncloud/
```

### Error de conexión a base de datos
- Verificar que PostgreSQL esté corriendo: `sudo systemctl status postgresql`
- Verificar credenciales en `.env`
- Verificar que el usuario tenga permisos: `sudo -u postgres psql -c "\du"`

### Archivos estáticos no se cargan
- Verificar que `collectstatic` se ejecutó correctamente
- Verificar permisos: `chmod -R 755 staticfiles`
- Verificar configuración de Nginx para `/static/`

### Error 502 Bad Gateway
- Verificar que Gunicorn esté corriendo: `ps aux | grep gunicorn`
- Verificar que el puerto 8000 esté accesible
- Verificar configuración de proxy en Nginx

## 📞 Soporte

Para más información, consulta:
- Documentación del proyecto: `README.md`
- Logs de la aplicación: `logs/gestioncloud.log`
- Issues en GitHub: [Repositorio del proyecto]

## 🔒 Seguridad

**IMPORTANTE:** Antes de poner en producción:

1. ✅ Cambiar `SECRET_KEY` por una clave única y segura
2. ✅ Configurar `DEBUG=False`
3. ✅ Configurar `ALLOWED_HOSTS` correctamente
4. ✅ Cambiar contraseña del superusuario
5. ✅ Configurar SSL/HTTPS
6. ✅ Configurar firewall (solo puertos 80, 443, 22)
7. ✅ Hacer backups regulares de la base de datos
8. ✅ Mantener el sistema y dependencias actualizadas



