-- Script SQL para crear la base de datos GestionCloud
-- Ejecuta estos comandos como superusuario (postgres) en psql o pgAdmin

-- 1. Crear la base de datos
CREATE DATABASE gestioncloud OWNER kreasoft;

-- 2. Conectar a la base de datos gestioncloud
\c gestioncloud

-- 3. Otorgar todos los privilegios al usuario kreasoft
GRANT ALL PRIVILEGES ON DATABASE gestioncloud TO kreasoft;

-- 4. Otorgar privilegios en el esquema público
GRANT ALL ON SCHEMA public TO kreasoft;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kreasoft;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO kreasoft;














