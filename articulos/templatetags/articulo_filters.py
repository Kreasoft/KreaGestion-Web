from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def format_price(value):
    """Formatea un precio con separadores de miles en formato chileno"""
    if not value:
        return "0"
    
    try:
        # Convertir string a decimal si es necesario
        if isinstance(value, str):
            # Remover separadores de miles existentes y convertir coma decimal a punto
            value = value.replace('.', '').replace(',', '.')
            value = Decimal(value)
        else:
            value = Decimal(str(value))
        
        # Formatear con separadores de miles
        return f"{int(value):,}".replace(',', '.')
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




