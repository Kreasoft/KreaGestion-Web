"""
Generador de Notas de Crédito Electrónicas (Tipo 61)
"""
from .base import GeneradorDTEBase


class GeneradorNotaCredito(GeneradorDTEBase):
    """
    Generador de Notas de Crédito Electrónicas (Tipo 61)
    
    Uso:
        nota_credito = GeneradorNotaCredito(
            folio=111,
            fecha='2025-12-20',
            rut_emisor='77117239-3',
            razon_social_emisor='Mi Empresa SPA',
            direccion_emisor='Av. Principal 123',
            comuna_emisor='Santiago',
            rut_receptor='12345678-9',
            razon_social_receptor='Cliente LTDA',
            items=[
                {
                    'nombre': 'Devolución Producto A',
                    'cantidad': 1,
                    'precio': 50000,
                }
            ],
            referencias=[
                {
                    'tipo_documento': 33,  # Factura
                    'folio': 12345,
                    'fecha': '2025-12-15',
                    'razon': 'Anula factura por error',
                    'codigo_referencia': 1,  # 1=Anula, 2=Corrige monto, 3=Corrige texto
                }
            ]
        )
        
        xml = nota_credito.generar_xml()
    """
    
    def __init__(self, folio, fecha, **kwargs):
        """
        Inicializa el generador de notas de crédito
        
        Args:
            folio (int): Número de folio
            fecha: Fecha de emisión
            **kwargs: Parámetros adicionales
        """
        # Tipo de DTE 61 = Nota de Crédito Electrónica
        super().__init__(tipo_dte=61, folio=folio, fecha=fecha, **kwargs)
        
        # Validar que tenga receptor
        if not self.rut_receptor:
            raise ValueError("RUT receptor es obligatorio para notas de crédito")
        
        # Validar que tenga al menos una referencia
        if not self.referencias:
            raise ValueError("Nota de crédito debe tener al menos una referencia al documento original")
        
        # Validar que la referencia tenga los campos requeridos
        for ref in self.referencias:
            if 'tipo_documento' not in ref:
                raise ValueError("Referencia debe incluir 'tipo_documento'")
            if 'folio' not in ref:
                raise ValueError("Referencia debe incluir 'folio'")
