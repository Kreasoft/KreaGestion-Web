# AUDITORÍA COMPLETA: SISTEMA DE ASIGNACIÓN DE FOLIOS

**Fecha**: 28 de diciembre de 2025
**Estado**: CRÍTICO - Problemas recurrentes con asignación de folios fuera de rango CAF

## PROBLEMA CRÍTICO IDENTIFICADO

Se detectó por segunda vez que el sistema asigna folios **FUERA DEL RANGO** autorizado por el CAF:

- **DTE Folio 18** (ID: 34) - Factura Electrónica
  - Estado: `pendiente`
  - Fecha emisión: 2025-12-28
  - **PROBLEMA**: No existe CAF que cubra el folio 18
  - CAF activo disponible: rango 47-61 (solo 2 folios usados: 47 y 48)

Este documento NO puede enviarse al SII porque no tiene un CAF válido que lo respalde.

---

## PUNTOS DE ENTRADA DONDE SE CREAN DTEs

### Análisis de código - 7 puntos identificados:

| # | Archivo | Función/Vista | Tipo DTE | Método Asignación Folio |
|---|---------|---------------|----------|-------------------------|
| 1 | `caja/views.py` | `procesar_venta()` | 33, 39, 52 | ✅ Usa `FolioService.obtener_siguiente_folio()` con validación |
| 2 | `ventas/views.py` | `pos_procesar_preventa()` | Vale (no DTE) | N/A - Solo crea preventa |
| 3 | `facturacion_electronica/services.py` | `DTEService.crear_dte_desde_venta()` | 33, 39, 52 | ⚠️ Usa `obtener_siguiente_folio()` pero código INCOMPLETO |
| 4 | `facturacion_electronica/dte_service.py` | `DTEService._crear_registro_dte()` | 33, 39, 52, 61 | ✅ Recibe folio ya asignado (no asigna) |
| 5 | `pedidos/utils_despacho.py` | `generar_guia_desde_orden_despacho()` | 52 | ⚠️ Llama directamente a `caf.obtener_siguiente_folio()` - NO usa FolioService |
| 6 | `pedidos/utils_despacho.py` | `generar_factura_desde_orden_despacho()` | 33 | ⚠️ Llama directamente a `caf.obtener_siguiente_folio()` - NO usa FolioService |
| 7 | `inventario/views_transferencias.py` | `transferencia_generar_guia()` | 52 | ⚠️ Llama directamente a `caf.obtener_siguiente_folio()` - NO usa FolioService |

---

## ANÁLISIS DETALLADO DE CADA PUNTO

### ✅ PUNTO 1: `caja/views.py` - `procesar_venta()`

**Estado**: CORRECTO (última corrección aplicada)

```python
# Líneas 1280-1290
# Usa FolioService correctamente con validación de rango
sucursal_facturacion = request.sucursal_activa if request.sucursal_activa else sucursal_principal
caf_obtenido, folio_dte, error_folio = FolioService.obtener_siguiente_folio(
    empresa=request.empresa,
    tipo_documento=tipo_doc_sii,
    sucursal=sucursal_facturacion
)

if not caf_obtenido or not folio_dte:
    # Manejo de error robusto
    ...
```

**Validación**: ✅ Tiene validación de rango en `FolioService`

---

### ⚠️ PUNTO 3: `facturacion_electronica/services.py` - `DTEService.crear_dte_desde_venta()`

**Estado**: INCOMPLETO - Código parcial

```python
# Líneas 235-260
@staticmethod
def crear_dte_desde_venta(venta, usuario=None):
    """Código incompleto - NO SE USA en producción actual"""
    # ...
    folio = FolioService.obtener_siguiente_folio(venta.empresa, tipo_doc_sii, venta.sucursal)
    # ...
```

**Problema**: Este código parece estar en desuso o incompleto. No se invoca desde ninguna parte crítica del sistema.

**Recomendación**: ELIMINAR o COMPLETAR

---

### ⚠️ PUNTO 5: `pedidos/utils_despacho.py` - `generar_guia_desde_orden_despacho()`

**Estado**: CRÍTICO - NO USA `FolioService`

