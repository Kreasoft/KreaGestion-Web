"""
DTE GDExpress - Paquete Python/Django para Facturación Electrónica Chilena

Este paquete proporciona todas las herramientas necesarias para implementar
facturación electrónica en Chile usando GDExpress/DTEBox.

Características:
- Generación de XML para todos los tipos de DTE
- Firma digital con certificado .pfx/.p12
- Integración con GDExpress/DTEBox
- Gestión de folios (CAF)
- Modelos Django opcionales
- Utilidades para RUT, montos, validaciones

Uso básico:
    from dte_gdexpress.generadores import GeneradorFactura
    from dte_gdexpress.firma import Firmador
    from dte_gdexpress.gdexpress import ClienteGDExpress
    
    # Generar factura
    factura = GeneradorFactura(...)
    xml = factura.generar_xml()
    
    # Firmar
    firmador = Firmador(...)
    xml_firmado = firmador.firmar(xml)
    
    # Enviar
    cliente = ClienteGDExpress(...)
    resultado = cliente.enviar_dte(xml_firmado)
"""

__version__ = '1.0.0'
__author__ = 'KreaSoft'
__email__ = 'soporte@kreasoft.cl'

# Importaciones principales para facilitar el uso
from .generadores import (
    GeneradorFactura,
    GeneradorBoleta,
    GeneradorGuia,
    GeneradorNotaCredito,
    GeneradorNotaDebito,
)

from .firma import Firmador

from .gdexpress import ClienteGDExpress

from .caf import GestorCAF

from .utils import (
    validar_rut,
    formatear_rut,
    calcular_iva,
    monto_en_palabras,
)

__all__ = [
    # Generadores
    'GeneradorFactura',
    'GeneradorBoleta',
    'GeneradorGuia',
    'GeneradorNotaCredito',
    'GeneradorNotaDebito',
    
    # Firma
    'Firmador',
    
    # GDExpress
    'ClienteGDExpress',
    
    # CAF
    'GestorCAF',
    
    # Utilidades
    'validar_rut',
    'formatear_rut',
    'calcular_iva',
    'monto_en_palabras',
]
