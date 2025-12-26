# 💡 Ejemplos de Uso - DTE GDExpress

## Índice

1. [Generar Factura Electrónica (33)](#1-generar-factura-electrónica-33)
2. [Generar Boleta Electrónica (39)](#2-generar-boleta-electrónica-39)
3. [Generar Guía de Despacho (52)](#3-generar-guía-de-despacho-52)
4. [Generar Nota de Crédito (61)](#4-generar-nota-de-crédito-61)
5. [Firmar Documentos](#5-firmar-documentos)
6. [Enviar a GDExpress](#6-enviar-a-gdexpress)
7. [Consultar Estado de DTE](#7-consultar-estado-de-dte)
8. [Sincronizar Documentos Recibidos](#8-sincronizar-documentos-recibidos)
9. [Gestión de Folios (CAF)](#9-gestión-de-folios-caf)
10. [Uso con Modelos Django](#10-uso-con-modelos-django)

---

## 1. Generar Factura Electrónica (33)

```python
from dte_gdexpress.generadores import GeneradorFactura
from datetime import date

# Crear generador
factura = GeneradorFactura(
    # Folio
    folio=12345,
    fecha=date.today(),
    
    # Emisor
    rut_emisor='77117239-3',
    razon_social_emisor='Mi Empresa SPA',
    giro_emisor='Servicios de Tecnología',
    direccion_emisor='Av. Libertador Bernardo O\'Higgins 123',
    comuna_emisor='Santiago',
    ciudad_emisor='Santiago',
    
    # Receptor
    rut_receptor='12345678-9',
    razon_social_receptor='Cliente Ejemplo LTDA',
    giro_receptor='Comercio al por menor',
    direccion_receptor='Calle Falsa 456',
    comuna_receptor='Providencia',
    ciudad_receptor='Santiago',
    
    # Items
    items=[
        {
            'numero_linea': 1,
            'nombre': 'Servicio de Desarrollo Web',
            'descripcion': 'Desarrollo de sitio web corporativo',
            'cantidad': 1,
            'unidad': 'UN',
            'precio': 1000000,
            'descuento_porcentaje': 0,
            'descuento_monto': 0,
        },
        {
            'numero_linea': 2,
            'nombre': 'Hosting Anual',
            'descripcion': 'Servicio de hosting por 12 meses',
            'cantidad': 12,
            'unidad': 'MES',
            'precio': 50000,
            'descuento_porcentaje': 10,  # 10% de descuento
        },
    ],
    
    # Forma de pago (opcional)
    forma_pago='2',  # 1=Contado, 2=Crédito
    fecha_vencimiento=date(2025, 1, 20),
    
    # Observaciones (opcional)
    observaciones='Gracias por su preferencia',
)

# Generar XML
xml = factura.generar_xml()
print(xml)
```

---

## 2. Generar Boleta Electrónica (39)

```python
from dte_gdexpress.generadores import GeneradorBoleta

boleta = GeneradorBoleta(
    folio=5678,
    fecha=date.today(),
    
    # Emisor
    rut_emisor='77117239-3',
    razon_social_emisor='Mi Tienda SPA',
    giro_emisor='Venta al por menor',
    direccion_emisor='Av. Principal 789',
    comuna_emisor='Santiago',
    
    # Items
    items=[
        {
            'nombre': 'Producto A',
            'cantidad': 2,
            'precio': 15000,
        },
        {
            'nombre': 'Producto B',
            'cantidad': 1,
            'precio': 25000,
        },
    ],
)

xml = boleta.generar_xml()
```

---

## 3. Generar Guía de Despacho (52)

```python
from dte_gdexpress.generadores import GeneradorGuia

guia = GeneradorGuia(
    folio=9999,
    fecha=date.today(),
    
    # Emisor
    rut_emisor='77117239-3',
    razon_social_emisor='Mi Empresa SPA',
    direccion_emisor='Av. Principal 123',
    comuna_emisor='Santiago',
    
    # Receptor
    rut_receptor='12345678-9',
    razon_social_receptor='Cliente LTDA',
    direccion_receptor='Calle Falsa 456',
    comuna_receptor='Providencia',
    
    # Traslado
    ind_traslado=1,  # 1=Operación constituye venta
    direccion_despacho='Calle Destino 789, Las Condes',
    comuna_despacho='Las Condes',
    ciudad_despacho='Santiago',
    rut_chofer='98765432-1',
    nombre_chofer='Juan Pérez',
    patente='ABCD12',
    
    # Items
    items=[
        {
            'nombre': 'Producto X',
            'cantidad': 10,
            'precio': 5000,
        },
    ],
    
    # Referencia a factura (opcional)
    referencias=[
        {
            'tipo_documento': 33,  # Factura
            'folio': 12345,
            'fecha': date(2025, 12, 15),
            'razon': 'Guía de despacho de factura 12345',
        }
    ],
)

xml = guia.generar_xml()
```

---

## 4. Generar Nota de Crédito (61)

```python
from dte_gdexpress.generadores import GeneradorNotaCredito

nota_credito = GeneradorNotaCredito(
    folio=111,
    fecha=date.today(),
    
    # Emisor
    rut_emisor='77117239-3',
    razon_social_emisor='Mi Empresa SPA',
    direccion_emisor='Av. Principal 123',
    comuna_emisor='Santiago',
    
    # Receptor
    rut_receptor='12345678-9',
    razon_social_receptor='Cliente LTDA',
    direccion_receptor='Calle Falsa 456',
    comuna_receptor='Providencia',
    
    # Items (productos devueltos o anulados)
    items=[
        {
            'nombre': 'Devolución Producto A',
            'cantidad': 1,
            'precio': 50000,
        },
    ],
    
    # Referencia al documento original (OBLIGATORIO)
    referencias=[
        {
            'tipo_documento': 33,  # Factura
            'folio': 12345,
            'fecha': date(2025, 12, 15),
            'razon': 'Anula factura 12345 por error en monto',
            'codigo_referencia': 1,  # 1=Anula, 2=Corrige monto, 3=Corrige texto
        }
    ],
)

xml = nota_credito.generar_xml()
```

---

## 5. Firmar Documentos

```python
from dte_gdexpress.firma import Firmador

# Inicializar firmador
firmador = Firmador(
    certificado_path='certificados/certificado.pfx',
    password='mi-password-seguro'
)

# Firmar XML
xml_sin_firmar = factura.generar_xml()
xml_firmado = firmador.firmar(xml_sin_firmar)

# Verificar firma
es_valida = firmador.verificar_firma(xml_firmado)
print(f"Firma válida: {es_valida}")

# Generar timbre electrónico (TED)
ted = firmador.generar_timbre(
    tipo_dte=33,
    folio=12345,
    fecha='2025-12-20',
    rut_emisor='77117239-3',
    rut_receptor='12345678-9',
    monto_total=1190000
)
```

---

## 6. Enviar a GDExpress

```python
from dte_gdexpress.gdexpress import ClienteGDExpress

# Inicializar cliente
cliente = ClienteGDExpress(
    api_key='tu-api-key',
    ambiente='CERTIFICACION'  # o 'PRODUCCION'
)

# Enviar DTE
resultado = cliente.enviar_dte(
    xml_firmado=xml_firmado,
    tipo_envio='DTE',  # o 'EnvioBOLETA'
)

if resultado['success']:
    print(f"✅ DTE enviado exitosamente")
    print(f"Track ID: {resultado['track_id']}")
    print(f"Estado: {resultado['estado']}")
else:
    print(f"❌ Error: {resultado['error']}")
    print(f"Detalle: {resultado.get('detalle', '')}")
```

---

## 7. Consultar Estado de DTE

```python
# Consultar por Track ID
estado = cliente.consultar_estado(track_id='ABC123XYZ')

print(f"Estado: {estado['estado']}")
print(f"Glosa: {estado['glosa']}")
print(f"Fecha: {estado['fecha']}")

# Consultar por Folio
estado_folio = cliente.consultar_por_folio(
    tipo_dte=33,
    folio=12345,
    rut_emisor='77117239-3'
)
```

---

## 8. Sincronizar Documentos Recibidos

```python
# Obtener documentos recibidos del último mes
documentos = cliente.obtener_documentos_recibidos(
    rut_receptor='77117239-3',
    dias=30,
    tipos_dte=[33, 34, 61, 56]  # Facturas, Facturas Exentas, NC, ND
)

print(f"Total documentos: {len(documentos)}")

for doc in documentos:
    print(f"\n{doc['tipo_documento']} #{doc['numero']}")
    print(f"  Proveedor: {doc['razon_social_emisor']}")
    print(f"  RUT: {doc['rut_emisor']}")
    print(f"  Fecha: {doc['fecha_emision']}")
    print(f"  Total: ${doc['total']:,.0f}")
    print(f"  PDF: {doc['download_url']}")
```

---

## 9. Gestión de Folios (CAF)

```python
from dte_gdexpress.caf import GestorCAF

# Inicializar gestor
gestor = GestorCAF(directorio='folios/')

# Cargar archivo CAF
gestor.cargar_caf('folios/FOLIO33.xml')

# Obtener siguiente folio disponible
folio = gestor.obtener_siguiente_folio(tipo_dte=33)
print(f"Siguiente folio: {folio}")

# Verificar folios disponibles
disponibles = gestor.folios_disponibles(tipo_dte=33)
print(f"Folios disponibles: {disponibles}")

# Verificar vigencia del CAF
vigente = gestor.verificar_vigencia(tipo_dte=33)
print(f"CAF vigente: {vigente}")

# Marcar folio como usado
gestor.marcar_folio_usado(tipo_dte=33, folio=12345)

# Obtener información del CAF
info = gestor.obtener_info_caf(tipo_dte=33)
print(f"Rango: {info['desde']} - {info['hasta']}")
print(f"Fecha autorización: {info['fecha_autorizacion']}")
```

---

## 10. Uso con Modelos Django

```python
from dte_gdexpress.models import Empresa, CAF, Documento, DetalleDocumento
from django.utils import timezone

# Crear empresa
empresa = Empresa.objects.create(
    rut='77117239-3',
    razon_social='Mi Empresa SPA',
    giro='Servicios de TI',
    direccion='Av. Principal 123',
    comuna='Santiago',
    ciudad='Santiago',
    api_key='tu-api-key',
    ambiente='CERTIFICACION'
)

# Cargar CAF
caf = CAF.objects.create(
    empresa=empresa,
    tipo_documento='FACTURA',
    desde=1,
    hasta=1000,
    fecha_autorizacion=timezone.now(),
    xml_data='<CAF>...</CAF>'
)

# Crear documento
documento = Documento.objects.create(
    empresa=empresa,
    tipo_documento='FACTURA',
    folio=12345,
    fecha_emision=timezone.now().date(),
    rut_receptor='12345678-9',
    razon_social_receptor='Cliente LTDA',
    neto=1000000,
    iva=190000,
    total=1190000,
    estado_fiscal=0  # Autorizado
)

# Agregar detalles
DetalleDocumento.objects.create(
    documento=documento,
    numero_linea=1,
    nombre='Servicio de Desarrollo',
    cantidad=1,
    precio_unitario=1000000,
    descuento=0,
    subtotal=1000000
)

# Generar y enviar
from dte_gdexpress.generadores import GeneradorFactura
from dte_gdexpress.firma import Firmador
from dte_gdexpress.gdexpress import ClienteGDExpress

# ... (código de generación, firma y envío)

# Actualizar documento con resultado
documento.track_id = resultado['track_id']
documento.xml_enviado = xml_firmado
documento.save()
```

---

## Ejemplo Completo: Flujo de Facturación

```python
from dte_gdexpress.generadores import GeneradorFactura
from dte_gdexpress.firma import Firmador
from dte_gdexpress.gdexpress import ClienteGDExpress
from dte_gdexpress.caf import GestorCAF
from datetime import date

# 1. Obtener folio
gestor_caf = GestorCAF()
folio = gestor_caf.obtener_siguiente_folio(tipo_dte=33)

# 2. Generar factura
factura = GeneradorFactura(
    folio=folio,
    fecha=date.today(),
    rut_emisor='77117239-3',
    razon_social_emisor='Mi Empresa SPA',
    giro_emisor='Servicios de TI',
    direccion_emisor='Av. Principal 123',
    comuna_emisor='Santiago',
    rut_receptor='12345678-9',
    razon_social_receptor='Cliente LTDA',
    direccion_receptor='Calle Falsa 456',
    comuna_receptor='Providencia',
    items=[
        {
            'nombre': 'Servicio de Desarrollo',
            'cantidad': 1,
            'precio': 1000000,
        }
    ]
)

xml = factura.generar_xml()

# 3. Firmar
firmador = Firmador(
    certificado_path='certificados/certificado.pfx',
    password='mi-password'
)
xml_firmado = firmador.firmar(xml)

# 4. Enviar
cliente = ClienteGDExpress(
    api_key='tu-api-key',
    ambiente='CERTIFICACION'
)
resultado = cliente.enviar_dte(xml_firmado)

# 5. Procesar resultado
if resultado['success']:
    # Marcar folio como usado
    gestor_caf.marcar_folio_usado(tipo_dte=33, folio=folio)
    
    print(f"✅ Factura {folio} enviada exitosamente")
    print(f"Track ID: {resultado['track_id']}")
    
    # Guardar en base de datos (si usas modelos)
    # ...
else:
    print(f"❌ Error al enviar factura: {resultado['error']}")
```

---

## Más Ejemplos

Para más ejemplos, consulta:
- [Integración en Proyecto Existente](INTEGRACION.md)
- [API Reference](API.md)
- [Proyecto de Ejemplo](ejemplo_integracion/)
