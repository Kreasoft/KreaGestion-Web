# Otorgar Permisos en PostgreSQL

El usuario `kreasoft` necesita permisos de creación en el esquema `public` para poder ejecutar las migraciones de Django.

## Opción 1: Ejecutar desde psql (Recomendado)

1. Abre una terminal y ejecuta:
```bash
psql -U postgres -d gestioncloud
```

2. Cuando te pida la contraseña, ingresa la contraseña del usuario `postgres`

3. Ejecuta estos comandos:
```sql
GRANT CREATE ON SCHEMA public TO kreasoft;
GRANT USAGE ON SCHEMA public TO kreasoft;
GRANT ALL ON SCHEMA public TO kreasoft;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kreasoft;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO kreasoft;
```

4. Sal de psql:
```sql
\q
```

## Opción 2: Ejecutar el archivo SQL

```bash
psql -U postgres -d gestioncloud -f otorgar_permisos_public.sql
```

## Opción 3: Desde pgAdmin

1. Abre pgAdmin
2. Conéctate al servidor PostgreSQL
3. Navega a: Servidores → PostgreSQL → Bases de datos → gestioncloud → Esquemas → public
4. Click derecho en `public` → Properties → Privileges
5. Agrega el usuario `kreasoft` con todos los permisos (CREATE, USAGE, ALL)

## Después de otorgar permisos

Ejecuta las migraciones:
```bash
python manage.py migrate
```


