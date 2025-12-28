# 📄 Sistema de Facturación Electrónica

Sistema completo de Facturación Electrónica integrado con el SII de Chile.

## 🎯 Características

### ✅ Implementado

- **Modelos de Base de Datos:**
  - ✅ `ArchivoCAF` - Gestión de Códigos de Autorización de Folios
  - ✅ `DocumentoTributarioElectronico` - Registro de todos los DTE
  - ✅ `EnvioDTE` - Control de envíos masivos al SII
  - ✅ `AcuseRecibo` - Gestión de acuses de clientes

- **Configuración de Empresa:**
  - ✅ Campos de FE en modelo Empresa
  - ✅ Certificado digital
  - ✅ Ambiente SII (Certificación/Producción)
  - ✅ Resoluciones SII
  - ✅ Datos para emisión

- **Interfaz:**
  - ✅ Pestaña de Facturación Electrónica en detalle de empresa
  - ✅ Panel administrativo de Django

### 🚧 En Desarrollo

- **Gestión de CAF:**
  - 🔄 Carga de archivos CAF
  - 🔄 Parser de XML CAF
  - 🔄 Control automático de folios
  - 🔄 Alertas de folios bajos

- **Generación de DTE:**
  - 🔄 Generación de XML según formato SII
  - 🔄 Firma electrónica con certificado digital
  - 🔄 Generación de TED (Timbre Electrónico)
  - 🔄 Generación de código PDF417
  - 🔄 Generación de PDF con timbre

- **Integración con SII:**
  - 🔄 Cliente SOAP para webservices SII
  - 🔄 Envío de DTE
  - 🔄 Consulta de estado
  - 🔄 Recepción de acuses
  - 🔄 Logs y auditoría

- **Integración con POS:**
  - 🔄 Selector de tipo documento electrónico
  - 🔄 Generación automática al procesar venta
  - 🔄 Impresión con timbre electrónico
  - 🔄 Envío automático por email

## 📦 Modelos

### ArchivoCAF

Control de rangos de folios autorizados por el SII.

**Campos principales:**
- `empresa` - Empresa propietaria
- `tipo_documento` - Tipo de DTE (33, 39, 52, etc.)
- `folio_desde` / `folio_hasta` - Rango de folios
- `archivo_xml` - Archivo CAF original
- `folio_actual` - Último folio utilizado
- `estado` - activo/agotado/vencido/anulado

**Métodos:**
- `obtener_siguiente_folio()` - Obtiene y reserva el siguiente folio disponible
- `folios_disponibles()` - Retorna cantidad de folios disponibles
- `porcentaje_uso()` - Retorna porcentaje de uso del CAF

### DocumentoTributarioElectronico

Registro completo de cada DTE emitido.

**Campos principales:**
- `empresa` / `venta` - Relaciones
- `tipo_dte` / `folio` - Identificación
- `fecha_emision` - Fecha de emisión
- Datos del receptor (RUT, razón social, dirección)
- Montos (neto, exento, IVA, total)
- `xml_dte` / `xml_firmado` - XML del documento
- `timbre_electronico` - TED generado
- `estado_sii` - Estado en el SII
- `track_id` - ID de seguimiento SII

### EnvioDTE

Control de envíos masivos al SII (SetDTE).

**Campos principales:**
- `empresa` - Empresa
- `documentos` - Many-to-Many con DTE
- `xml_envio` - XML del SetDTE
- `track_id` - ID de seguimiento
- `estado` - pendiente/enviado/aceptado/rechazado

### AcuseRecibo

Registro de acuses recibidos de clientes.

**Campos principales:**
- `dte` - Documento relacionado
- `tipo_acuse` - comercial/recibo/reclamo/aceptacion
- `xml_acuse` - XML del acuse
- `procesado` - Flag de procesamiento

## 🔧 Configuración

### 1. Activar Facturación Electrónica en Empresa

En el admin de Django o en la interfaz de empresa, configurar:

```python
empresa.facturacion_electronica = True
empresa.ambiente_sii = 'certificacion'  # o 'produccion'
empresa.certificado_digital = archivo_p12
empresa.password_certificado = '******'
empresa.resolucion_numero = 80  # Número de resolución para ambiente de pruebas SII
empresa.resolucion_fecha = '2014-08-22'
# ... otros campos
```

### 2. Cargar Archivos CAF

```python
from facturacion_electronica.models import ArchivoCAF

caf = ArchivoCAF.objects.create(
    empresa=empresa,
    tipo_documento='39',  # Boleta Electrónica
    folio_desde=1,
    folio_hasta=1000,
    cantidad_folios=1000,
    archivo_xml=archivo_caf,
    contenido_caf=xml_content,
    fecha_autorizacion='2024-01-01',
    firma_electronica=frma
)
```

### 3. Generar DTE (Próximamente)

```python
from facturacion_electronica.services import DTEGenerator

generator = DTEGenerator(empresa)
dte = generator.generar_desde_venta(venta, tipo_dte='39')
```

## 📚 Documentación SII

- [Portal MIPYME](https://mipyme.sii.cl/)
- [Formato XML DTE](https://www.sii.cl/factura_electronica/formato_dte.pdf)
- [Webservices SII](https://www4.sii.cl/wsregistroreclamoreclamos/registroreclamoservice?wsdl)

## 🔐 Seguridad

⚠️ **IMPORTANTE:**

- Los certificados digitales deben estar encriptados en la base de datos
- Las contraseñas de certificados deben usar encriptación (django-fernet-fields)
- Los archivos CAF deben tener permisos restringidos
- Mantener logs de auditoría de todas las operaciones

## 📝 TODO List

### Fase 1: Parser de CAF
- [ ] Crear servicio para leer XML de CAF
- [ ] Extraer datos (rangos, firma, etc.)
- [ ] Validar integridad del CAF
- [ ] Vista para cargar CAF

### Fase 2: Generador de DTE
- [ ] Template XML para cada tipo de DTE
- [ ] Servicio de firma electrónica
- [ ] Generador de TED
- [ ] Generador de código PDF417
- [ ] Template PDF con timbre

### Fase 3: Integración SII
- [ ] Cliente SOAP para SII
- [ ] Envío de DTE
- [ ] Consulta de estado
- [ ] Procesamiento de respuestas

### Fase 4: Integración POS
- [ ] Modificar flujo de caja
- [ ] Selector de tipo DTE
- [ ] Generación automática
- [ ] Impresión mejorada

## 🤝 Contribución

Para contribuir al desarrollo:

1. Revisa el TODO List
2. Crea un branch para tu feature
3. Implementa con tests
4. Documenta en este README
5. Crea un Pull Request

## 📞 Soporte

Para dudas sobre implementación SII:
- Mesa de ayuda SII: 223952000
- Portal MIPYME: https://mipyme.sii.cl





















