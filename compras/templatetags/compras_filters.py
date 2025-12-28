from django import template

register = template.Library()

@register.filter
def sum_field(queryset_or_list, field_name):
    """
    Suma un campo específico de una lista de diccionarios o queryset.
    Uso: {{ documentos|sum_field:'total' }}
    """
    try:
        total = 0
        for item in queryset_or_list:
            if isinstance(item, dict):
                value = item.get(field_name, 0)
            else:
                value = getattr(item, field_name, 0)
            
            # Convertir a número si es string
            if isinstance(value, str):
                value = float(value) if value else 0
            
            total += value
        return total
    except:
        return 0
