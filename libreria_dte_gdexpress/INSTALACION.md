# 📦 Guía de Instalación - DTE GDExpress

## Requisitos Previos

- Python 3.8 o superior
- Django 3.2 o superior (si usas los modelos)
- Certificado digital (.pfx o .p12) para firma electrónica
- API Key de GDExpress/DTEBox

## Instalación

### Opción 1: Instalación con pip (Recomendado)

```bash
pip install dte-gdexpress
```

### Opción 2: Instalación desde código fuente

```bash
git clone https://github.com/Kreasoft/dte_gdexpress.git
cd dte_gdexpress
pip install -e .
```

### Opción 3: Instalación manual

1. Descarga el paquete
2. Copia la carpeta `dte_gdexpress` a tu proyecto
3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Configuración

### 1. Configuración Básica (Sin Django)

Si solo necesitas las funciones sin usar Django:

```python
# config.py
DTE_CONFIG = {
    'API_KEY': 'tu-api-key-gdexpress',
    'AMBIENTE': 'CERTIFICACION',  # o 'PRODUCCION'
    'URL_SERVICIO': 'http://200.6.118.43/api/Core.svc/Core',
    'CERTIFICADO_PATH': '/path/to/certificado.pfx',
    'CERTIFICADO_PASSWORD': 'password-certificado',
}
```

### 2. Configuración con Django

#### 2.1 Agregar a INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Tu app
    'tu_app',
    
    # DTE GDExpress
    'dte_gdexpress',  # Solo si usarás los modelos
]
```

#### 2.2 Configurar en settings.py

```python
# settings.py

# Configuración DTE GDExpress
DTE_GDEXPRESS = {
    # Credenciales GDExpress/DTEBox
    'API_KEY': os.getenv('GDEXPRESS_API_KEY', 'tu-api-key'),
    
    # Ambiente: 'CERTIFICACION' o 'PRODUCCION'
    'AMBIENTE': os.getenv('DTE_AMBIENTE', 'CERTIFICACION'),
    
    # URL del servicio
    'URL_SERVICIO': 'http://200.6.118.43/api/Core.svc/Core',
    
    # Certificado Digital
    'CERTIFICADO_PATH': os.path.join(BASE_DIR, 'certificados', 'certificado.pfx'),
    'CERTIFICADO_PASSWORD': os.getenv('CERT_PASSWORD', ''),
    
    # Configuración de Folios
    'CAF_DIRECTORY': os.path.join(BASE_DIR, 'folios'),
    
    # Configuración de Empresa (Opcional)
    'RUT_EMISOR': '77117239-3',
    'RAZON_SOCIAL': 'Mi Empresa SPA',
    'GIRO': 'Servicios de TI',
    'DIRECCION': 'Av. Principal 123',
    'COMUNA': 'Santiago',
    'CIUDAD': 'Santiago',
}
```

#### 2.3 Variables de Entorno (.env)

Crea un archivo `.env` en la raíz de tu proyecto:

```bash
# .env

# GDExpress
GDEXPRESS_API_KEY=tu-api-key-aqui
DTE_AMBIENTE=CERTIFICACION

# Certificado
CERT_PASSWORD=password-del-certificado

# Base de datos (si usas modelos)
DATABASE_URL=postgresql://user:password@localhost/dbname
```

Instala python-decouple para leer el .env:

```bash
pip install python-decouple
```

Y en settings.py:

```python
from decouple import config

DTE_GDEXPRESS = {
    'API_KEY': config('GDEXPRESS_API_KEY'),
    'AMBIENTE': config('DTE_AMBIENTE', default='CERTIFICACION'),
    'CERTIFICADO_PASSWORD': config('CERT_PASSWORD'),
    ...
}
```

### 3. Ejecutar Migraciones (Solo si usas modelos Django)

```bash
python manage.py migrate dte_gdexpress
```

Esto creará las siguientes tablas:
- `dte_gdexpress_empresa`
- `dte_gdexpress_caf`
- `dte_gdexpress_documento`
- `dte_gdexpress_detalledocumento`
- `dte_gdexpress_cliente`

### 4. Configurar Certificado Digital

#### 4.1 Crear directorio para certificados

```bash
mkdir certificados
```

#### 4.2 Copiar tu certificado

```bash
cp /path/to/tu-certificado.pfx certificados/
```

#### 4.3 Proteger el directorio

```bash
chmod 700 certificados
chmod 600 certificados/*.pfx
```

#### 4.4 Agregar a .gitignore

```
# .gitignore
certificados/
*.pfx
*.p12
.env
```

### 5. Configurar Folios (CAF)

#### 5.1 Crear directorio para folios

```bash
mkdir folios
```

#### 5.2 Descargar folios desde el SII

1. Ingresa al sitio del SII
2. Ve a "Facturación Electrónica" > "Folios"
3. Descarga los archivos CAF (.xml)

#### 5.3 Copiar archivos CAF

```bash
cp /path/to/FOLIO33.xml folios/
cp /path/to/FOLIO39.xml folios/
# etc...
```

### 6. Verificar Instalación

Crea un script de prueba:

```python
# test_instalacion.py
from dte_gdexpress.utils import validar_rut
from dte_gdexpress.gdexpress import ClienteGDExpress

# Test 1: Validar RUT
print("Test 1: Validación de RUT")
print(f"RUT válido: {validar_rut('77117239-3')}")  # True
print(f"RUT inválido: {validar_rut('12345678-9')}")  # False

# Test 2: Conexión con GDExpress
print("\nTest 2: Conexión GDExpress")
try:
    cliente = ClienteGDExpress(
        api_key='tu-api-key',
        ambiente='CERTIFICACION'
    )
    print("✅ Cliente GDExpress inicializado correctamente")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n✅ Instalación completada exitosamente!")
```

Ejecuta:

```bash
python test_instalacion.py
```

## Solución de Problemas

### Error: "No module named 'dte_gdexpress'"

```bash
pip install -e .
```

### Error: "Invalid API Key"

Verifica que tu API Key sea correcta en el archivo `.env` o `settings.py`

### Error: "Certificate not found"

Verifica la ruta del certificado:

```python
import os
print(os.path.exists('certificados/certificado.pfx'))
```

### Error de firma: "Invalid password"

Verifica que el password del certificado sea correcto.

## Próximos Pasos

1. Lee la [Guía de Ejemplos](EJEMPLOS.md)
2. Revisa la [Guía de Integración](INTEGRACION.md)
3. Consulta la [API Reference](API.md)

## Soporte

Si tienes problemas con la instalación:

- 📧 Email: soporte@kreasoft.cl
- 🐛 Issues: [GitHub Issues](https://github.com/Kreasoft/dte_gdexpress/issues)
- 📚 Wiki: [Documentación](https://github.com/Kreasoft/dte_gdexpress/wiki)
