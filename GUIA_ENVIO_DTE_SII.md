# Guía de Envío de DTEs al SII

## 📋 Índice
1. [Comandos Disponibles](#comandos-disponibles)
2. [Procedimiento Paso a Paso](#procedimiento-paso-a-paso)
3. [Exportación de XMLs](#exportación-de-xmls)
4. [Envío al SII](#envío-al-sii)
5. [Solución de Problemas](#solución-de-problemas)
6. [Verificación del Estado](#verificación-del-estado)

---

## 🛠️ Comandos Disponibles

### 1. Generar Documentos de Prueba

```bash
# Generar factura para una empresa específica
python manage.py generar_factura_prueba --empresa-id 3 --tipo factura

# Generar boleta
python manage.py generar_factura_prueba --empresa-id 3 --tipo boleta

# Generar guía de despacho
python manage.py generar_factura_prueba --empresa-id 3 --tipo guia

# Ayuda del comando
python manage.py generar_factura_prueba --help
```

**Qué hace**: Crea una venta completa con DTE, timbre PDF417 y XML firmado.

**Tipos disponibles**:
- `factura` (tipo DTE: 33)
- `boleta` (tipo DTE: 39)
- `guia` (tipo DTE: 52)

---

### 2. Exportar XMLs de DTEs

```bash
# Exportar un DTE específico
python manage.py exportar_xml_dte --dte-id 3

# Exportar todos los DTEs de una empresa
python manage.py exportar_xml_dte --empresa-id 3

# Exportar solo DTEs pendientes (no enviados)
python manage.py exportar_xml_dte --empresa-id 3 --pendientes

# Especificar directorio de salida
python manage.py exportar_xml_dte --empresa-id 3 --output-dir "xml_facturas"
```

**Qué hace**: Genera archivos XML firmados listos para enviar al SII.

**Ubicación de salida**: Por defecto en `xml_export/`

---

### 3. Enviar DTEs al SII

```bash
# Enviar un DTE específico
python manage.py enviar_dte_sii --dte-id 3

# Enviar todos los DTEs pendientes de una empresa
python manage.py enviar_dte_sii --empresa-id 3

# Enviar todos los DTEs pendientes de todas las empresas
python manage.py enviar_dte_sii --todos
```

**Qué hace**: Envía los DTEs al servidor del SII (certificación o producción según configuración).

---

### 4. Gestión de Folios

```bash
# Resetear folios de un CAF (SOLO PARA PRUEBAS)
python manage.py resetear_folios_caf --tipo-documento 33 --confirmacion

# Configurar modo de reutilización de folios (pruebas)
python manage.py configurar_modo_prueba --habilitar
python manage.py configurar_modo_prueba --deshabilitar
```

**Importante**: El modo de reutilización solo debe usarse en ambiente de certificación para pruebas.

---

## 📝 Procedimiento Paso a Paso

### Día 1: Preparación y Pruebas Locales

#### Paso 1: Verificar Configuración de la Empresa

```bash
python manage.py shell -c "from empresas.models import Empresa; e = Empresa.objects.get(id=3); print(f'Empresa: {e.nombre}'); print(f'RUT: {e.rut}'); print(f'Ambiente SII: {e.ambiente_sii}'); print(f'Modo reutilizacion: {e.modo_reutilizacion_folios}')"
```

**Verificar**:
- ✅ Empresa tiene certificado digital configurado
- ✅ CAF cargados para los tipos de documento necesarios (33=Factura, 39=Boleta, 52=Guía)
- ✅ Ambiente SII configurado (certificacion o produccion)

---

#### Paso 2: Generar Documentos de Prueba

```bash
# Generar factura de prueba
python manage.py generar_factura_prueba --empresa-id 3 --tipo factura

# Generar boleta de prueba
python manage.py generar_factura_prueba --empresa-id 3 --tipo boleta

# Generar guía de despacho de prueba
python manage.py generar_factura_prueba --empresa-id 3 --tipo guia
```

**Resultado esperado**:
```
DTE GENERADO EXITOSAMENTE
   ID: 3
   Tipo: Factura Electrónica / Boleta Electrónica / Guía de Despacho Electrónica
   Folio: 46 / 201 / 10
   Timbre PDF417: SÍ
   URL: http://localhost:8000/ventas/ventas/70/html/
```

---

#### Paso 3: Verificar los Documentos Generados

1. Abrir en navegador: `http://localhost:8000/ventas/ventas/[ID_VENTA]/html/`
2. Verificar que se muestre:
   - ✅ Número de folio correcto
   - ✅ Timbre PDF417 (código de barras 2D)
   - ✅ Datos de empresa y cliente
   - ✅ Totales correctos
   - ✅ Botón "Volver" funciona correctamente

**Nota**: Las boletas electrónicas también mostrarán el timbre PDF417 si tienen DTE asociado.

---

#### Paso 4: Exportar XMLs para Revisión

```bash
# Exportar el DTE generado
python manage.py exportar_xml_dte --dte-id 3 --output-dir "revision_xml"
```

**Revisar el XML**:
- Abrir el archivo XML generado en `revision_xml/`
- Verificar estructura y datos
- Confirmar que tiene firma digital (etiqueta `<ds:Signature>`)

---

### Día 2: Envío al SII

#### Paso 1: Verificar DTEs Pendientes

```bash
python manage.py shell -c "from facturacion_electronica.models import DocumentoTributarioElectronico; dtes = DocumentoTributarioElectronico.objects.filter(empresa_id=3, estado_sii='generado'); print(f'DTEs pendientes: {dtes.count()}'); [print(f'  - {dte.get_tipo_dte_display()} Folio {dte.folio}') for dte in dtes]"
```

---

#### Paso 2: Exportar XMLs Antes de Enviar (Backup)

```bash
# Crear backup de todos los XMLs pendientes
python manage.py exportar_xml_dte --empresa-id 3 --pendientes --output-dir "backup_xml_$(date +%Y%m%d)"
```

---

#### Paso 3: Enviar DTEs al SII

**Opción A: Enviar un DTE específico** (recomendado para prueba inicial)

```bash
python manage.py enviar_dte_sii --dte-id 3
```

**Opción B: Enviar todos los pendientes de la empresa**

```bash
python manage.py enviar_dte_sii --empresa-id 3
```

**Resultado esperado**:
```
DTE ENVIADO EXITOSAMENTE
Track ID: 123456789
Estado: RECIBIDO
```

---

#### Paso 4: Verificar el Estado en el SII

**Anotar el Track ID** recibido y esperar 5-10 minutos.

Consultar estado (próximamente se agregará comando para esto):
```bash
# Por ahora, verificar manualmente en el portal del SII
# https://maullin.sii.cl/cvc_cgi/dte/ee_consulta_estado_dte
```

---

## 📦 Exportación de XMLs

### Estructura de Archivos Exportados

```
xml_export/
├── [RUT]_[Nombre_Empresa]/
│   ├── DTE_33_46_20251020.xml      # Factura Folio 46
│   ├── DTE_33_47_20251020.xml      # Factura Folio 47
│   ├── DTE_39_100_20251020.xml     # Boleta Folio 100
│   └── DTE_52_10_20251020.xml      # Guía Folio 10
```

### Comandos Útiles de Exportación

```bash
# Exportar todos los DTEs (enviados y no enviados)
python manage.py exportar_xml_dte --empresa-id 3 --output-dir "xml_todos"

# Exportar solo pendientes
python manage.py exportar_xml_dte --empresa-id 3 --pendientes --output-dir "xml_pendientes"

# Exportar un DTE específico
python manage.py exportar_xml_dte --dte-id 3 --output-dir "xml_individual"
```

---

## 🚀 Envío al SII

### Ambiente de Certificación vs Producción

**Certificación** (maullin.sii.cl):
- Para pruebas
- Los DTEs NO son válidos legalmente
- Permite reutilizar folios (modo prueba)

**Producción** (palena.sii.cl):
- DTEs válidos legalmente
- Cada folio se consume permanentemente
- Requiere CAF vigente del SII

### Cambiar Ambiente

```bash
python manage.py shell -c "from empresas.models import Empresa; e = Empresa.objects.get(id=3); e.ambiente_sii = 'certificacion'; e.save(); print('Ambiente cambiado a certificación')"

python manage.py shell -c "from empresas.models import Empresa; e = Empresa.objects.get(id=3); e.ambiente_sii = 'produccion'; e.save(); print('Ambiente cambiado a producción')"
```

---

## 🔧 Solución de Problemas

### Error: "Server returned response (503)"

**Causa**: Servidor del SII temporalmente no disponible.

**Solución**:
1. Esperar 10-15 minutos
2. Intentar nuevamente
3. Verificar en [estado del SII](https://www.sii.cl)

---

### Error: "No hay folios disponibles"

**Causa**: CAF agotado para ese tipo de documento.

**Solución**:
```bash
# Verificar folios disponibles
python manage.py shell -c "from facturacion_electronica.models import ArchivoCAF; cafs = ArchivoCAF.objects.filter(empresa_id=3, estado='activo'); [print(f'{caf.get_tipo_documento_display()}: {caf.folios_disponibles()} disponibles') for caf in cafs]"

# Cargar nuevo CAF desde el admin o portal del SII
```

---

### Error: "Certificado digital vencido"

**Causa**: Certificado de firma electrónica expirado.

**Solución**:
1. Renovar certificado digital con autoridad certificadora
2. Actualizar en la empresa desde el admin
3. Verificar fecha de vigencia:

```bash
python manage.py shell -c "from empresas.models import Empresa; e = Empresa.objects.get(id=3); from facturacion_electronica.firma_electronica import FirmadorDTE; f = FirmadorDTE(e.certificado_digital.path, e.password_certificado); info = f.obtener_info_certificado(); print(info)"
```

---

### Error: "XML inválido"

**Causa**: Estructura del XML no cumple con formato SII.

**Solución**:
1. Exportar el XML: `python manage.py exportar_xml_dte --dte-id [ID]`
2. Validar en [validador del SII](https://www4.sii.cl/facturacion/validaciondte/)
3. Revisar logs de errores en el servidor

---

## 📊 Verificación del Estado

### Consultar DTEs en la Base de Datos

```bash
# Ver todos los DTEs de una empresa
python manage.py shell -c "from facturacion_electronica.models import DocumentoTributarioElectronico; dtes = DocumentoTributarioElectronico.objects.filter(empresa_id=3); [print(f'{dte.get_tipo_dte_display()} F{dte.folio} - {dte.estado_sii} - Track: {dte.track_id}') for dte in dtes]"

# Ver solo DTEs enviados
python manage.py shell -c "from facturacion_electronica.models import DocumentoTributarioElectronico; dtes = DocumentoTributarioElectronico.objects.filter(empresa_id=3, estado_sii__in=['enviado','aceptado']); print(f'DTEs enviados: {dtes.count()}')"

# Ver DTEs pendientes
python manage.py shell -c "from facturacion_electronica.models import DocumentoTributarioElectronico; dtes = DocumentoTributarioElectronico.objects.filter(empresa_id=3, estado_sii='generado'); print(f'DTEs pendientes: {dtes.count()}')"
```

---

## 📁 Ubicaciones Importantes

### Archivos Generados

| Tipo | Ubicación | Descripción |
|------|-----------|-------------|
| XMLs exportados | `xml_export/` | XMLs firmados listos para enviar |
| Timbres PDF417 | `media/dte/timbres/` | Imágenes de códigos de barras |
| CAF cargados | `media/caf/` | Archivos CAF del SII |
| Certificados | `media/certificados/` | Certificados digitales |

### Logs y Debugging

```bash
# Ver logs del servidor Django
tail -f logs/django.log

# Logs de errores específicos
grep "ERROR" logs/django.log

# Activar modo debug para más información
# En settings.py: DEBUG = True
```

---

## ✅ Checklist Pre-Envío

Antes de enviar DTEs a producción, verificar:

- [ ] Empresa tiene certificado digital válido y vigente
- [ ] CAF cargados y con folios disponibles
- [ ] Ambiente SII configurado correctamente (produccion)
- [ ] Modo reutilización deshabilitado (`modo_reutilizacion_folios = False`)
- [ ] DTEs generados con datos correctos
- [ ] Timbres PDF417 se generan correctamente
- [ ] XMLs exportados y validados
- [ ] Backup de XMLs realizado
- [ ] Pruebas exitosas en ambiente de certificación

---

## 🔐 Seguridad

### Protección del Certificado Digital

```bash
# Verificar permisos del certificado (solo lectura para el usuario del servidor)
chmod 400 media/certificados/*.pfx

# Nunca commitear certificados o contraseñas en git
# Asegurarse que estén en .gitignore
```

### Variables Sensibles

Las contraseñas de certificados deben estar en variables de entorno o en un gestor de secretos, NO en código fuente.

---

## 📞 Soporte

### Recursos del SII

- Portal SII: https://www.sii.cl
- Documentación técnica: https://www.sii.cl/factura_electronica/
- Ambiente certificación: https://maullin.sii.cl
- Ambiente producción: https://palena.sii.cl
- Validador DTE: https://www4.sii.cl/facturacion/validaciondte/

### Comandos de Ayuda

```bash
# Ver ayuda de cualquier comando
python manage.py [comando] --help

# Ejemplos:
python manage.py generar_factura_prueba --help
python manage.py exportar_xml_dte --help
python manage.py enviar_dte_sii --help
```

---

## 📝 Notas Importantes

1. **Folios en Producción**: Cada folio usado en producción se consume permanentemente. Planificar bien antes de enviar.

2. **Certificados**: Los certificados digitales tienen fecha de vencimiento. Renovar antes de que expiren.

3. **CAF Vigencia**: Los CAF también tienen fecha de vencimiento. Solicitar nuevos con anticipación.

4. **Backup**: Siempre exportar XMLs antes de operaciones masivas.

5. **Track ID**: Guardar los Track IDs para consultar estado posteriormente.

6. **Horarios SII**: El SII puede tener mantenimientos programados. Verificar horarios de disponibilidad.

---

## 🎯 Resumen de Comandos Rápidos

```bash
# Flujo completo típico:

# 1. Generar documento (factura, boleta o guía)
python manage.py generar_factura_prueba --empresa-id 3 --tipo factura
python manage.py generar_factura_prueba --empresa-id 3 --tipo boleta
python manage.py generar_factura_prueba --empresa-id 3 --tipo guia

# 2. Verificar en navegador
# http://localhost:8000/ventas/ventas/[ID]/html/

# 3. Exportar XML (backup)
python manage.py exportar_xml_dte --dte-id [ID]

# 4. Enviar al SII
python manage.py enviar_dte_sii --dte-id [ID]

# 5. Anotar Track ID para seguimiento
```

---

**Fecha de creación**: 20 de Octubre 2025  
**Última actualización**: 20 de Octubre 2025  
**Versión**: 1.0

