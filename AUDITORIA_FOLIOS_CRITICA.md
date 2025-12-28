# AUDITORÍA CRÍTICA: SISTEMA DE FOLIOS Y CAFS
## Fecha: 28 de Diciembre de 2025

---

## 🚨 PROBLEMA IDENTIFICADO

### Causa Raíz
El sistema tiene **DOS lugares diferentes** que crean DTEs:

1. **`facturacion_electronica/dte_service.py`** (DTEService) ✅ CORRECTO
   - Usa `FolioService.obtener_siguiente_folio()` correctamente
   - Valida que el folio esté dentro del rango del CAF
   - **ESTE CÓDIGO ES CORRECTO**

2. **`caja/views.py` (función `procesar_venta`)** ❌ INCORRECTO
   - NO usa `FolioService.obtener_siguiente_folio()`
   - Genera un número correlativo simple (1, 2, 3, 18...)
   - Usa ese número como folio del DTE **DIRECTAMENTE**
   - Ignora completamente el rango del CAF

### Líneas Problemáticas en `caja/views.py`

**Línea 1024-1036:** Genera `numero_venta` correlativo
```python
numero_venta = f"{numero:06d}"  # Genera "000001", "000018", etc.
```

**Línea 1273:** Obtiene el CAF (esto está bien)
```python
numero_venta, caf = FolioService.obtener_siguiente_folio(
    request.empresa, tipo_dte, sucursal=request.empresa.casa_matriz
)
```

**PERO...**

**Línea 1339:** Crea el DTE usando el `numero_venta` anterior (el correlativo simple) ❌
```python
dte = DocumentoTributarioElectronico.objects.create(
    empresa=request.empresa,
    tipo_dte=tipo_dte,
    folio=numero_venta,  # <-- PROBLEMA: Usa el correlativo simple, NO el folio del CAF
    caf_utilizado=caf,
    ...
)
```

**Resultado:**
- DTE Folio 18 con CAF que cubre 47-61 ← INVÁLIDO
- El SII rechazaría esto de inmediato

---

## 📋 TODOS LOS LUGARES QUE CREAN DTEs

### 1. ✅ `facturacion_electronica/dte_service.py` (DTEService)
- **Método:** `generar_dte_desde_venta()`
- **Estado:** CORRECTO - Usa `FolioService.obtener_siguiente_folio()`
- **Usado por:** Notas de crédito, notas de débito, y generación manual de DTEs

### 2. ❌ `caja/views.py` (función `procesar_venta`)
- **Método:** `procesar_venta(request, ticket_id)`
- **Estado:** INCORRECTO - Usa correlativo simple como folio
- **Usado por:** Módulo de caja al procesar tickets/vales

### 3. ⚠️ `ventas/views.py` (funciones POS)
- **Métodos:** Varios (necesita verificación detallada)
- **Estado:** DESCONOCIDO - Requiere auditoría completa
- **Usado por:** POS (punto de venta)

### 4. ⚠️ `pedidos/utils_despacho.py`
- **Método:** Generación de guías de despacho
- **Estado:** DESCONOCIDO - Requiere auditoría
- **Usado por:** Módulo de despacho

### 5. ⚠️ `inventario/views_transferencias.py`
- **Método:** Guías de traslado
- **Estado:** DESCONOCIDO - Requiere auditoría
- **Usado por:** Módulo de inventario/transferencias

---

## 🔧 PLAN DE CORRECCIÓN (Paso a Paso)

### FASE 1: LIMPIEZA DE DATOS ACTUALES (30 min)
1. **Eliminar DTE folio 18** (ID: 34) que está inválido
2. **Verificar si hay otros DTEs inválidos** (folios fuera de rangos CAF)
3. **Resetear cualquier contador corrupto**

### FASE 2: CORRECCIÓN DE `caja/views.py` (1 hora)
1. **Eliminar la generación de `numero_venta` correlativo simple** (líneas 993-1036)
2. **Mover la llamada a `FolioService.obtener_siguiente_folio()` ANTES de crear el DTE**
3. **Usar SOLO el folio devuelto por `FolioService`** como folio del DTE
4. **Eliminar TODA lógica que asigna folios manualmente**

