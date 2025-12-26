"""
Utilidades para cálculos de montos, IVA y conversión a palabras
"""


def calcular_iva(neto, tasa=19):
    """
    Calcula el IVA sobre un monto neto
    
    Args:
        neto (float): Monto neto
        tasa (int): Tasa de IVA en porcentaje (default: 19%)
        
    Returns:
        int: Monto de IVA redondeado
    """
    return round(neto * tasa / 100)


def calcular_total(neto, iva=None, exento=0):
    """
    Calcula el total de un documento
    
    Args:
        neto (float): Monto neto
        iva (float, optional): Monto de IVA. Si es None, se calcula automáticamente
        exento (float): Monto exento
        
    Returns:
        int: Total redondeado
    """
    if iva is None:
        iva = calcular_iva(neto)
    
    return round(neto + iva + exento)


def calcular_neto_desde_total(total, tasa_iva=19):
    """
    Calcula el neto a partir del total (incluye IVA)
    
    Args:
        total (float): Monto total (con IVA incluido)
        tasa_iva (int): Tasa de IVA en porcentaje
        
    Returns:
        tuple: (neto, iva)
    """
    neto = round(total / (1 + tasa_iva / 100))
    iva = total - neto
    return neto, iva


def formatear_monto(monto, separador_miles='.', separador_decimales=',', decimales=0):
    """
    Formatea un monto con separadores de miles
    
    Args:
        monto (float): Monto a formatear
        separador_miles (str): Separador de miles
        separador_decimales (str): Separador de decimales
        decimales (int): Cantidad de decimales
        
    Returns:
        str: Monto formateado
        
    Examples:
        >>> formatear_monto(1234567.89)
        '1.234.568'
        >>> formatear_monto(1234567.89, decimales=2)
        '1.234.567,89'
    """
    monto = round(monto, decimales)
    
    if decimales > 0:
        parte_entera = int(monto)
        parte_decimal = round((monto - parte_entera) * (10 ** decimales))
    else:
        parte_entera = round(monto)
        parte_decimal = None
    
    # Formatear parte entera con separadores de miles
    str_entera = str(parte_entera)
    resultado = ''
    for i, digit in enumerate(reversed(str_entera)):
        if i > 0 and i % 3 == 0:
            resultado = separador_miles + resultado
        resultado = digit + resultado
    
    # Agregar parte decimal si corresponde
    if parte_decimal is not None:
        str_decimal = str(int(parte_decimal)).zfill(decimales)
        resultado = f"{resultado}{separador_decimales}{str_decimal}"
    
    return resultado


# Diccionarios para conversión a palabras
UNIDADES = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
DECENAS = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 
           'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
ESPECIALES = {
    11: 'ONCE', 12: 'DOCE', 13: 'TRECE', 14: 'CATORCE', 15: 'QUINCE',
    16: 'DIECISEIS', 17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE',
    21: 'VEINTIUN', 22: 'VEINTIDOS', 23: 'VEINTITRES', 24: 'VEINTICUATRO',
    25: 'VEINTICINCO', 26: 'VEINTISEIS', 27: 'VEINTISIETE', 28: 'VEINTIOCHO',
    29: 'VEINTINUEVE'
}
CENTENAS = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS',
            'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']


def numero_a_palabras_hasta_999(numero):
    """
    Convierte un número de 0 a 999 en palabras
    
    Args:
        numero (int): Número a convertir
        
    Returns:
        str: Número en palabras
    """
    if numero == 0:
        return 'CERO'
    
    if numero == 100:
        return 'CIEN'
    
    # Casos especiales (11-29)
    if numero in ESPECIALES:
        return ESPECIALES[numero]
    
    centena = numero // 100
    decena = (numero % 100) // 10
    unidad = numero % 10
    
    resultado = []
    
    if centena > 0:
        resultado.append(CENTENAS[centena])
    
    if decena > 0:
        resultado.append(DECENAS[decena])
    
    if unidad > 0:
        if decena > 2:
            resultado.append('Y')
        resultado.append(UNIDADES[unidad])
    
    return ' '.join(resultado)


def monto_en_palabras(monto):
    """
    Convierte un monto en pesos chilenos a palabras
    
    Args:
        monto (float): Monto a convertir
        
    Returns:
        str: Monto en palabras
        
    Examples:
        >>> monto_en_palabras(1234567)
        'UN MILLON DOSCIENTOS TREINTA Y CUATRO MIL QUINIENTOS SESENTA Y SIETE PESOS'
    """
    monto = int(round(monto))
    
    if monto == 0:
        return 'CERO PESOS'
    
    # Dividir en millones, miles y unidades
    millones = monto // 1000000
    miles = (monto % 1000000) // 1000
    unidades = monto % 1000
    
    partes = []
    
    if millones > 0:
        if millones == 1:
            partes.append('UN MILLON')
        else:
            partes.append(f"{numero_a_palabras_hasta_999(millones)} MILLONES")
    
    if miles > 0:
        if miles == 1:
            partes.append('MIL')
        else:
            partes.append(f"{numero_a_palabras_hasta_999(miles)} MIL")
    
    if unidades > 0:
        partes.append(numero_a_palabras_hasta_999(unidades))
    
    resultado = ' '.join(partes)
    
    # Agregar "PESOS" al final
    return f"{resultado} PESOS"
