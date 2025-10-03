from django import template
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




