# 📘 Documentación API DTEBox - SendDocumentAsXML

## 🔗 Endpoint

**POST** `http://[ip-dtebox]/api/Core.svc/core/SendDocumentAsXML`

### Ejemplo de URL:
- **API URL Base**: `http://200.6.118.43/api/Core.svc/Core`
- **Endpoint Completo**: `http://200.6.118.43/api/Core.svc/core/SendDocumentAsXML`
- **API Key**: `0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0`

## 📋 Descripción

Envío de documentos DTE como formato XML, basado en el XML descrito en el generador de código.

## 📥 Request - Parámetros

| Campo | Tipo | Valor | Comentario |
|-------|------|-------|------------|
| `Environment` | String | `T` o `P` | Se usará `T` para Homologación y `P` para Producción |
| `Content` | Base64[] | Arreglo de bytes en Base64 | El documento XML codificado en Base64 |
| `ResolutionDate` | String | `2019-01-01` | La fecha de resolución (formato YYYY-MM-DD) |
| `ResolutionNumber` | String/Number | `20` | Número de resolución |
| `PDF417Columns` | Number | `5` | Número de la columna del PDF (opcional, puede estar vacío) |
| `PDF417Level` | Number | `2` | Número del nivel del PDF (opcional, puede estar vacío) |
| `PDF417Type` | Number | `1` | Tipo del PDF (opcional, puede estar vacío) |
| `TED` | Base64[] | Vacío o Base64 | Se envía el TED cuando se utiliza Timbraje Offline, de lo contrario se envía vacío |

## 📤 Response - Parámetros

| Campo | Tipo | Valor | Comentario |
|-------|------|-------|------------|
| `Result` | Number | `0` o `1` | Devuelve `0` cuando es satisfactorio, `1` cuando hay error |
| `Description` | String | Mensaje de error | La descripción del error. Vacío si es exitoso |
| `TED` | Base64[] | Arreglo de bytes en Base64 | Se devuelve el TED que es un arreglo de bytes en base64 |

## 🔑 Headers Requeridos

### Para XML:
```
AuthKey: [Llave de cada box]
Content-Type: application/xml
Accept: application/xml
```

### Para JSON:
```
AuthKey: [Llave de cada box]
Content-Type: application/json
Accept: application/json
```

## 📝 Ejemplos

### Ejemplo XML

```xml
<SendDocumentAsXMLRequest xmlns="http://gdexpress.cl/api">
  <Environment>T</Environment>
  <Content>PERURSB2ZXJzaW9uPSIxLjAiPgoJPEV4cG9ydGFjaW9uZXMgSUQ9IkYxODFUMTEyIj4KCQk8RW5jYWJlemFkbz4KCQkJPElkRG9jPgoJCQkJPFRpcG9EVEU+MTEyPC9UaXBvRFRFPgoJCQkJPEZvbGlvPjE4MTwvRm9saW8+CgkJCQk8RmNoRW1pcz4yMDE4LTA3LTMwPC9GY2hFbWlzaXphZG9fMjE+MDwvUGVyc29uYWxpemFkb18yMT4KCQkJCTxQZXJzb25hbGl6YWRvXzIyPjA8L1BlcnNvbmFsaXphZG9fMjI+CgkJCTwvSW1wcmVzaW9uPgoJCTwvRG9jUGVyc29uYWxpemFkbz48L1BlcnNvbmFsaXphZG9zPgo8L0RURT4=</Content>
  <ResolutionDate>2019-01-01</ResolutionDate>
  <ResolutionNumber>80</ResolutionNumber>
  <PDF417Columns></PDF417Columns>
  <PDF417Level></PDF417Level>
  <PDF417Type></PDF417Type>
  <TED></TED>
</SendDocumentAsXMLRequest>
```

### Ejemplo JSON

```json
{ 
  "Environment" : "T", 
  "Content" : "PERURSB2ZXJzaW9uPSIxLjAiPgoJPEV4cG9ydGFjaW9uZXMgSUQ9IkYxODFUMTEyIj4KCQk8RW5jYWJlemFkbz4KCQkJPElkRG9jPgoJCQkJPFRpcG9EVEU+MTEyPC9UaXBvRFRFPgoJCQkJPEZvbGlvPjE4MTwvRm9saW8+CgkJCQk8RmNoRW1pcz4yMDE4LTA3LTMwPC9GY2hFbWlzaXphZG9fMjE+MDwvUGVyc29uYWxpemFkb18yMT4KCQkJCTxQZXJzb25hbGl6YWRvXzIyPjA8L1BlcnNvbmFsaXphZG9fMjI+CgkJCTwvSW1wcmVzaW9uPgoJCTwvRG9jUGVyc29uYWxpemFkbz48L1BlcnNvbmFsaXphZG9zPgo8L0RURT4=", 
  "ResolutionDate" : "2019-01-01", 
  "ResolutionNumber" : "80", 
  "PDF417Columns" : "", 
  "PDF417Level" : "", 
  "PDF417Type" : "", 
  "TED" : "" 
}
```

## 🔧 Uso en GestionCloud

El servicio `DTEBoxService` en `facturacion_electronica/dtebox_service.py` implementa esta API.

### Configuración en la Empresa

1. Habilitar DTEBox en la configuración de la empresa
2. Configurar la URL del servidor DTEBox (ej: `http://200.6.118.43/api/Core.svc/Core`)
3. Configurar la Auth Key (ej: `0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0`)
4. Configurar el ambiente (`T` para Homologación, `P` para Producción)
5. Configurar parámetros PDF417 (opcionales)

### Ejemplo de Uso

```python
from facturacion_electronica.dtebox_service import DTEBoxService

# Inicializar servicio
dtebox_service = DTEBoxService(empresa)

# Timbrar DTE (obtener TED)
resultado = dtebox_service.timbrar_dte(xml_firmado)

if resultado['success']:
    ted = resultado['ted']
    print(f"TED obtenido exitosamente: {ted}")
else:
    print(f"Error: {resultado['error']}")
```

## ⚠️ Notas Importantes

1. **Encoding**: El XML debe estar codificado en `ISO-8859-1` antes de convertir a Base64
2. **TED Vacío**: Cuando se usa Timbraje Offline, el campo `TED` debe enviarse vacío. DTEBox generará el TED.
3. **Resultado**: 
   - `Result = 0`: Operación exitosa
   - `Result = 1`: Error (revisar `Description`)
4. **Ambiente**: 
   - `T` = Homologación (Testing)
   - `P` = Producción (Production)
5. **Resolución**: Los datos de `ResolutionDate` y `ResolutionNumber` deben coincidir con los configurados en el servidor DTEBox

## 🐛 Solución de Problemas

### Error 404
- Verificar que la URL del endpoint sea correcta
- El endpoint debe ser: `/api/Core.svc/core/SendDocumentAsXML` (con minúscula 'core')

### Error 500
- Verificar que el XML del DTE sea válido
- Verificar que los datos de resolución coincidan con los del servidor
- Verificar que el formato del request sea correcto

### Result = 1
- Revisar el campo `Description` en la respuesta para ver el error específico
- Verificar que el XML del DTE esté correctamente formado
- Verificar que los datos de resolución sean correctos

## 📚 Referencias

- Servicio implementado en: `facturacion_electronica/dtebox_service.py`
- Configuración en modelo: `empresas/models.py` (campos `dtebox_*`)







