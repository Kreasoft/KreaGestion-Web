"""
Generador de Facturas Electrónicas (Tipo 33)
"""
from .base import GeneradorDTEBase


class GeneradorFactura(GeneradorDTEBase):
    """
    Generador de Facturas Electrónicas (Tipo 33)
    
    Uso:
        factura = GeneradorFactura(
            folio=12345,
            fecha='2025-12-20',
            rut_emisor='77117239-3',
            razon_social_emisor='Mi Empresa SPA',
            giro_emisor='Servicios de TI',
            direccion_emisor='Av. Principal 123',
            comuna_emisor='Santiago',
            rut_receptor='12345678-9',
            razon_social_receptor='Cliente LTDA',
            direccion_receptor='Calle Falsa 456',
            comuna_receptor='Providencia',
            items=[
                {
                    'nombre': 'Servicio de Desarrollo',
                    'cantidad': 1,
                    'precio': 1000000,
                }
            ]
        )
        
        xml = factura.generar_xml()
    """
    
    def __init__(self, folio, fecha, **kwargs):
        """
        Inicializa el generador de facturas
        
        Args:
            folio (int): Número de folio
            fecha: Fecha de emisión
            **kwargs: Parámetros adicionales (ver GeneradorDTEBase)
        """
        # Tipo de DTE 33 = Factura Electrónica
        super().__init__(tipo_dte=33, folio=folio, fecha=fecha, **kwargs)
        
        # Validar que tenga receptor (obligatorio para facturas)
        if not self.rut_receptor:
            raise ValueError("RUT receptor es obligatorio para facturas")
        
        if not self.razon_social_receptor:
            raise ValueError("Razón social receptor es obligatoria para facturas")
