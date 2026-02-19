# FUNCIONALIDAD: AJUSTAR FOLIO DE CAF DESDE LA INTERFAZ WEB

## Descripción

Se ha agregado una nueva funcionalidad amigable para que usuarios no técnicos puedan ajustar manualmente el folio actual de un CAF directamente desde la interfaz web, sin necesidad de usar scripts o comandos.

---

## ¿Por qué es necesario?

En ocasiones puede ser necesario ajustar manualmente el folio actual de un CAF por:
- Corrección de errores en la asignación
- Sincronización después de eliminar DTEs de prueba
- Ajustes después de migraciones o restauraciones de respaldo

---

## ¿Cómo funciona?

### 1. Acceso
- Ir a: **Facturación Electrónica → Gestión de CAFs**
- En la lista de CAFs, cada uno tiene un botón de edición (✏️) **"Ajustar Folio"**

### 2. Modal Interactivo
Al hacer clic, se abre un modal con:

**Información del CAF:**
- Tipo de documento
- Rango autorizado por el SII
- Folio actual

**Campo de entrada:**
- Ingresar el nuevo folio actual
- Se muestra el rango válido permitido

### 3. Validaciones Automáticas en Tiempo Real

El sistema valida automáticamente:

✅ **Rango mínimo**: El folio debe ser ≥ (folio_desde - 1)  
✅ **Rango máximo**: El folio debe ser ≤ folio_hasta  
✅ **Sin conflictos**: No puede haber DTEs emitidos con folios superiores al nuevo folio

Si hay algún error, se muestra un mensaje claro explicando el problema.

### 4. Vista Previa de Cambios

Antes de guardar, el sistema muestra:
- Folio actual: `48 → 50` (ejemplo)
- Folios utilizados: `2 → 4` (se calcula automáticamente)
- Estado: `activo → agotado` (si aplica)
- **Próximo folio a asignar**: `51`

### 5. Confirmación

Se solicita confirmación final antes de aplicar los cambios.

### 6. Aplicación Segura

Los cambios se aplican en una **transacción atómica** con bloqueo del registro para evitar condiciones de carrera.

---

## Validaciones Implementadas

### Backend (Servidor):

1. **Validación de rango**:
   ```python
   if nuevo_folio < (caf.folio_desde - 1):
       # Error: Folio muy bajo
   
   if nuevo_folio > caf.folio_hasta:
       # Error: Folio excede límite autorizado
   ```

2. **Validación de conflictos**:
   ```python
   dtes_posteriores = DocumentoTributarioElectronico.objects.filter(
       caf_utilizado=caf,
       folio__gt=nuevo_folio
   ).count()
   
   if dtes_posteriores > 0:
       # Error: Hay documentos con folios mayores
   ```

3. **Cálculo automático de folios utilizados**:
   ```python
   if nuevo_folio < caf.folio_desde:
       nuevos_folios_utilizados = 0
   else:
       nuevos_folios_utilizados = nuevo_folio - caf.folio_desde + 1
   ```

4. **Actualización de estado**:
   ```python
   if nuevos_folios_utilizados >= caf.cantidad_folios:
       nuevo_estado = 'agotado'
   else:
       nuevo_estado = 'activo'
   ```

### Frontend (Interfaz):

1. **Validación en tiempo real** al escribir
2. **Indicadores visuales** (campo verde = válido, rojo = inválido)
3. **Mensajes de error claros** en español
4. **Vista previa** antes de confirmar
5. **Doble confirmación** con SweetAlert2

---

## Ejemplo de Uso

### Caso: Ajustar folio de 48 a 50

**Estado Inicial:**
- CAF: Factura Electrónica
- Rango: 47 - 61
- Folio actual: 48
- Folios utilizados: 2

**Pasos:**
1. Click en botón ✏️ "Ajustar Folio"
2. Ingresar: `50`
3. Sistema valida y muestra vista previa:
   - Folio actual: 48 → 50
   - Folios utilizados: 2 → 4
   - Próximo folio: 51
4. Click en "Guardar Cambios"
5. Confirmar
6. ✅ Éxito

**Estado Final:**
- Folio actual: 50
- Folios utilizados: 4
- Próximo folio a asignar: 51

---

## Seguridad

✅ **Transacciones atómicas**: Los cambios se aplican de forma segura  
✅ **Bloqueo de registro**: `select_for_update()` previene condiciones de carrera  
✅ **Validación doble**: Cliente (JavaScript) y servidor (Python)  
✅ **Auditoría**: Se registra en logs cada ajuste manual  
✅ **Restricciones**: No permite ajustes que causen inconsistencias

---

## Archivos Modificados

1. **`facturacion_electronica/templates/facturacion_electronica/caf_list.html`**
   - Agregado botón "Ajustar Folio" en cada fila
   - Agregado modal interactivo con validaciones
   - Agregado JavaScript para validación en tiempo real
   - Vista previa de cambios

2. **`facturacion_electronica/views_caf.py`**
   - Nueva vista: `ajustar_folio_caf()`
   - Validaciones backend
   - Respuesta JSON para AJAX
   - Logging de auditoría

3. **`facturacion_electronica/urls.py`**
   - Nueva ruta: `/caf/<id>/ajustar-folio/`

---

## Beneficios

### Para PYMEs:
✅ **No requiere conocimientos técnicos**  
✅ **Interfaz amigable y visual**  
✅ **Validaciones automáticas previenen errores**  
✅ **Vista previa antes de confirmar**  
✅ **Mensajes claros en español**

### Para el Sistema:
✅ **Seguro y robusto**  
✅ **Auditable (logs)**  
✅ **Previene inconsistencias**  
✅ **Compatible con sistema existente**

---

## Mensajes de Error Comunes

| Error | Significado | Solución |
|-------|-------------|----------|
| "El folio es menor que el mínimo permitido" | El folio ingresado es muy bajo | Usar un folio entre el rango mostrado |
| "El folio excede el máximo autorizado" | El folio ingresado es muy alto | Verificar el rango del CAF |
| "Existen documentos emitidos con folios superiores" | Hay DTEs con folios mayores | No se puede retroceder, solo avanzar |

---

## Recomendaciones

1. **Verificar antes de ajustar**: Revisar el estado actual del CAF
2. **Vista previa**: Siempre revisar la vista previa antes de confirmar
3. **Próximo folio**: Tomar nota del próximo folio que se asignará
4. **Respaldo**: Considerar respaldo antes de ajustes importantes
5. **Auditoría**: Los ajustes quedan registrados en logs del servidor

---

**Fin del documento**


