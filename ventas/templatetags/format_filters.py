"""
Filtros personalizados para formateo de números y montos
"""
from django import template
from decimal import Decimal

register = template.Library()


@register.filter(name='format_miles')
def format_miles(value):
    """
    Formatea un número con separador de miles (punto) y sin decimales
    Ejemplo: 1000000 -> 1.000.000
    """
    try:
        # Convertir a número
        if isinstance(value, str):
            value = value.replace(',', '').replace('.', '')
        
        num = Decimal(str(value))
        
        # Redondear sin decimales
        num = int(round(num))
        
        # Formatear con separador de miles (punto)
        formatted = "{:,}".format(num).replace(',', '.')
        
        return formatted
    except (ValueError, TypeError, Decimal.InvalidOperation):
        return value


@register.filter(name='format_precio')
def format_precio(value):
    """
    Formatea un precio con separador de miles (punto) y sin decimales
    Retorna solo el número, sin símbolo de moneda
    Ejemplo: 1000000 -> 1.000.000
    """
    return format_miles(value)


@register.filter(name='format_moneda')
def format_moneda(value):
    """
    Formatea un monto con símbolo de moneda ($) y separador de miles
    Ejemplo: 1000000 -> $1.000.000
    """
    formatted = format_miles(value)
    return f"${formatted}"




