"""
Filtros de format_miles para la app tesoreria.
Definición local para evitar conflicto de nombre con ventas.templatetags.format_filters
"""
from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter(name='format_number')
def format_number(value):
    try:
        if isinstance(value, str):
            value = value.replace(',', '').replace('.', '')
        num = Decimal(str(value))
        num = int(round(num))
        return "{:,}".format(num).replace(',', '.')
    except (ValueError, TypeError, InvalidOperation):
        return value


@register.filter(name='format_miles')
def format_miles(value):
    return format_number(value)


@register.filter(name='format_precio')
def format_precio(value):
    return format_number(value)


@register.filter(name='format_moneda')
def format_moneda(value):
    return f"${format_number(value)}"
