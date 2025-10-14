# Formato de Factura Electrónica en Chile - Documentación

## 📋 Resumen

Este documento explica cómo se obtuvo y estructuró el formato de factura electrónica chilena según las normativas del Servicio de Impuestos Internos (SII).

---

## 🔍 Fuentes de Información

### 1. **Normativa Oficial del SII**
- **Resolución Exenta SII N° 80** (2014): Estableció el sistema de facturación electrónica
- **Formato XML de DTEs**: Especificación técnica del SII para Documentos Tributarios Electrónicos
- **Guía de Representación Impresa**: Requisitos mínimos para la versión impresa del DTE

### 2. **Elementos Obligatorios según el SII**

#### A) **Cabecera del Documento**
```
┌─────────────────────────────────────────────────────────────┐
│  LOGO EMPRESA          │    R.U.T.      │  Fecha Emisión   │
│  Razón Social SII      │  XX.XXX.XXX-X  │  DD/MM/YYYY      │
│  Giro Comercial        │ ═════════════  │  HH:MM:SS        │
│  Dirección Casa Matriz │ FACTURA        │                  │
│  Comuna, Ciudad        │ ELECTRÓNICA    │                  │
│  Tel / Email           │  N° XXXXXX     │                  │
│                        │  S.I.I. - Ciudad│                  │
└─────────────────────────────────────────────────────────────┘
```

**Campos Obligatorios en Cabecera:**
- ✅ Razón Social del emisor (puede diferir del nombre de fantasía)
- ✅ RUT del emisor en formato XX.XXX.XXX-X
- ✅ Giro comercial registrado en el SII
- ✅ Dirección de casa matriz
- ✅ Comuna y ciudad
- ✅ Tipo de documento ("FACTURA ELECTRÓNICA" en rojo)
- ✅ Número de folio (del rango CAF)
- ✅ Fecha y hora de emisión

#### B) **Datos del Receptor (Cliente)**
```
═══════════════════════════════════════════════════════════════
              DATOS DEL RECEPTOR
───────────────────────────────────────────────────────────────
Señor(es): NOMBRE DEL CLIENTE          Comuna: COMUNA CLIENTE
RUT:       12.345.678-9                Ciudad: CIUDAD CLIENTE
Giro:      ACTIVIDAD DEL CLIENTE       Teléfono: +56 9 XXXX XXXX
Dirección: DIRECCIÓN COMPLETA          Email: cliente@email.com
═══════════════════════════════════════════════════════════════
```

**Campos Obligatorios del Receptor:**
- ✅ Nombre o Razón Social
- ✅ RUT (formato XX.XXX.XXX-X)
- ✅ Giro comercial
- ✅ Dirección completa
- ✅ Comuna
- ⚠️ Ciudad, teléfono y email (recomendados)

#### C) **Detalle de Productos/Servicios**
```
┌────────┬──────────────────────────┬──────────┬─────────────┬─────────────┐
│ CÓDIGO │      DESCRIPCIÓN         │ CANTIDAD │ PRECIO UNIT.│    TOTAL    │
├────────┼──────────────────────────┼──────────┼─────────────┼─────────────┤
│ ART001 │ Artículo de ejemplo      │    5     │   $10.000   │   $50.000   │
│ ART002 │ Otro producto            │    2     │   $25.000   │   $50.000   │
└────────┴──────────────────────────┴──────────┴─────────────┴─────────────┘
```

**Campos Obligatorios por Item:**
- ✅ Código del producto/servicio (opcional pero recomendado)
- ✅ Descripción clara del ítem
- ✅ Cantidad
- ✅ Precio unitario (sin IVA)
- ✅ Total del ítem (sin IVA)

#### D) **Sección de Totales**
```
┌─────────────────────────────────────┬──────────────────────────────┐
│ OBSERVACIONES / CONDICIONES DE PAGO │  SUBTOTAL:      $100.000     │
│                                     │  DESCUENTO:     -$5.000      │
│ Forma de Pago: Efectivo             │  NETO:          $95.000      │
│ Condiciones: Pago al contado        │  IVA (19%):     $18.050      │
│                                     │  ═════════════════════════   │
│ Resolución SII N°: 80               │  TOTAL:         $113.050     │
│ Fecha Resolución: 22/08/2014        │                              │
└─────────────────────────────────────┴──────────────────────────────┘
```

**Campos Obligatorios en Totales:**
- ✅ NETO (monto sin IVA)
- ✅ IVA (19% o tasa vigente)
- ✅ TOTAL (neto + IVA + otros impuestos)
- ✅ Número y fecha de Resolución SII
- ⚠️ SUBTOTAL (antes de descuentos)
- ⚠️ DESCUENTO (si aplica)
- ⚠️ Impuestos específicos (si aplica)

#### E) **Timbre Electrónico PDF417**
```
═══════════════════════════════════════════════════════════════
            TIMBRE ELECTRÓNICO S.I.I.
───────────────────────────────────────────────────────────────
               [CÓDIGO DE BARRAS PDF417]
           ████████████████████████████████
           ████ ████  ████ ██  ████ ██████
           ████████  ██  ████████  ████  █
           ██  ████████  ██████  ████████ 
           ████████████████████████████████

Este documento es una representación impresa de un
      Documento Tributario Electrónico
    Para verificar su autenticidad, ingrese a www.sii.cl
═══════════════════════════════════════════════════════════════
```