### FASE 3: AUDITORÍA Y CORRECCIÓN DE `ventas/views.py` (2 horas)
1. **Buscar TODAS las creaciones de DTEs en el POS**
2. **Verificar si usan `FolioService` correctamente**
3. **Corregir cualquier asignación manual de folios**
4. **Asegurar que SIEMPRE se use `FolioService.obtener_siguiente_folio()`**

### FASE 4: AUDITORÍA DE OTROS MÓDULOS (1 hora)
1. **`pedidos/utils_despacho.py`:** Verificar generación de guías
2. **`inventario/views_transferencias.py`:** Verificar guías de traslado
3. **Cualquier otro lugar** que use `DocumentoTributarioElectronico.objects.create()`

### FASE 5: VALIDACIÓN ADICIONAL EN EL MODELO (30 min)
1. **Agregar validación en `DocumentoTributarioElectronico.save()`**
2. **Verificar que el folio esté SIEMPRE dentro del rango del CAF**
3. **Lanzar excepción si el folio es inválido**
4. **Esto previene que cualquier código nuevo cometa el mismo error**

### FASE 6: TESTS AUTOMATIZADOS (2 horas)
1. **Crear tests** que verifiquen asignación correcta de folios
2. **Test:** Intentar crear DTE con folio fuera de rango → debe fallar
3. **Test:** Crear 5 DTEs consecutivos → deben tener folios 47, 48, 49, 50, 51
4. **Test:** CAF se agota → debe dar error claro
5. **Test:** Dos usuarios crean DTE al mismo tiempo → no debe duplicar folios

### FASE 7: LOGGING Y MONITOREO (1 hora)
1. **Agregar logging detallado** en `FolioService.obtener_siguiente_folio()`
2. **Log:** Cada asignación de folio con timestamp, usuario, CAF usado
3. **Crear comando Django** para verificar integridad de folios
4. **Dashboard** que muestre folios usados vs disponibles en tiempo real

---

## 📊 RIESGOS IDENTIFICADOS

### 🔴 CRÍTICO - Requieren corrección inmediata
1. **`caja/views.py` línea 1339:** Usa correlativo simple como folio ← **PRIORIDAD 1**
2. **Falta validación en el modelo:** No verifica que folio esté en rango CAF
3. **No hay transaccionalidad completa:** Posible race condition en asignación de folios

### 🟡 ALTO - Requieren auditoría
1. **`ventas/views.py`:** Múltiples puntos de creación de ventas/DTEs (POS)
2. **`pedidos/utils_despacho.py`:** Generación de guías de despacho
3. **`inventario/views_transferencias.py`:** Guías de traslado

### 🟢 MEDIO - Mejoras necesarias
1. **Falta tests automatizados** que validen asignación de folios
2. **Logging insuficiente:** Difícil rastrear cuándo se asignó cada folio
3. **No hay herramienta de diagnóstico** para verificar integridad

---

## ✅ SOLUCIÓN PROPUESTA: CENTRALIZACIÓN TOTAL

### Principio: UNA SOLA FUENTE DE VERDAD

**REGLA DE ORO:**
```
NINGÚN código debe crear un DocumentoTributarioElectronico 
con folio asignado EXCEPTO DTEService o FolioService.
```

### Implementación:

1. **TODO código que necesite un DTE debe llamar a `DTEService`:**
   ```python
   from facturacion_electronica.dte_service import DTEService
   
   dte_service = DTEService(empresa)
   dte = dte_service.generar_dte_desde_venta(venta, tipo_dte='33')
   ```

2. **ELIMINAR toda lógica de folios fuera de `FolioService`:**
   - No más `numero_venta` correlativo
   - No más asignaciones manuales
   - No más `Max(numero_venta) + 1`

