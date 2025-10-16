"""
Utilidades para cálculo de precios especiales por cliente
"""
from decimal import Decimal
from django.utils import timezone
from .models import PrecioClienteArticulo


def obtener_precio_articulo(articulo, cliente=None, empresa=None):
    """
    Obtiene el precio de un artículo considerando precios especiales del cliente.
    
    Lógica de prioridad:
    1. Si NO hay cliente -> Retorna precio general del artículo
    2. Si hay cliente -> Busca precio especial activo y vigente
       - Si existe precio especial -> Retorna precio especial
       - Si NO existe -> Retorna precio general (fallback)
    
    Args:
        articulo: Instancia del modelo Articulo
        cliente: Instancia del modelo Cliente (opcional)
        empresa: Instancia del modelo Empresa (opcional, para filtrar)
    
    Returns:
        Decimal: Precio final a aplicar
    """
    # Si no hay cliente, retornar precio general
    if not cliente:
        return articulo.precio_venta
    
    # Buscar precio especial del cliente
    try:
        precio_cliente = PrecioClienteArticulo.objects.filter(
            cliente=cliente,
            articulo=articulo,
            activo=True
        )
        
        # Filtrar por empresa si se proporciona
        if empresa:
            precio_cliente = precio_cliente.filter(empresa=empresa)
        
        # Obtener el primer resultado
        precio_cliente = precio_cliente.first()
        
        # Si existe y está vigente, usar precio especial
        if precio_cliente and precio_cliente.esta_vigente():
            return precio_cliente.get_precio_final()
    
    except Exception as e:
        # En caso de error, usar precio general como fallback
        print(f"Error al obtener precio especial: {e}")
    
    # Fallback: retornar precio general
    return articulo.precio_venta


def tiene_precio_especial(articulo, cliente, empresa=None):
    """
    Verifica si un artículo tiene precio especial para un cliente.
    
    Args:
        articulo: Instancia del modelo Articulo
        cliente: Instancia del modelo Cliente
        empresa: Instancia del modelo Empresa (opcional)
    
    Returns:
        bool: True si tiene precio especial vigente, False en caso contrario
    """
    if not cliente:
        return False
    
    try:
        precio_cliente = PrecioClienteArticulo.objects.filter(
            cliente=cliente,
            articulo=articulo,
            activo=True
        )
        
        if empresa:
            precio_cliente = precio_cliente.filter(empresa=empresa)
        
        precio_cliente = precio_cliente.first()
        
        return precio_cliente is not None and precio_cliente.esta_vigente()
    
    except Exception:
        return False


def obtener_precios_multiples(articulos, cliente=None, empresa=None):
    """
    Obtiene precios para múltiples artículos de una vez (optimizado).
    
    Args:
        articulos: Lista o QuerySet de artículos
        cliente: Instancia del modelo Cliente (opcional)
        empresa: Instancia del modelo Empresa (opcional)
    
    Returns:
        dict: Diccionario {articulo_id: precio}
    """
    precios = {}
    
    # Si no hay cliente, retornar precios generales
    if not cliente:
        for articulo in articulos:
            precios[articulo.id] = articulo.precio_venta
        return precios
    
    # Obtener todos los precios especiales del cliente de una vez
    articulos_ids = [a.id for a in articulos]
    
    precios_especiales = PrecioClienteArticulo.objects.filter(
        cliente=cliente,
        articulo_id__in=articulos_ids,
        activo=True
    )
    
    if empresa:
        precios_especiales = precios_especiales.filter(empresa=empresa)
    
    # Crear diccionario de precios especiales
    precios_esp_dict = {}
    for pe in precios_especiales:
        if pe.esta_vigente():
            precios_esp_dict[pe.articulo_id] = pe.get_precio_final()
    
    # Asignar precios (especial si existe, general si no)
    for articulo in articulos:
        if articulo.id in precios_esp_dict:
            precios[articulo.id] = precios_esp_dict[articulo.id]
        else:
            precios[articulo.id] = articulo.precio_venta
    
    return precios