```python
# Líneas 49-59
caf_disponible = ArchivoCAF.obtener_caf_activo(
    empresa=orden_despacho.empresa,
    sucursal=sucursal,
    tipo_documento='52'
)

siguiente_folio = caf_disponible.obtener_siguiente_folio()  # ← PROBLEMA
```

**Problema**: 
1. Llama directamente a `caf.obtener_siguiente_folio()` en el modelo
2. NO pasa por `FolioService` que tiene las validaciones de rango
3. NO hay validación de que el folio esté dentro del rango autorizado

**Validación actual en ArchivoCAF.obtener_siguiente_folio()**:
```python
# Solo incrementa, NO valida rango:
self.folio_actual += 1
self.folios_utilizados += 1
self.save()
return self.folio_actual
```

**🚨 FALLO CRÍTICO**: Si `folio_actual` está corrupto o fuera de rango, simplemente lo incrementa sin validar.

---

### ⚠️ PUNTO 6: `pedidos/utils_despacho.py` - `generar_factura_desde_orden_despacho()`

**Estado**: CRÍTICO - NO USA `FolioService`

```python
# Líneas 234-244
caf_disponible = ArchivoCAF.obtener_caf_activo(
    empresa=orden_despacho.empresa,
    sucursal=sucursal,
    tipo_documento='33'
)

siguiente_folio = caf_disponible.obtener_siguiente_folio()  # ← PROBLEMA
```

**Mismo problema que Punto 5**: No valida rango.

---

### ⚠️ PUNTO 7: `inventario/views_transferencias.py` - `transferencia_generar_guia()`

**Estado**: PARCIALMENTE CORRECTO - Implementa lógica de validación propia

```python
# Líneas 590-618
with transaction.atomic():
    caf = ArchivoCAF.objects.select_for_update().get(pk=caf.pk)
    
    # ✅ Tiene lógica de validación de rango y reintentos
    MAX_INTENTOS = 5
    folio = None
    for _ in range(MAX_INTENTOS):
        candidato = caf.folio_actual + 1
        if candidato > caf.folio_hasta:  # ✅ Valida límite superior
            raise ValueError("Folio fuera de rango")
        # ...
        if existe:
            caf.folio_actual = candidato
            caf.folios_utilizados += 1
            # ...
        folio = caf.obtener_siguiente_folio()
        break
```

**Estado**: Mejor que los anteriores, pero **NO centralizado** en `FolioService`.

---

## CAUSAS RAÍZ DEL PROBLEMA

### 1. **Falta de centralización**
- `FolioService` existe y tiene validaciones
- PERO solo 1 de 7 puntos lo usa correctamente
- Los demás llaman directamente a métodos del modelo `ArchivoCAF`

### 2. **Método `ArchivoCAF.obtener_siguiente_folio()` NO valida rango**

Código actual:
```python
def obtener_siguiente_folio(self):
    """Obtiene y reserva el siguiente folio disponible"""
    if self.estado != 'activo':
        raise ValueError(f"El CAF no está activo (estado: {self.estado})")
    
    if self.folios_utilizados >= self.cantidad_folios:
        raise ValueError("No hay más folios disponibles en este CAF")
    
    self.folio_actual += 1  # ← Solo incrementa, NO valida rango
    self.folios_utilizados += 1
    
    # ...
    
    self.save()
    return self.folio_actual  # ← Puede estar fuera de rango!
```

### 3. **`folio_actual` puede estar corrupto**
- Si `folio_actual` está en 18 (de un CAF anterior eliminado)
- Y el CAF activo es 47-61
- El método simplemente incrementa a 19, 20, 21... sin validar

### 4. **No hay validación al momento de crear el DTE**
- Una vez que se tiene el folio (corrupto o no), se crea el DTE
- NO hay una validación final que verifique: "¿Este folio está realmente en el rango del CAF usado?"

---

## ESTADO ACTUAL DEL CAF

```
=== CAFs ACTIVOS ===
ID: 6 | Tipo: 33 | Rango: 47-61 | Actual: 48 | Usados: 2 | Sucursal: Casa Matriz

=== DTEs RECIENTES ===
ID: 34 | Folio: 18    | Tipo: 33 | Fecha: 2025-12-28 | Estado: pendiente   ← ❌ FUERA DE RANGO
ID: 32 | Folio: 48    | Tipo: 33 | Fecha: 2025-12-28 | Estado: enviado     ← ✅ OK
ID: 28 | Folio: 56    | Tipo: 52 | Fecha: 2025-12-27 | Estado: generado    ← ✅ OK (otro CAF)
```

