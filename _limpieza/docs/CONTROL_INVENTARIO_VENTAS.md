# Control de Inventario en Ventas

## Descripción General

Se ha implementado un sistema completo de control de inventario que valida y descuenta automáticamente el stock al realizar ventas.

## Características Implementadas

### 1. Validación de Stock en POS

**Ubicación**: `ventas/views.py`

#### Función `pos_agregar_articulo`
- Valida el stock disponible antes de agregar un artículo a la venta
- Solo valida si el artículo tiene `control_stock = True`
- Considera la cantidad ya agregada en la venta actual
- Retorna error si no hay stock suficiente

```python
# Ejemplo de validación
if articulo.control_stock:
    stock_disponible = articulo.stock_disponible
    if cantidad_total > stock_disponible:
        return JsonResponse({
            'success': False, 
            'error': f'Stock insuficiente. Disponible: {stock_disponible}'
        })
```

#### Función `pos_actualizar_detalle`
- Valida el stock al modificar la cantidad de un artículo
- Previene que se aumente la cantidad más allá del stock disponible

### 2. Descuento Automático de Stock

**Ubicación**: `ventas/signals.py`

#### Señal `actualizar_stock_venta`
Se ejecuta automáticamente cuando:
- Una venta cambia su estado a `'confirmada'`
- Una venta cambia su estado a `'anulada'`

**Comportamiento**:
- **Ventas Confirmadas**: Descuenta el stock y crea movimientos de inventario tipo "salida"
- **Ventas Anuladas**: Repone el stock y crea movimientos de inventario tipo "entrada"
- **Cotizaciones**: No afectan el stock (se ignoran)

#### Función `descontar_stock_venta`
```python
# Para cada artículo en la venta:
1. Verifica que tenga control_stock = True
2. Obtiene o crea el registro de Stock en la bodega principal
3. Descuenta la cantidad vendida
4. Crea un movimiento de inventario tipo "salida"
5. Registra el número de venta como referencia
```

#### Función `reponer_stock_venta`
```python
# Para cada artículo en la venta anulada:
1. Verifica que tenga control_stock = True
2. Obtiene o crea el registro de Stock en la bodega principal
3. Repone la cantidad vendida
4. Crea un movimiento de inventario tipo "entrada" con motivo "Anulación de venta"
```

### 3. Propiedad `stock_disponible` en Artículo

**Ubicación**: `articulos/models.py`

```python
@property
def stock_disponible(self):
    """Alias de stock_actual para compatibilidad"""
    return self.stock_actual

@property
def stock_actual(self):
    """Retorna el stock actual del artículo (suma de todas las bodegas)"""
    stocks = Stock.objects.filter(articulo=self, empresa=self.empresa)
    total_stock = sum(float(stock.cantidad) for stock in stocks)
    return int(total_stock)
```

## Flujo de Trabajo

### Venta Normal (POS)

1. **Usuario agrega artículo al carrito**
   - Sistema valida stock disponible
   - Si hay stock: agrega al carrito
   - Si no hay stock: muestra error

2. **Usuario procesa la venta**
   - Se crea la venta con estado `'borrador'`
   - No se afecta el stock aún

3. **Sistema confirma la venta** (en caja)
   - Cambia estado a `'confirmada'`
   - **Señal se activa automáticamente**
   - Descuenta stock de la bodega principal
   - Crea movimientos de inventario tipo "salida"

### Anulación de Venta

1. **Usuario anula una venta**
   - Cambia estado a `'anulada'`
   - **Señal se activa automáticamente**
   - Repone stock a la bodega principal
   - Crea movimientos de inventario tipo "entrada"

### Cotizaciones

- **No afectan el stock**
- Se pueden crear sin validar disponibilidad
- Al convertir a venta, se valida el stock en ese momento

## Configuración por Artículo

Cada artículo tiene un campo `control_stock` (booleano):

- **`control_stock = True`**: Se valida y descuenta stock automáticamente
- **`control_stock = False`**: No se valida ni descuenta stock (útil para servicios)

## Modelos Relacionados

### Stock (`inventario/models.py`)
```python
- empresa: ForeignKey
- bodega: ForeignKey
- articulo: ForeignKey
- cantidad: Decimal
- stock_minimo: Decimal
- stock_maximo: Decimal
- precio_promedio: Decimal
```

### Inventario (`inventario/models.py`)
```python
- empresa: ForeignKey
- bodega_origen: ForeignKey (nullable)
- bodega_destino: ForeignKey (nullable)
- articulo: ForeignKey
- tipo_movimiento: CharField (entrada/salida/ajuste/transferencia)
- cantidad: Decimal
- precio_unitario: Decimal
- descripcion: TextField
- numero_documento: CharField
- estado: CharField
```

## Integración con Módulos

### Módulo de Ventas
- Valida stock al agregar artículos
- Crea ventas con estado borrador
- Confirma ventas desde el módulo de caja

### Módulo de Caja
- Confirma ventas (cambia estado a 'confirmada')
- Activa las señales de descuento de stock

### Módulo de Inventario
- Almacena el stock por bodega
- Registra todos los movimientos
- Proporciona reportes de stock

### Módulo de Bodegas
- Define las bodegas disponibles
- La bodega principal (primera activa) se usa para ventas

## Consideraciones Importantes

1. **Bodega Principal**: El sistema usa la primera bodega activa de la empresa para los movimientos de venta

2. **Stock Negativo**: El sistema previene stock negativo estableciendo cantidad = 0 si el descuento resulta en negativo

3. **Transacciones Atómicas**: Los descuentos de stock se realizan dentro de transacciones para garantizar consistencia

4. **Auditoría**: Todos los movimientos quedan registrados en el modelo `Inventario` con:
   - Usuario que realizó la acción
   - Fecha y hora
   - Número de documento de referencia
   - Descripción del movimiento

5. **Compatibilidad**: La propiedad `stock_disponible` es un alias de `stock_actual` para mantener compatibilidad con código existente

## Próximas Mejoras Sugeridas

1. **Selección de Bodega**: Permitir seleccionar la bodega desde la que se descuenta el stock
2. **Reserva de Stock**: Implementar reserva de stock para ventas en borrador
3. **Alertas de Stock Bajo**: Notificaciones cuando el stock llega al mínimo
4. **Reportes**: Dashboard con estado de inventario por artículo
5. **Anulación de Ventas**: Interfaz para anular ventas y reponer stock

## Testing

Para probar el sistema:

1. Crear un artículo con `control_stock = True`
2. Agregar stock inicial en el módulo de inventario
3. Crear una venta en el POS con ese artículo
4. Procesar la venta desde caja
5. Verificar que el stock se descontó correctamente
6. Revisar los movimientos de inventario creados

## Archivos Modificados/Creados

- ✅ `articulos/models.py` - Agregada propiedad `stock_disponible`
- ✅ `ventas/views.py` - Validación de stock en POS
- ✅ `ventas/signals.py` - Señales para descuento automático (NUEVO)
- ✅ `ventas/apps.py` - Registro de señales
- ✅ `CONTROL_INVENTARIO_VENTAS.md` - Documentación (NUEVO)
