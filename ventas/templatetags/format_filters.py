"""
Filtros personalizados para formateo de números y montos
"""
from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter(name='format_miles')
def format_miles(value):
    """
    Formatea un número con separador de miles (punto) y sin decimales
    Ejemplo: 1000000 -> 1.000.000
    """
    try:
        if isinstance(value, str):
            from articulos.templatetags.articulo_filters import parse_chilean_decimal
            num = parse_chilean_decimal(value)
        else:
            num = Decimal(str(value))
        
        # Redondear sin decimales
        num = int(round(num))
        
        # Formatear con separador de miles (punto)
        formatted = "{:,}".format(num).replace(',', '.')
        
        return formatted
    except (ValueError, TypeError, InvalidOperation):
        return value


@register.filter(name='format_precio')
def format_precio(value):
    """
    Formatea un precio con separador de miles (punto) y sin decimales
    Retorna solo el número, sin símbolo de moneda
    Ejemplo: 1000000 -> 1.000.000
    """
    return format_miles(value)


@register.filter(name='format_moneda')
def format_moneda(value):
    """
    Formatea un monto con símbolo de moneda ($) y separador de miles
    Ejemplo: 1000000 -> $1.000.000
    """
    formatted = format_miles(value)
    return f"${formatted}"


@register.filter(name='glosa_visible')
def glosa_visible(value):
    """Quita prefijos internos y deja solo la observación del usuario."""
    texto = str(value or '').strip()
    if not texto:
        return ''
    if texto.lower().startswith('ticket generado automáticamente'):
        return ''
    prefijos = ('[FACTURADOR_DIRECTO]', '[MOVIL]')
    cambiado = True
    while cambiado:
        cambiado = False
        for prefijo in prefijos:
            if texto.upper().startswith(prefijo):
                texto = texto[len(prefijo):].strip()
                cambiado = True
    if texto.startswith('[MOVIL-ID:') or texto.startswith('[CIERRE]'):
        return ''
    texto_up = texto.upper()
    if texto_up.startswith('DTE RECIBIDO') or 'DATOS COINCIDEN CON LOS REGISTRADOS' in texto_up:
        return ''
    if texto_up.startswith('ENVIO PROCESADO') or texto_up.startswith('ENVÍO PROCESADO'):
        return ''
    return texto








