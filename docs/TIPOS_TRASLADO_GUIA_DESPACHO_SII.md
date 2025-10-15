# Tipos de Traslado para Guías de Despacho Electrónicas (SII)

## Tipos Oficiales según el Servicio de Impuestos Internos (SII) de Chile

Estos son los tipos de traslado válidos para Guías de Despacho Electrónicas (Tipo DTE 52):

### Código 1: Operación constituye venta
- **Descripción**: Venta de productos
- **Uso**: Cuando la guía documenta una venta efectiva
- **Ejemplo**: Entrega de mercadería vendida a un cliente

### Código 2: Venta por efectuar
- **Descripción**: Venta anticipada (por efectuar)
- **Uso**: Cuando se entrega mercadería antes de emitir la factura
- **Ejemplo**: Entrega en consignación que se facturará posteriormente

### Código 3: Consignaciones
- **Descripción**: Mercadería en consignación
- **Uso**: Entrega de productos en consignación a un tercero
- **Ejemplo**: Productos dejados en local de terceros para venta

### Código 4: Entrega gratuita
- **Descripción**: Devolución de productos
- **Uso**: Cuando se devuelven productos al proveedor
- **Ejemplo**: Devolución de mercadería defectuosa

### Código 5: Traslados internos
- **Descripción**: Traslado interno entre bodegas/sucursales
- **Uso**: Movimiento de inventario dentro de la misma empresa
- **Ejemplo**: Transferencia de bodega central a sucursal
- **⭐ USADO EN TRANSFERENCIAS DE INVENTARIO**

### Código 6: Otros traslados no venta
- **Descripción**: Transformación de productos
- **Uso**: Traslado para procesos de transformación
- **Ejemplo**: Envío a planta de producción

### Código 7: Guía de devolución
- **Descripción**: Entrega gratuita (muestras, promociones)
- **Uso**: Entrega sin costo de productos
- **Ejemplo**: Muestras gratis, regalos promocionales

### Código 8: Traslados para exportación
- **Descripción**: Otros traslados no clasificados
- **Uso**: Cualquier otro tipo de traslado no especificado
- **Ejemplo**: Traslados especiales

### Código 9: Venta para exportación
- **Descripción**: Traslado para exportación
- **Uso**: Movimiento de mercadería destinada a exportación
- **Ejemplo**: Traslado a zona franca o puerto

## Implementación en el Sistema

```python
TIPO_TRASLADO_CHOICES = [
    ('1', 'Operación constituye venta'),
    ('2', 'Venta por efectuar'),
    ('3', 'Consignaciones'),
    ('4', 'Entrega gratuita'),
    ('5', 'Traslados internos'),
    ('6', 'Otros traslados no venta'),
    ('7', 'Guía de devolución'),
    ('8', 'Traslados para exportación'),
    ('9', 'Venta para exportación'),
]
```

## Uso en Transferencias de Inventario

Para las transferencias de inventario entre bodegas de la misma empresa, se utiliza:
- **Tipo 5**: Traslados internos

## Referencias
- Resolución Exenta SII N° 45 del 2003
- Formato de Documentos Tributarios Electrónicos (DTE)
- Manual de Uso Guía de Despacho Electrónica SII