---

## PLAN DE CORRECCIÓN

### FASE 1: LIMPIEZA INMEDIATA (CRÍTICO)

**Objetivo**: Eliminar datos corruptos y estabilizar el sistema actual

#### Acción 1.1: Eliminar DTE folio 18
```python
DocumentoTributarioElectronico.objects.filter(
    empresa_id=1,
    tipo_dte='33',
    folio=18
).delete()
```

#### Acción 1.2: Verificar y corregir todos los CAFs
- Verificar que `folio_actual` esté dentro de `[folio_desde, folio_hasta]`
- Si está fuera, ajustar a `folio_desde - 1` (antes del primer folio válido)
- Recalcular `folios_utilizados` basándose en DTEs reales

#### Acción 1.3: Agregar validación defensiva en `ArchivoCAF.obtener_siguiente_folio()`
```python
def obtener_siguiente_folio(self):
    # ... validaciones existentes ...
    
    # NUEVO: Validar que el próximo folio esté en rango
    proximo_folio = self.folio_actual + 1
    
    if proximo_folio < self.folio_desde or proximo_folio > self.folio_hasta:
        raise ValueError(
            f"Folio {proximo_folio} fuera del rango autorizado "
            f"[{self.folio_desde}-{self.folio_hasta}] para CAF ID {self.id}"
        )
    
    self.folio_actual = proximo_folio
    # ...
```

---

### FASE 2: REFACTORIZACIÓN (IMPORTANTE)

**Objetivo**: Centralizar TODA la lógica de asignación de folios en `FolioService`

#### Acción 2.1: Fortalecer `FolioService.obtener_siguiente_folio()`
- Agregar transacción atómica con `select_for_update()`
- Agregar doble validación de rango (antes y después)
- Agregar logging detallado
- Agregar manejo de reintentos si hay conflictos

#### Acción 2.2: Refactorizar `pedidos/utils_despacho.py`
**Antes**:
```python
caf_disponible = ArchivoCAF.obtener_caf_activo(...)
siguiente_folio = caf_disponible.obtener_siguiente_folio()
```

**Después**:
```python
from facturacion_electronica.services import FolioService

caf, folio, error = FolioService.obtener_siguiente_folio(
    empresa=orden_despacho.empresa,
    tipo_documento='52',
    sucursal=sucursal
)
if error:
    raise Exception(error)
```

#### Acción 2.3: Refactorizar `inventario/views_transferencias.py`
- Eliminar la lógica custom de asignación de folios
- Usar `FolioService` centralizado

#### Acción 2.4: Eliminar o completar `facturacion_electronica/services.py::DTEService.crear_dte_desde_venta()`
- Si no se usa: ELIMINAR
- Si se usa: COMPLETAR y PROBAR

---

### FASE 3: VALIDACIÓN Y PRUEBAS (ESENCIAL)

#### Acción 3.1: Agregar validación final al crear DTE
```python
def crear_dte(..., folio, caf):
    # Validación antes de guardar
    if folio < caf.folio_desde or folio > caf.folio_hasta:
        raise ValueError(
            f"CRÍTICO: Intento de crear DTE con folio {folio} "
            f"fuera del rango del CAF [{caf.folio_desde}-{caf.folio_hasta}]"
        )
    
    dte = DocumentoTributarioElectronico.objects.create(...)
```

#### Acción 3.2: Crear tests automatizados
```python
def test_no_permite_folios_fuera_rango():
    """Test: El sistema NO debe permitir crear DTEs con folios fuera del rango CAF"""
    caf = ArchivoCAF.objects.create(
        folio_desde=100,
        folio_hasta=110,
        folio_actual=99,
        # ...
    )
    
    # Intentar asignar 11 folios (debería fallar en el 11º)
    for i in range(12):
        try:
            folio, caf_usado, error = FolioService.obtener_siguiente_folio(...)
            if folio == 111:  # Fuera de rango
                assert False, "No debió permitir folio 111"
        except ValueError as e:
            assert "fuera del rango" in str(e)
```

