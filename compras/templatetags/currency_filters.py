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
