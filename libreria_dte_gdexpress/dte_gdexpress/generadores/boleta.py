"""
Generador de Boletas Electrónicas (Tipo 39)
"""
from .base import GeneradorDTEBase


class GeneradorBoleta(GeneradorDTEBase):
    """
    Generador de Boletas Electrónicas (Tipo 39)
    
    Uso:
        boleta = GeneradorBoleta(
            folio=5678,
            fecha='2025-12-20',
            rut_emisor='77117239-3',
            razon_social_emisor='Mi Tienda SPA',
            giro_emisor='Venta al por menor',
            direccion_emisor='Av. Principal 789',
            comuna_emisor='Santiago',
            items=[
                {
                    'nombre': 'Producto A',
                    'cantidad': 2,
                    'precio': 15000,
                }
            ]
        )
        
        xml = boleta.generar_xml()
    """
    
    def __init__(self, folio, fecha, **kwargs):
        """
        Inicializa el generador de boletas
        
        Args:
            folio (int): Número de folio
            fecha: Fecha de emisión
            **kwargs: Parámetros adicionales (ver GeneradorDTEBase)
        """
        # Tipo de DTE 39 = Boleta Electrónica
        super().__init__(tipo_dte=39, folio=folio, fecha=fecha, **kwargs)
        
        # Para boletas, el receptor es opcional
        # Si no se especifica, se usa RUT genérico
        if not self.rut_receptor:
            self.rut_receptor = '66666666-6'  # RUT genérico para boletas
            self.razon_social_receptor = 'CONSUMIDOR FINAL'
