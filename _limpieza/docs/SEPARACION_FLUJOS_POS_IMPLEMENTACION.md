# Separación de Flujos POS - Implementación

## Problema Identificado

El POS actual tiene **DOS modos de operación distintos** pero usa el **MISMO template y lógica**, lo que causa confusión:

### Modo 1: VALE FACTURABLE (cierre_directo=False)
- Se genera SOLO un vale/documento de venta
- La forma de pago se captura **AL MOMENTO DE FACTURAR EN CAJA**, no en el POS
- Flujo: POS → Vale → Caja → Formulario con forma de pago → Emite DTE

### Modo 2: FACTURA DIRECTA (cierre_directo=True)
- Se emite DTE inmediatamente en el mismo proceso de venta
- La forma de pago se captura **EN EL POS al momento de la venta**
- Flujo: POS → Formulario con forma de pago → Emite DTE directamente

## Problema Actual

El sistema usa `procesar_venta.html` para ambos casos y tiene lógica condicional que:
1. A veces pide forma de pago cuando NO debe (modo vale)
2. A veces NO pide forma de pago cuando SÍ debe (modo factura directa)
3. Es difícil de mantener y debuggear

## Solución Implementada

### Arquitectura Propuesta

```
POS (pos.html)
    │
    ├─ Modo VALE (cierre_directo=False)
    │   └─> views_pos_procesar.procesar_venta_pos()
    │       └─> Genera vale SIN pedir forma de pago
    │       └─> Redirige a impresión de vale
    │       └─> Vuelve al POS
    │
    └─ Modo FACTURA DIRECTA (cierre_directo=True)
        └─> views_pos_procesar.procesar_venta_pos_directo()
            └─> pos_procesar_directo.html (NUEVO TEMPLATE)
            └─> Pide forma de pago
            └─> Emite DTE directamente
            └─> Imprime documento
            └─> Vuelve al POS
```

### Archivos a Crear/Modificar

#### 1. **Template Nuevo: `pos_procesar_directo.html`**
- Formulario específico para factura/boleta directa desde POS
- **SIEMPRE** muestra formas de pago (excepto guías)
- Información del ticket en panel izquierdo
- Formulario compacto en panel derecho

#### 2. **Vista Nueva: `procesar_venta_pos_directo()`**
- Muestra formulario con formas de pago
- Valida formas de pago
- Emite DTE directamente
- Redirige a impresión y vuelve al POS

#### 3. **Vista Modificada: `procesar_venta_pos()`**
- Simplificar: SOLO para modo vale
- NO pedir forma de pago
- Generar vale y redirigir a impresión

#### 4. **Template de Caja: `procesar_venta.html`**
- Se mantiene EXCLUSIVO para caja
- Procesa vales generados desde POS
- SIEMPRE pide forma de pago (excepto guías)

## Flujos Detallados

### Flujo 1: POS con VALE (cierre_directo=False)

```
1. Usuario agrega productos en POS
2. Click "Procesar Venta" → POST a pos_procesar_preventa
3. Se crea Venta con tipo_documento='vale'
4. Redirige a views_pos_procesar.procesar_venta_pos(ticket_id)
5. Vista detecta cierre_directo=False
6. Genera vale SIN pedir forma de pago
7. Marca ticket.facturado=True (para evitar duplicados)
8. Redirige a vale_html?auto=1&return_url=pos
9. Imprime vale y vuelve al POS
10. [DESPUÉS] Cajero busca vale en caja
11. Caja muestra procesar_venta.html (formas de pago)
12. Emite DTE desde caja
```

### Flujo 2: POS con FACTURA DIRECTA (cierre_directo=True)

```
1. Usuario agrega productos en POS
2. Click "Procesar Venta" → POST a pos_procesar_preventa
3. Se crea Venta temporal (puede ser tipo_documento='boleta' o 'factura')
4. Redirige a views_pos_procesar.procesar_venta_pos_directo(ticket_id)
5. Vista muestra pos_procesar_directo.html
6. Template muestra formulario con FORMAS DE PAGO
7. Usuario ingresa forma(s) de pago
8. POST → valida formas de pago
9. Emite DTE directamente (TODO: implementar)
10. Redirige a impresión y vuelve al POS
```

## Beneficios

✅ **Claridad**: Cada flujo tiene su propio template y lógica
✅ **Mantenibilidad**: Cambios en un flujo no afectan al otro
✅ **Menos errores**: Sin condicionales confusos
✅ **Fácil debugging**: Flujo explícito y trazable
✅ **Escalabilidad**: Fácil agregar nuevos modos

## Estado de Implementación

- [ ] Crear template `pos_procesar_directo.html`
- [ ] Crear vista `procesar_venta_pos_directo()`
- [ ] Modificar vista `procesar_venta_pos()` para simplificar
- [ ] Actualizar URLs para nueva vista
- [ ] Modificar `pos_procesar_preventa()` para decidir qué vista usar
- [ ] Probar flujo modo vale
- [ ] Probar flujo modo factura directa
- [ ] Documentar cambios

## Notas Técnicas

- El campo `EstacionTrabajo.cierre_directo` determina el modo
- El campo `Venta.tipo_documento_planeado` determina el tipo de DTE final
- La forma de pago es CRÍTICA solo en:
  - Modo factura directa POS
  - Al procesar vale en caja
- Las guías NO requieren forma de pago en ningún caso
