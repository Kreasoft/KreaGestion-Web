from django import template

register = template.Library()

@register.filter
def currency_format(value):
    """Formatea un número con separador de miles usando punto"""
    if value is None or value == '':
        return "0"
    
    try:
        # Convertir a entero
        num = int(float(value))
        # Formatear con comas y luego reemplazar por puntos
        formatted = f"{num:,}".replace(",", ".")
        return formatted
    except (ValueError, TypeError, AttributeError):
        return "0"

@register.filter
def currency_format_coma(value):
    """Formatea un número con separador de miles usando coma (estilo estadounidense)"""
    if value is None or value == '':
        return "0"
    
    try:
        # Convertir a entero para quitar decimales
        num = int(float(value))
        # Formatear con comas
        return f"{num:,}"
    except (ValueError, TypeError, AttributeError):
        return "0"

@register.filter
def currency_format_with_symbol(value):
    """Formatea un número como moneda con símbolo $, separador de miles y sin decimales"""
    formatted = currency_format_coma(value)
    return f"${formatted}"