3. **Validación en el modelo `DocumentoTributarioElectronico`:**
   ```python
   def save(self, *args, **kwargs):
       # Verificar que el folio esté en el rango del CAF
       if self.caf_utilizado:
           if not (self.caf_utilizado.folio_desde <= self.folio <= self.caf_utilizado.folio_hasta):
               raise ValidationError(
                   f"Folio {self.folio} fuera del rango del CAF "
                   f"({self.caf_utilizado.folio_desde}-{self.caf_utilizado.folio_hasta})"
               )
       super().save(*args, **kwargs)
   ```

4. **Usar `select_for_update()` en `FolioService`:**
   ```python
   with transaction.atomic():
       caf = ArchivoCAF.objects.select_for_update().get(...)
       folio = caf.folio_actual + 1
       caf.folio_actual = folio
       caf.folios_utilizados += 1
       caf.save()
   ```

---

## 📝 CHECKLIST DE IMPLEMENTACIÓN

### Antes de empezar:
- [x] Commit de código actual (completado)
- [ ] Backup de base de datos
- [ ] Documentar estado actual de DTEs

### Fase 1: Limpieza
- [ ] Eliminar DTE folio 18
- [ ] Buscar otros DTEs inválidos
- [ ] Resetear contadores si es necesario

### Fase 2: Corrección `caja/views.py`
- [ ] Eliminar generación de `numero_venta` correlativo
- [ ] Mover llamada a `FolioService` al lugar correcto
- [ ] Usar folio devuelto por `FolioService`
- [ ] Probar con 3 tickets consecutivos

### Fase 3: Auditoría `ventas/views.py`
- [ ] Buscar todos los `DocumentoTributarioElectronico.objects.create()`
- [ ] Verificar cada uno usa `FolioService`
- [ ] Corregir los que no lo usen
- [ ] Probar POS con 3 ventas consecutivas

### Fase 4: Otros módulos
- [ ] Auditar `pedidos/utils_despacho.py`
- [ ] Auditar `inventario/views_transferencias.py`
- [ ] Corregir si es necesario

### Fase 5: Validación en modelo
- [ ] Agregar validación en `save()`
- [ ] Probar intentar crear DTE con folio inválido → debe fallar

### Fase 6: Tests
- [ ] Test: Folio fuera de rango
- [ ] Test: 5 DTEs consecutivos
- [ ] Test: CAF agotado
- [ ] Test: Concurrencia (race condition)

### Fase 7: Logging y monitoreo
- [ ] Agregar logging en `FolioService`
- [ ] Crear comando de verificación
- [ ] Dashboard de folios

### Final:
- [ ] Prueba completa end-to-end (POS → DTE → SII)
- [ ] Documentar cambios
- [ ] Commit final
- [ ] Push a repositorio

---

## ⏱️ TIEMPO ESTIMADO TOTAL: 8-10 horas

**Prioridad Máxima (CRÍTICO):** Fases 1-2 (1.5 horas)
**Alta Prioridad:** Fases 3-5 (3.5 horas)
**Media Prioridad:** Fases 6-7 (3 horas)

---

## 🎯 OBJETIVO FINAL

Al finalizar, el sistema debe garantizar que:

1. ✅ **NUNCA** se asigne un folio fuera del rango de un CAF
2. ✅ **SIEMPRE** se use `FolioService.obtener_siguiente_folio()`
3. ✅ **TODO** DTE tiene un folio válido y verificable
4. ✅ **NO HAY** race conditions en asignación de folios
5. ✅ **EXISTE** validación automática que previene errores futuros
6. ✅ **HAY** tests que verifican el funcionamiento correcto
7. ✅ **SE PUEDE** rastrear cada asignación de folio
8. ✅ **EL SISTEMA** es confiable para producción

---

## 📞 SIGUIENTE PASO INMEDIATO

**FASE 1: Limpieza de Datos**
- Ejecutar script de limpieza
- Verificar estado actual
- Preparar para correcciones

**Comando para iniciar:**
```bash
python investigar_folio_18.py
python limpiar_dte_invalido_18.py
```

---

*Documento generado automáticamente durante auditoría crítica del sistema de folios*
*Fecha: 2025-12-28*
*Auditor: AI Assistant Claude*

