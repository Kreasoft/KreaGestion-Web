# DTE GDExpress

Paquete Python/Django para integración completa de Facturación Electrónica Chilena con GDExpress/DTEBox.

## 🚀 Características

- ✅ Generación de XML para todos los tipos de DTE (33, 34, 39, 52, 56, 61)
- ✅ Firma digital con certificado .pfx/.p12
- ✅ Generación de timbre electrónico (TED)
- ✅ Integración completa con GDExpress/DTEBox
- ✅ Gestión de folios (CAF)
- ✅ Sincronización de documentos recibidos
- ✅ Modelos Django opcionales
- ✅ Utilidades para RUT, montos, validaciones

## 📦 Instalación

```bash
pip install dte-gdexpress
```

O desde el código fuente:

```bash
git clone https://github.com/tuusuario/dte_gdexpress.git
cd dte_gdexpress
pip install -e .
```

## 🔧 Configuración Rápida

### 1. Agregar a INSTALLED_APPS (opcional, si usas modelos)

```python
INSTALLED_APPS = [
    ...
    'dte_gdexpress',
]
```

### 2. Configurar credenciales

```python
# settings.py
DTE_GDEXPRESS = {
    'API_KEY': 'tu-api-key-aqui',
    'AMBIENTE': 'CERTIFICACION',  # o 'PRODUCCION'
    'URL_SERVICIO': 'http://200.6.118.43/api/Core.svc/Core',
    'CERTIFICADO_PATH': 'path/to/certificado.pfx',
    'CERTIFICADO_PASSWORD': 'password',
}
```

### 3. Ejecutar migraciones (si usas modelos)

```bash
python manage.py migrate dte_gdexpress
```

## 💡 Uso Básico

### Generar y Enviar una Factura

```python
from dte_gdexpress.generadores import GeneradorFactura
from dte_gdexpress.firma import Firmador
from dte_gdexpress.gdexpress import ClienteGDExpress

# 1. Generar XML
factura = GeneradorFactura(
    folio=12345,
    fecha='2025-12-20',
    rut_emisor='77117239-3',
    razon_social_emisor='Mi Empresa SPA',
    giro_emisor='Servicios de TI',
    direccion_emisor='Av. Principal 123',
    comuna_emisor='Santiago',
    rut_receptor='12345678-9',
    razon_social_receptor='Cliente Ejemplo',
    giro_receptor='Comercio',
    direccion_receptor='Calle Falsa 456',
    comuna_receptor='Providencia',
    items=[
        {
            'nombre': 'Servicio de Desarrollo',
            'cantidad': 1,
            'precio': 100000,
            'descuento_porcentaje': 0,
        }
    ]
)

xml = factura.generar_xml()

# 2. Firmar
firmador = Firmador(
    certificado_path='certificado.pfx',
    password='mi-password'
)
xml_firmado = firmador.firmar(xml)

# 3. Enviar a GDExpress
cliente = ClienteGDExpress(
    api_key='tu-api-key',
    ambiente='CERTIFICACION'
)

resultado = cliente.enviar_dte(xml_firmado)

if resultado['success']:
    print(f"DTE enviado exitosamente. Track ID: {resultado['track_id']}")
else:
    print(f"Error: {resultado['error']}")
```

### Sincronizar Documentos Recibidos

```python
from dte_gdexpress.gdexpress import ClienteGDExpress

cliente = ClienteGDExpress(api_key='tu-api-key')

# Obtener documentos del último mes
documentos = cliente.obtener_documentos_recibidos(
    rut_receptor='77117239-3',
    dias=30
)

for doc in documentos:
    print(f"{doc['tipo']} #{doc['numero']} - ${doc['total']}")
```

### Gestión de Folios (CAF)

```python
from dte_gdexpress.caf import GestorCAF

gestor = GestorCAF()

# Cargar archivo CAF
gestor.cargar_caf('FOLIO33.xml')

# Obtener siguiente folio disponible
folio = gestor.obtener_siguiente_folio(tipo_dte=33)

# Verificar folios disponibles
disponibles = gestor.folios_disponibles(tipo_dte=33)
print(f"Folios disponibles: {disponibles}")
```

## 📚 Documentación Completa

- [Instalación Detallada](INSTALACION.md)
- [Ejemplos de Uso](EJEMPLOS.md)
- [Integración en Proyecto Existente](INTEGRACION.md)
- [API Reference](API.md)

## 🏗️ Tipos de DTE Soportados

| Código | Tipo de Documento |
|--------|-------------------|
| 33 | Factura Electrónica |
| 34 | Factura Exenta Electrónica |
| 39 | Boleta Electrónica |
| 52 | Guía de Despacho Electrónica |
| 56 | Nota de Débito Electrónica |
| 61 | Nota de Crédito Electrónica |

## 🔐 Seguridad

- Las credenciales deben almacenarse en variables de entorno
- Los certificados digitales deben protegerse adecuadamente
- Nunca commitear archivos .pfx o passwords en el repositorio

## 🤝 Contribuir

Las contribuciones son bienvenidas! Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

MIT License - ver archivo [LICENSE](LICENSE)

## 👥 Autores

- **KreaSoft** - *Desarrollo inicial* - [Kreasoft](https://github.com/Kreasoft)

## 🙏 Agradecimientos

- Servicio de Impuestos Internos (SII) de Chile
- GDExpress/DTEBox por su plataforma de facturación

## 📞 Soporte

- Email: soporte@kreasoft.cl
- Issues: [GitHub Issues](https://github.com/Kreasoft/dte_gdexpress/issues)
- Documentación: [Wiki](https://github.com/Kreasoft/dte_gdexpress/wiki)
