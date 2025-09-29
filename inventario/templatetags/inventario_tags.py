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
