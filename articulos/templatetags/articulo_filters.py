from django import template
from django.utils.safestring import mark_safe
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

@register.filter
def precio_final_con_impuestos(articulo):
    """Calcula el precio final incluyendo IVA e impuesto específico"""
    if not articulo:
        return "0"
    
    try:
        # Obtener precio neto correctamente
        precio_neto = float(articulo.precio_venta)
        
        # Calcular IVA (19%)
        iva = precio_neto * 0.19
        
        # Calcular impuesto específico si existe
        impuesto_especifico = 0.0
        if hasattr(articulo, 'categoria') and articulo.categoria and articulo.categoria.impuesto_especifico:
            # Usar el método get_porcentaje_decimal() y dividir por 100
            porcentaje_decimal = float(articulo.categoria.impuesto_especifico.get_porcentaje_decimal()) / 100
            impuesto_especifico = precio_neto * porcentaje_decimal
        
        # Precio final = precio neto + IVA + impuesto específico
        precio_final = precio_neto + iva + impuesto_especifico
        
        # Redondear a entero
        precio_final = round(precio_final)
        
        # Formatear con separadores de miles (formato chileno)
        return f"{precio_final:,}".replace(',', '.')
    except Exception as e:
        print(f"ERROR en precio_final_con_impuestos: {e}")
        # Si hay error, devolver el precio original
        return str(int(float(articulo.precio_venta)))

@register.filter
def test_precio(articulo):
    """Template tag de prueba para verificar que funciona"""
    return "TEST-1800"

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




