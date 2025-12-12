# Configuración de PostgreSQL para GestionCloud

## Pasos para configurar PostgreSQL

### 1. Instalar PostgreSQL

Si no tienes PostgreSQL instalado, descárgalo desde: https://www.postgresql.org/download/windows/

### 2. Crear la base de datos

Abre una terminal de PostgreSQL (psql) o usa pgAdmin y ejecuta:

```sql
-- Crear usuario (si no existe)
CREATE USER postgres WITH PASSWORD 'postgres';

-- Crear base de datos
CREATE DATABASE gestioncloud OWNER postgres;

-- Otorgar privilegios
GRANT ALL PRIVILEGES ON DATABASE gestioncloud TO postgres;
```

### 3. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto (copia `.env.example`):

```bash
# Windows PowerShell
Copy-Item .env.example .env
```

Luego edita el archivo `.env` con tus credenciales:

```
DB_ENGINE=django.db.backends.postgresql
DB_NAME=gestioncloud
DB_USER=postgres
DB_PASSWORD=tu_password_aqui
DB_HOST=localhost
DB_PORT=5432
```

### 4. Instalar dependencias

Asegúrate de tener `psycopg2-binary` instalado (ya está en requirements.txt):

```bash
pip install psycopg2-binary
```

### 5. Migrar la base de datos

Ejecuta las migraciones para crear las tablas:

```bash
python manage.py migrate
```

### 6. Crear superusuario (opcional)

Si necesitas crear un usuario administrador:

```bash
python manage.py createsuperuser
```

### 7. Cargar datos iniciales (si aplica)

Si tienes datos en SQLite que quieres migrar, puedes usar:

```bash
# Exportar desde SQLite
python manage.py dumpdata > backup.json

# Cambiar a PostgreSQL en settings.py
# Ejecutar migraciones
python manage.py migrate

# Importar datos
python manage.py loaddata backup.json
```

## Verificar conexión

Para verificar que la conexión funciona:

```bash
python manage.py dbshell
```

Si se conecta correctamente, verás el prompt de PostgreSQL.

## Notas importantes

- **Backup**: Antes de cambiar, haz un backup de tu base de datos SQLite actual
- **Credenciales**: Cambia las credenciales por defecto en producción
- **Puerto**: El puerto por defecto de PostgreSQL es 5432
- **Host**: Si PostgreSQL está en otro servidor, cambia `DB_HOST` a la IP o dominio correspondiente


