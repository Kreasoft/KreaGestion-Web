from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Filtro personalizado para obtener un item de un diccionario por su clave.
    Uso en template: {{ my_dict|get_item:my_key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)







