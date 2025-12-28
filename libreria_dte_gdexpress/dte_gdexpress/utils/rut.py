"""
Utilidades para validación y formateo de RUT chileno
"""


def limpiar_rut(rut):
    """
    Limpia un RUT eliminando puntos, guiones y espacios
    
    Args:
        rut (str): RUT a limpiar
        
    Returns:
        str: RUT limpio
    """
    if not rut:
        return ''
    return str(rut).replace('.', '').replace('-', '').replace(' ', '').upper()


def calcular_digito_verificador(rut_sin_dv):
    """
    Calcula el dígito verificador de un RUT
    
    Args:
        rut_sin_dv (str): RUT sin dígito verificador
        
    Returns:
        str: Dígito verificador ('0'-'9' o 'K')
    """
    rut_sin_dv = str(rut_sin_dv)
    reversed_digits = map(int, reversed(rut_sin_dv))
    factors = [2, 3, 4, 5, 6, 7]
    
    s = sum(d * factors[i % 6] for i, d in enumerate(reversed_digits))
    dv = 11 - (s % 11)
    
    if dv == 11:
        return '0'
    elif dv == 10:
        return 'K'
    else:
        return str(dv)


def validar_rut(rut):
    """
    Valida un RUT chileno
    
    Args:
        rut (str): RUT a validar (puede incluir puntos y guión)
        
    Returns:
        bool: True si el RUT es válido, False en caso contrario
        
    Examples:
        >>> validar_rut('77117239-3')
        True
        >>> validar_rut('12345678-9')
        False
    """
    if not rut:
        return False
    
    rut_limpio = limpiar_rut(rut)
    
    if len(rut_limpio) < 2:
        return False
    
    rut_sin_dv = rut_limpio[:-1]
    dv = rut_limpio[-1]
    
    if not rut_sin_dv.isdigit():
        return False
    
    dv_calculado = calcular_digito_verificador(rut_sin_dv)
    
    return dv == dv_calculado


def formatear_rut(rut, con_puntos=True):
    """
    Formatea un RUT chileno
    
    Args:
        rut (str): RUT a formatear
        con_puntos (bool): Si True, incluye puntos de miles
        
    Returns:
        str: RUT formateado
        
    Examples:
        >>> formatear_rut('771172393', con_puntos=True)
        '77.117.239-3'
        >>> formatear_rut('771172393', con_puntos=False)
        '77117239-3'
    """
    if not rut:
        return ''
    
    rut_limpio = limpiar_rut(rut)
    
    if len(rut_limpio) < 2:
        return rut
    
    rut_sin_dv = rut_limpio[:-1]
    dv = rut_limpio[-1]
    
    if con_puntos:
        # Agregar puntos de miles
        rut_formateado = ''
        for i, digit in enumerate(reversed(rut_sin_dv)):
            if i > 0 and i % 3 == 0:
                rut_formateado = '.' + rut_formateado
            rut_formateado = digit + rut_formateado
        return f"{rut_formateado}-{dv}"
    else:
        return f"{rut_sin_dv}-{dv}"


def extraer_numero_rut(rut):
    """
    Extrae solo el número del RUT (sin dígito verificador)
    
    Args:
        rut (str): RUT completo
        
    Returns:
        int: Número del RUT
    """
    rut_limpio = limpiar_rut(rut)
    if len(rut_limpio) < 2:
        return 0
    return int(rut_limpio[:-1])


def extraer_dv_rut(rut):
    """
    Extrae el dígito verificador del RUT
    
    Args:
        rut (str): RUT completo
        
    Returns:
        str: Dígito verificador
    """
    rut_limpio = limpiar_rut(rut)
    if len(rut_limpio) < 2:
        return ''
    return rut_limpio[-1]
