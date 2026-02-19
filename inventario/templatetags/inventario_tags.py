from django import template
from django.db import models
from inventario.models import Stock

register = template.Library()

@register.simple_tag
def get_stock_total(articulo):
    """Obtiene el stock total de un artículo sumando todas las bodegas"""
    if not articulo or not articulo.control_stock:
        return 0
    
    try:
        total = Stock.objects.filter(articulo=articulo).aggregate(
            total=models.Sum('cantidad')
        )['total']
        return total or 0
    except:
        return 0


@register.filter(name='format_miles')
def format_miles(value):
    """
    Formatea un número con separador de miles (punto) y sin decimales
    Ejemplo: 1000000 -> 1.000.000
    """
    from decimal import Decimal
    try:
        # Convertir a número
        if isinstance(value, str):
            if not value.strip(): return '0'
            value = value.replace(',', '').replace('.', '')
            if not value: return '0'
        
        if value is None: return '0'
        
        num = Decimal(str(value))
        
        # Redondear sin decimales
        num = int(round(num))
        
        # Formatear con separador de miles (punto)
        formatted = "{:,}".format(num).replace(',', '.')
        
        return formatted
    except Exception:
        return str(value)
