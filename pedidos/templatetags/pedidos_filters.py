from django import template

register = template.Library()

@register.filter(name='sin_formato')
def sin_formato(value):
    """Retorna el número sin formato, solo dígitos"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return value
