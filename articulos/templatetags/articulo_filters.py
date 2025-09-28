from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def format_price(value):
    """Formatea un precio con separadores de miles en formato chileno"""
    if not value:
        return "0,00"
    
    try:
        # Convertir a Decimal si es necesario
        if isinstance(value, str):
            value = Decimal(value)
        else:
            value = Decimal(str(value))
        
        # Formatear con separadores de miles y 2 decimales
        formatted = f"{value:,.2f}"
        # Reemplazar comas de miles por puntos y punto decimal por coma
        return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
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




