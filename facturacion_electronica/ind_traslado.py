"""Catálogo IndTraslado / TipoDespacho del SII para Guías de Despacho (DTE 52).

Res. Ex. 154/2025 (obligatoria desde el 1-nov-2026, Res. 52/2026):
IndTraslado 7 pasa a llamarse Devolución de Mercaderías.
"""

IND_TRASLADO_CHOICES = [
    ('1', '1 - Operación constituye venta'),
    ('2', '2 - Ventas por efectuar'),
    ('3', '3 - Consignaciones'),
    ('4', '4 - Entrega gratuita'),
    ('5', '5 - Traslados internos'),
    ('6', '6 - Otros traslados no venta'),
    ('7', '7 - Devolución de Mercaderías'),
    ('8', '8 - Traslado para exportación'),
    ('9', '9 - Ventas para exportación'),
]

TIPO_DESPACHO_SII_CHOICES = [
    ('1', '1 - Por cuenta del receptor'),
    ('2', '2 - Por cuenta del emisor al cliente'),
    ('3', '3 - Por cuenta del emisor a otras instalaciones'),
]
