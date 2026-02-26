from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag(takes_context=True)
def url_replace_sort(context, field):
    """
    Actualiza los parámetros de la URL para ordenar por un campo específico.
    Si ya se estaba ordenando por ese campo, alterna la dirección.
    """
    request = context.get('request')
    if not request:
        return ''
    
    dict_ = request.GET.copy()
    
    current_sort = dict_.get('sort')
    current_direction = dict_.get('direction', 'asc')
    
    if current_sort == field:
        # Alternar dirección
        dict_['direction'] = 'desc' if current_direction == 'asc' else 'asc'
    else:
        # Nuevo campo, por defecto ascendente
        dict_['sort'] = field
        dict_['direction'] = 'asc'
    
    return dict_.urlencode()

@register.simple_tag(takes_context=True)
def get_sort_icon(context, field):
    """
    Retorna el icono de FontAwesome correspondiente al estado actual del ordenamiento.
    """
    request = context.get('request')
    if not request:
        return ''
    
    sort = request.GET.get('sort')
    direction = request.GET.get('direction', 'asc')
    
    if sort == field:
        if direction == 'asc':
            return mark_safe('<i class="fas fa-sort-alpha-down ms-1"></i>')
        else:
            return mark_safe('<i class="fas fa-sort-alpha-up-alt ms-1"></i>')
    
    return mark_safe('<i class="fas fa-sort ms-1 opacity-25"></i>')
