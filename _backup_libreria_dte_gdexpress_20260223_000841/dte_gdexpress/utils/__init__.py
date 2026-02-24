"""
Módulo de utilidades para DTE GDExpress
"""

from .rut import (
    validar_rut,
    formatear_rut,
    limpiar_rut,
    calcular_digito_verificador,
    extraer_numero_rut,
    extraer_dv_rut,
)

from .montos import (
    calcular_iva,
    calcular_total,
    calcular_neto_desde_total,
    formatear_monto,
    monto_en_palabras,
)

from .validadores import (
    validar_fecha,
    validar_tipo_dte,
    validar_folio,
    validar_monto,
    validar_cantidad,
    validar_texto,
    validar_items,
    validar_ambiente,
)

__all__ = [
    # RUT
    'validar_rut',
    'formatear_rut',
    'limpiar_rut',
    'calcular_digito_verificador',
    'extraer_numero_rut',
    'extraer_dv_rut',
    
    # Montos
    'calcular_iva',
    'calcular_total',
    'calcular_neto_desde_total',
    'formatear_monto',
    'monto_en_palabras',
    
    # Validadores
    'validar_fecha',
    'validar_tipo_dte',
    'validar_folio',
    'validar_monto',
    'validar_cantidad',
    'validar_texto',
    'validar_items',
    'validar_ambiente',
]