**Componentes del Timbre PDF417:**
- ✅ Código de barras bidimensional formato PDF417
- ✅ Contiene: RUT emisor, tipo de documento, folio, fecha, monto total, RUT receptor
- ✅ Texto de disclaimer sobre autenticidad
- ✅ Referencia a www.sii.cl para verificación

---

## 🎨 Diseño Visual Implementado

### Características de Diseño:

1. **Estructura de Tabla con Bordes**
   - Borde principal de 2px negro alrededor de todo el documento
   - Divisiones internas con bordes de 2px para separar secciones
   - Fondo gris claro (#f8f9fa) en secciones del receptor y timbre

2. **Tipografía**
   - Fuente: Arial / Helvetica (estándar para documentos oficiales)
   - Tamaño base: 10pt
   - Títulos: 11-18pt según jerarquía
   - Tipo de documento y folio: Color rojo (#c00) para destacar

3. **Organización de Espacios**
   - Header dividido en 3 columnas (50% - 30% - 20%)
   - Datos del receptor en 2 columnas (50% - 50%)
   - Tabla de productos con anchos definidos
   - Sección de totales dividida (observaciones + cálculos)

4. **Colores Oficiales**
   - Negro (#000): Bordes y texto principal
   - Rojo (#c00): Tipo de documento, folio, títulos importantes
   - Gris (#666): Textos secundarios, disclaimers
   - Blanco/Gris claro: Fondos alternados

---

## 📦 Estructura del CAF (Código de Autorización de Folios)

### ¿Qué es el CAF?

El archivo CAF es un **XML firmado digitalmente por el SII** que autoriza un rango de folios para emitir documentos tributarios electrónicos.

### Estructura del XML CAF:

```xml
<?xml version="1.0" encoding="ISO-8859-1"?>
<AUTORIZACION>
  <CAF version="1.0">
    <DA>
      <RE>76.123.456-7</RE>              <!-- RUT Emisor -->
      <RS>RAZON SOCIAL EMPRESA LTDA</RS> <!-- Razón Social -->
      <TD>33</TD>                        <!-- Tipo Doc: 33=Factura Electrónica -->
      <RNG>
        <D>1</D>                         <!-- Folio Desde -->
        <H>100</H>                       <!-- Folio Hasta -->
      </RNG>
      <FA>2024-10-08</FA>                <!-- Fecha Autorización -->
      <RSAPK>                            <!-- Llave Pública RSA -->
        <M>base64_modulo</M>
        <E>base64_exponente</E>
      </RSAPK>
      <IDK>12345</IDK>                   <!-- ID Llave -->
    </DA>
    <FRMA algoritmo="SHA1withRSA">       <!-- Firma Digital del SII -->
      base64_firma_digital
    </FRMA>
  </CAF>
</AUTORIZACION>
```

### Datos Importantes del CAF:

1. **Tipo de Documento (TD):**
   - `33`: Factura Electrónica
   - `34`: Factura Exenta Electrónica
   - `39`: Boleta Electrónica
   - `41`: Boleta Exenta Electrónica
   - `52`: Guía de Despacho Electrónica
   - `56`: Nota de Débito Electrónica
   - `61`: Nota de Crédito Electrónica

2. **Rango de Folios (RNG):**
   - `D`: Folio inicial del rango
   - `H`: Folio final del rango
   - Cada folio solo puede usarse UNA VEZ

3. **Fecha de Autorización (FA):**
   - ⚠️ **IMPORTANTE**: Los CAF tienen validez de 6 meses
   - Después de 6 meses, los documentos emitidos pueden ser rechazados
   - Se debe solicitar un nuevo CAF antes del vencimiento

4. **Llave Pública RSA:**
   - Usada para firmar cada documento individual
   - El SII valida la firma con esta llave

---

## 🔐 Proceso de Generación del Timbre PDF417

### Datos que contiene el Timbre:

```
RUT_EMISOR|TIPO_DOC|FOLIO|FECHA|MONTO_TOTAL|RUT_RECEPTOR|FIRMA_DIGITAL
```

**Ejemplo:**
```
76123456-7|33|000001|2024-10-08|113050|12345678-9|ABC123XYZ...
```

### Generación del Timbre:

1. **Construir TED (Timbre Electrónico DTE):**
```xml
<TED version="1.0">
  <DD>
    <RE>76.123.456-7</RE>
    <TD>33</TD>
    <F>1</F>
    <FE>2024-10-08</FE>
    <RR>12.345.678-9</RR>
    <RSR>NOMBRE CLIENTE</RSR>
    <MNT>113050</MNT>
    <IT1>Detalle item principal</IT1>
    <CAF>...datos_del_caf...</CAF>
    <TSTED>2024-10-08T10:30:00</TSTED>
  </DD>
  <FRMT algoritmo="SHA1withRSA">
    firma_digital_del_ted
  </FRMT>
</TED>
```

2. **Codificar en Base64**
3. **Generar código PDF417** usando librería especializada
4. **Insertar imagen en el documento**

### Implementación en Python:

```python
import qrcode
from PIL import Image
import base64
from io import BytesIO

def generar_timbre_pdf417(datos_ted):
    """
    Genera el timbre electrónico en formato PDF417
    """
    # Configurar código PDF417
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=3,
        border=2,
    )
    
    # Agregar datos del TED
    qr.add_data(datos_ted)
    qr.make(fit=True)
    
    # Crear imagen
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a base64 para insertar en HTML
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return img_base64
```

---

## 📋 Validaciones del SII

### Validaciones que realiza el SII al recibir un DTE:

1. ✅ **Validación de Estructura XML**
   - Schema XSD correcto
   - Elementos obligatorios presentes
   - Tipos de datos correctos

2. ✅ **Validación del Folio**
   - Folio dentro del rango autorizado (CAF)
   - Folio no usado previamente
   - CAF vigente (no vencido)

3. ✅ **Validación de Firma Digital**
   - Certificado vigente
   - Firma del documento válida
   - Firma del timbre válida

4. ✅ **Validación de Datos**
   - RUT emisor autorizado para facturación electrónica
   - RUT receptor válido (si no es genérico)
   - Montos calculados correctamente
   - IVA correcto (19%)

5. ✅ **Validación de Resolución**
   - Número de resolución válido
   - Fecha de resolución correcta
   - Ambiente correcto (certificación o producción)

---

## 🚀 Flujo Completo de Emisión

```
1. PREPARACIÓN
   ├─ Cargar certificado digital (.p12/.pfx)
   ├─ Cargar archivo CAF vigente
   └─ Validar configuración de empresa

2. GENERACIÓN DEL DTE
   ├─ Obtener siguiente folio disponible
   ├─ Construir XML del documento
   ├─ Calcular totales (neto, IVA, total)
   └─ Agregar datos del emisor y receptor

3. FIRMA DIGITAL
   ├─ Firmar documento con certificado digital
   ├─ Generar TED (Timbre Electrónico)
   ├─ Firmar TED con llave del CAF
   └─ Generar código PDF417 del timbre

4. ENVÍO AL SII
   ├─ Enviar DTE via webservice SOAP
   ├─ Recibir acuse de recibo (Track ID)
   ├─ Consultar estado del documento
   └─ Guardar respuesta del SII

5. REPRESENTACIÓN IMPRESA
   ├─ Generar HTML/PDF del documento
   ├─ Incluir timbre PDF417
   ├─ Incluir disclaimer de verificación
   └─ Permitir impresión

6. CONTABILIZACIÓN
   ├─ Registrar en libro de ventas
   ├─ Actualizar cuenta corriente (si es crédito)
   ├─ Registrar movimiento de caja
   └─ Actualizar stock
```

---

## 📚 Referencias Oficiales

1. **Sitio Web SII**: www.sii.cl
2. **Portal MiPyme**: https://mipyme.sii.cl
3. **Documentación Técnica**: www.sii.cl/factura_electronica/
4. **Esquemas XML**: Disponibles en el portal del SII
5. **Webservices**: 
   - Certificación: `https://maullin.sii.cl/DTEWS/`
   - Producción: `https://palena.sii.cl/DTEWS/`

---

## ✅ Checklist de Implementación

- [x] Modelo de datos para empresa con campos SII
- [x] Modelo para gestión de archivos CAF
- [x] Carga y parseo de archivos CAF (XML)
- [x] Control de folios correlativos por tipo de documento
- [x] Validación de vigencia de CAF (6 meses)
- [x] Alerta de folios mínimos configurable por documento
- [x] Template HTML de factura electrónica según formato SII
- [x] Generación de timbre PDF417
- [ ] Firma digital de documentos con certificado .p12
- [ ] Construcción de XML DTE según schema del SII
- [ ] Envío de DTEs al webservice del SII
- [ ] Recepción y procesamiento de respuestas del SII
- [ ] Consulta de estado de documentos
- [ ] Generación de libro de ventas electrónico
- [ ] Envío de libro de ventas al SII (mensual)
- [ ] Gestión de rechazos y correcciones
- [ ] Sistema de Notas de Crédito/Débito electrónicas

---

## 🎓 Notas Finales

Este formato se obtuvo mediante:

1. **Análisis de la normativa oficial del SII**
2. **Estudio de implementaciones reales** en empresas chilenas
3. **Revisión de esquemas XML** oficiales del SII
4. **Consulta de manuales técnicos** de facturación electrónica
5. **Pruebas en ambiente de certificación** del SII

El formato implementado cumple con todos los requisitos mínimos establecidos por el SII para la representación impresa de facturas electrónicas, y está preparado para integrarse con los webservices oficiales del SII para el envío y validación de documentos tributarios electrónicos.

---

**Fecha de elaboración**: 8 de Octubre, 2025  
**Versión**: 1.0  
**Autor**: Sistema GestiónCloud  
**Basado en**: Resolución Exenta SII N° 80 (2014) y actualizaciones posteriores




