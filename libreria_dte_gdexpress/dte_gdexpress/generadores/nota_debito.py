"""
Generador de Notas de Débito Electrónicas (Tipo 56)
"""
from .base import GeneradorDTEBase


class GeneradorNotaDebito(GeneradorDTEBase):
    """
    Generador de Notas de Débito Electrónicas (Tipo 56)
    
    Uso:
        nota_debito = GeneradorNotaDebito(
            folio=222,
            fecha='2025-12-20',
            rut_emisor='77117239-3',
            razon_social_emisor='Mi Empresa SPA',
            direccion_emisor='Av. Principal 123',
            comuna_emisor='Santiago',
            rut_receptor='12345678-9',
            razon_social_receptor='Cliente LTDA',
            items=[
                {
                    'nombre': 'Intereses por mora',
                    'cantidad': 1,
                    'precio': 10000,
                }
            ],
            referencias=[
                {
                    'tipo_documento': 33,  # Factura
                    'folio': 12345,
                    'fecha': '2025-12-15',
                    'razon': 'Intereses por pago fuera de plazo',
                    'codigo_referencia': 1,
                }
            ]
        )
        
        xml = nota_debito.generar_xml()
    """
    
    def __init__(self, folio, fecha, **kwargs):
        """
        Inicializa el generador de notas de débito
        
        Args:
            folio (int): Número de folio
            fecha: Fecha de emisión
            **kwargs: Parámetros adicionales
        """
        # Tipo de DTE 56 = Nota de Débito Electrónica
        super().__init__(tipo_dte=56, folio=folio, fecha=fecha, **kwargs)
        
        # Validar que tenga receptor
        if not self.rut_receptor:
            raise ValueError("RUT receptor es obligatorio para notas de débito")
        
        # Validar que tenga al menos una referencia
        if not self.referencias:
            raise ValueError("Nota de débito debe tener al menos una referencia al documento original")
        
        # Validar que la referencia tenga los campos requeridos
        for ref in self.referencias:
            if 'tipo_documento' not in ref:
                raise ValueError("Referencia debe incluir 'tipo_documento'")
            if 'folio' not in ref:
                raise ValueError("Referencia debe incluir 'folio'")
