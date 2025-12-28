-- Script SQL para otorgar permisos completos en el esquema public
-- Ejecuta este archivo como superusuario (postgres)

-- Conectar a la base de datos gestioncloud
\c gestioncloud

-- Otorgar permisos de creación y uso en el esquema public
GRANT CREATE ON SCHEMA public TO kreasoft;
GRANT USAGE ON SCHEMA public TO kreasoft;
GRANT ALL ON SCHEMA public TO kreasoft;

-- Configurar privilegios por defecto para tablas y secuencias
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kreasoft;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO kreasoft;

-- Otorgar permisos en todas las tablas existentes (si las hay)
DO $$ 
DECLARE 
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') 
    LOOP
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE public.' || quote_ident(r.tablename) || ' TO kreasoft';
    END LOOP;
END $$;

-- Verificar permisos
\dn+ public













