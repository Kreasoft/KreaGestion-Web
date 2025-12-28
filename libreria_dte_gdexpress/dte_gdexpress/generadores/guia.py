"""
Generador de Guías de Despacho Electrónicas (Tipo 52)
"""
from lxml import etree
from .base import GeneradorDTEBase
from ..utils import validar_texto, validar_rut, formatear_rut


class GeneradorGuia(GeneradorDTEBase):
    """
    Generador de Guías de Despacho Electrónicas (Tipo 52)
    
    Uso:
        guia = GeneradorGuia(
            folio=9999,
            fecha='2025-12-20',
            rut_emisor='77117239-3',
            razon_social_emisor='Mi Empresa SPA',
            direccion_emisor='Av. Principal 123',
            comuna_emisor='Santiago',
            rut_receptor='12345678-9',
            razon_social_receptor='Cliente LTDA',
            direccion_receptor='Calle Falsa 456',
            comuna_receptor='Providencia',
            ind_traslado=1,  # 1=Operación constituye venta
            direccion_despacho='Calle Destino 789',
            comuna_despacho='Las Condes',
            rut_chofer='98765432-1',
            nombre_chofer='Juan Pérez',
            patente='ABCD12',
            items=[...]
        )
        
        xml = guia.generar_xml()
    """
    
    def __init__(self, folio, fecha, **kwargs):
        """
        Inicializa el generador de guías de despacho
        
        Args:
            folio (int): Número de folio
            fecha: Fecha de emisión
            **kwargs: Parámetros adicionales
        """
        # Tipo de DTE 52 = Guía de Despacho Electrónica
        super().__init__(tipo_dte=52, folio=folio, fecha=fecha, **kwargs)
        
        # Datos específicos de guía de despacho
        self.ind_traslado = kwargs.get('ind_traslado', 1)  # 1=Venta, 2=Traslado interno, etc.
        self.direccion_despacho = kwargs.get('direccion_despacho', '')
        self.comuna_despacho = kwargs.get('comuna_despacho', '')
        self.ciudad_despacho = kwargs.get('ciudad_despacho', '')
        
        # Datos del transporte
        self.rut_chofer = kwargs.get('rut_chofer', '')
        self.nombre_chofer = kwargs.get('nombre_chofer', '')
        self.patente = kwargs.get('patente', '')
        
        # Validar receptor (obligatorio para guías)
        if not self.rut_receptor:
            raise ValueError("RUT receptor es obligatorio para guías de despacho")
    
    def _crear_elemento_encabezado(self):
        """
        Sobrescribe el método para agregar información específica de guías
        """
        encabezado = super()._crear_elemento_encabezado()
        
        # Agregar indicador de traslado en IdDoc
        id_doc = encabezado.find('IdDoc')
        if id_doc is not None:
            etree.SubElement(id_doc, 'IndTraslado').text = str(self.ind_traslado)
        
        # Agregar información de transporte si existe
        if self.rut_chofer or self.patente:
            transporte = etree.SubElement(encabezado, 'Transporte')
            
            if self.patente:
                etree.SubElement(transporte, 'Patente').text = self.patente[:8]
            
            if self.rut_chofer and validar_rut(self.rut_chofer):
                etree.SubElement(transporte, 'RUTTrans').text = formatear_rut(self.rut_chofer, con_puntos=False)
            
            if self.nombre_chofer:
                etree.SubElement(transporte, 'NombreTransp').text = validar_texto(
                    self.nombre_chofer, 'Nombre Chofer', max_length=40, requerido=False
                )
            
            # Dirección de destino
            if self.direccion_despacho:
                etree.SubElement(transporte, 'DirDest').text = self.direccion_despacho[:70]
            if self.comuna_despacho:
                etree.SubElement(transporte, 'CmnaDest').text = self.comuna_despacho[:20]
            if self.ciudad_despacho:
                etree.SubElement(transporte, 'CiudadDest').text = self.ciudad_despacho[:20]
        
        return encabezado