#### Acción 3.3: Agregar logging robusto
```python
import logging
logger = logging.getLogger('facturacion_electronica.folios')

# En cada asignación de folio
logger.info(f"Folio asignado: {folio} | CAF ID: {caf.id} | "
            f"Rango: [{caf.folio_desde}-{caf.folio_hasta}] | "
            f"Empresa: {empresa.nombre} | Sucursal: {sucursal.nombre}")
```

---

### FASE 4: MONITOREO Y ALERTAS (PREVENTIVO)

#### Acción 4.1: Comando de verificación diaria
```python
# management/commands/verificar_integridad_cafs.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        # 1. Verificar que folio_actual esté en rango
        # 2. Verificar que folios_utilizados coincida con DTEs reales
        # 3. Detectar DTEs con folios fuera de rango
        # 4. Enviar alerta si hay inconsistencias
```

#### Acción 4.2: Vista de auditoría en el admin
- Mostrar todos los CAFs con su estado
- Mostrar últimos 10 folios asignados por CAF
- Detectar y resaltar inconsistencias

---

## CRONOGRAMA ESTIMADO

| Fase | Tiempo Estimado | Prioridad |
|------|----------------|-----------|
| Fase 1: Limpieza | 2-3 horas | 🔴 CRÍTICA |
| Fase 2: Refactorización | 6-8 horas | 🟠 ALTA |
| Fase 3: Validación | 4-6 horas | 🟠 ALTA |
| Fase 4: Monitoreo | 2-3 horas | 🟡 MEDIA |
| **TOTAL** | **14-20 horas** | |

---

## RIESGOS

### Si NO se corrige:
- ❌ Documentos inválidos enviados al SII → Sanciones fiscales
- ❌ Folios duplicados → Auditorías y multas
- ❌ Pérdida de trazabilidad contable
- ❌ Sistema no confiable para producción

### Si se aplican solo parches:
- ⚠️ El problema puede reaparecer en cualquier momento
- ⚠️ Difícil de diagnosticar sin logging robusto
- ⚠️ No hay garantía de integridad a largo plazo

### Si se aplica el plan completo:
- ✅ Sistema robusto y confiable
- ✅ Fácil de mantener y extender
- ✅ Trazabilidad completa
- ✅ Preparado para producción

---

## DECISIÓN REQUERIDA

**Opción A**: Aplicar plan completo (14-20 horas de trabajo)
- ✅ Solución definitiva
- ✅ Sistema confiable
- ❌ Requiere tiempo y dedicación

**Opción B**: Solo Fase 1 (limpieza) + parches mínimos (3-4 horas)
- ✅ Rápido
- ⚠️ NO garantiza que no vuelva a pasar
- ⚠️ Sistema sigue frágil

**Opción C**: Pausar desarrollo y migrar a sistema probado
- ✅ Sin riesgo técnico
- ❌ Pérdida de inversión en desarrollo
- ❌ Limitaciones del sistema alternativo

---

## RECOMENDACIÓN TÉCNICA

**Proceder con Opción A (Plan Completo)** por las siguientes razones:

1. El problema es **ESTRUCTURAL**, no un bug puntual
2. Los parches NO son suficientes (ya se intentó y volvió a fallar)
3. La inversión de 14-20 horas es razonable vs. riesgo fiscal/legal
4. El sistema resultante será robusto y escalable
5. Es la única opción que garantiza confiabilidad en producción

**Condiciones para el éxito**:
- Trabajo continuo sin interrupciones críticas
- Pruebas exhaustivas en cada fase
- Commit después de cada fase completada
- Documentación de cada cambio

---

## PRÓXIMOS PASOS INMEDIATOS

1. ✅ Commit realizado (código actual respaldado)
2. ⏳ Revisar y aprobar este plan de auditoría
3. ⏳ Ejecutar Fase 1 (limpieza) - 2-3 horas
4. ⏳ Commit después de Fase 1
5. ⏳ Ejecutar Fase 2 (refactorización) - 6-8 horas
6. ⏳ Commit después de Fase 2
7. ⏳ Ejecutar Fase 3 (validación) - 4-6 horas
8. ⏳ Commit después de Fase 3
9. ⏳ Ejecutar Fase 4 (monitoreo) - 2-3 horas
10. ⏳ Commit final y pruebas de integración

---

**Fin del documento de auditoría**


