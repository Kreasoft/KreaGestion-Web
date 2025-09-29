from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def format_price(value):
    """Formatea un precio con separadores de miles en formato chileno (sin decimales)"""
    if not value:
        return "0"
    
    try:
        # Convertir a Decimal si es necesario
        if isinstance(value, str):
            value = Decimal(value)
        else:
            value = Decimal(str(value))
        
        # Redondear a entero
        value = round(value)
        
        # Formatear con separadores de miles (sin decimales)
        formatted = f"{value:,}"
        # Reemplazar comas de miles por puntos
        return formatted.replace(',', '.')
    except:
        return str(value)

@register.filter
def format_percentage(value):
    """Formatea un porcentaje con 2 decimales"""
    if not value:
        return "0.00"
    
    try:
        if isinstance(value, str):
            value = value.replace('.', '').replace(',', '.')
            value = float(value)
        else:
            value = float(value)
        
        return f"{value:.2f}"
    except:
        return str(value)




