"""
Utilidades de validación para DTEs
"""
from datetime import date, datetime


def validar_fecha(fecha):
    """
    Valida que una fecha sea válida
    
    Args:
        fecha: Puede ser str (YYYY-MM-DD), date o datetime
        
    Returns:
        str: Fecha en formato YYYY-MM-DD
        
    Raises:
        ValueError: Si la fecha no es válida
    """
    if isinstance(fecha, str):
        try:
            datetime.strptime(fecha, '%Y-%m-%d')
            return fecha
        except ValueError:
            raise ValueError(f"Fecha inválida: {fecha}. Formato esperado: YYYY-MM-DD")
    
    elif isinstance(fecha, (date, datetime)):
        return fecha.strftime('%Y-%m-%d')
    
    else:
        raise ValueError(f"Tipo de fecha no soportado: {type(fecha)}")


def validar_tipo_dte(tipo_dte):
    """
    Valida que el tipo de DTE sea válido
    
    Args:
        tipo_dte (int): Código del tipo de DTE
        
    Returns:
        int: Código validado
        
    Raises:
        ValueError: Si el tipo de DTE no es válido
    """
    tipos_validos = [33, 34, 39, 52, 56, 61]
    
    tipo_dte = int(tipo_dte)
    
    if tipo_dte not in tipos_validos:
        raise ValueError(
            f"Tipo de DTE inválido: {tipo_dte}. "
            f"Tipos válidos: {tipos_validos}"
        )
    
    return tipo_dte


def validar_folio(folio):
    """
    Valida que el folio sea un número positivo
    
    Args:
        folio (int): Número de folio
        
    Returns:
        int: Folio validado
        
    Raises:
        ValueError: Si el folio no es válido
    """
    folio = int(folio)
    
    if folio <= 0:
        raise ValueError(f"Folio inválido: {folio}. Debe ser mayor a 0")
    
    return folio


def validar_monto(monto, nombre_campo='monto'):
    """
    Valida que un monto sea un número no negativo
    
    Args:
        monto (float): Monto a validar
        nombre_campo (str): Nombre del campo para mensajes de error
        
    Returns:
        float: Monto validado
        
    Raises:
        ValueError: Si el monto no es válido
    """
    try:
        monto = float(monto)
    except (TypeError, ValueError):
        raise ValueError(f"{nombre_campo} inválido: {monto}")
    
    if monto < 0:
        raise ValueError(f"{nombre_campo} no puede ser negativo: {monto}")
    
    return monto


def validar_cantidad(cantidad):
    """
    Valida que una cantidad sea un número positivo
    
    Args:
        cantidad (float): Cantidad a validar
        
    Returns:
        float: Cantidad validada
        
    Raises:
        ValueError: Si la cantidad no es válida
    """
    try:
        cantidad = float(cantidad)
    except (TypeError, ValueError):
        raise ValueError(f"Cantidad inválida: {cantidad}")
    
    if cantidad <= 0:
        raise ValueError(f"Cantidad debe ser mayor a 0: {cantidad}")
    
    return cantidad


def validar_texto(texto, nombre_campo, max_length=None, requerido=True):
    """
    Valida un campo de texto
    
    Args:
        texto (str): Texto a validar
        nombre_campo (str): Nombre del campo
        max_length (int, optional): Longitud máxima
        requerido (bool): Si el campo es requerido
        
    Returns:
        str: Texto validado
        
    Raises:
        ValueError: Si el texto no es válido
    """
    if texto is None or texto == '':
        if requerido:
            raise ValueError(f"{nombre_campo} es requerido")
        return ''
    
    texto = str(texto).strip()
    
    if requerido and not texto:
        raise ValueError(f"{nombre_campo} no puede estar vacío")
    
    if max_length and len(texto) > max_length:
        raise ValueError(
            f"{nombre_campo} excede la longitud máxima de {max_length} caracteres"
        )
    
    return texto


def validar_items(items):
    """
    Valida que la lista de items sea válida
    
    Args:
        items (list): Lista de items
        
    Returns:
        list: Items validados
        
    Raises:
        ValueError: Si los items no son válidos
    """
    if not items:
        raise ValueError("Debe incluir al menos un item")
    
    if not isinstance(items, list):
        raise ValueError("Items debe ser una lista")
    
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Item {i} debe ser un diccionario")
        
        # Validar campos requeridos
        if 'nombre' not in item:
            raise ValueError(f"Item {i}: falta campo 'nombre'")
        
        if 'cantidad' not in item:
            raise ValueError(f"Item {i}: falta campo 'cantidad'")
        
        if 'precio' not in item:
            raise ValueError(f"Item {i}: falta campo 'precio'")
        
        # Validar valores
        validar_cantidad(item['cantidad'])
        validar_monto(item['precio'], 'precio')
    
    return items


def validar_ambiente(ambiente):
    """
    Valida que el ambiente sea válido
    
    Args:
        ambiente (str): Ambiente ('CERTIFICACION' o 'PRODUCCION')
        
    Returns:
        str: Ambiente validado
        
    Raises:
        ValueError: Si el ambiente no es válido
    """
    ambiente = str(ambiente).upper()
    
    if ambiente not in ['CERTIFICACION', 'PRODUCCION']:
        raise ValueError(
            f"Ambiente inválido: {ambiente}. "
            "Valores válidos: 'CERTIFICACION', 'PRODUCCION'"
        )
    
    return ambiente
