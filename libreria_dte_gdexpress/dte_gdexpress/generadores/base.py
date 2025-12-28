"""
Clase base para generadores de DTE
"""
from lxml import etree
from datetime import datetime
from ..utils import (
    validar_rut, formatear_rut, extraer_numero_rut, extraer_dv_rut,
    calcular_iva, calcular_total, validar_fecha, validar_folio,
    validar_monto, validar_items, validar_texto
)


class GeneradorDTEBase:
    """
    Clase base para todos los generadores de DTE
    """
    
    # Mapeo de códigos de tipo de documento
    TIPOS_DTE = {
        33: 'Factura Electrónica',
        34: 'Factura Exenta Electrónica',
        39: 'Boleta Electrónica',
        52: 'Guía de Despacho Electrónica',
        56: 'Nota de Débito Electrónica',
        61: 'Nota de Crédito Electrónica',
    }
    
    def __init__(self, tipo_dte, folio, fecha, **kwargs):
        """
        Inicializa el generador base
        
        Args:
            tipo_dte (int): Código del tipo de DTE
            folio (int): Número de folio
            fecha: Fecha de emisión (str YYYY-MM-DD, date o datetime)
            **kwargs: Parámetros adicionales
        """
        self.tipo_dte = int(tipo_dte)
        self.folio = validar_folio(folio)
        self.fecha = validar_fecha(fecha)
        
        # Validar que el tipo de DTE esté soportado
        if self.tipo_dte not in self.TIPOS_DTE:
            raise ValueError(f"Tipo de DTE no soportado: {self.tipo_dte}")
        
        # Datos del emisor
        self.rut_emisor = kwargs.get('rut_emisor')
        self.razon_social_emisor = kwargs.get('razon_social_emisor')
        self.giro_emisor = kwargs.get('giro_emisor', '')
        self.direccion_emisor = kwargs.get('direccion_emisor', '')
        self.comuna_emisor = kwargs.get('comuna_emisor', '')
        self.ciudad_emisor = kwargs.get('ciudad_emisor', '')
        
        # Validar RUT emisor
        if not validar_rut(self.rut_emisor):
            raise ValueError(f"RUT emisor inválido: {self.rut_emisor}")
        
        # Datos del receptor (opcional para algunos tipos)
        self.rut_receptor = kwargs.get('rut_receptor')
        self.razon_social_receptor = kwargs.get('razon_social_receptor')
        self.giro_receptor = kwargs.get('giro_receptor', '')
        self.direccion_receptor = kwargs.get('direccion_receptor', '')
        self.comuna_receptor = kwargs.get('comuna_receptor', '')
        self.ciudad_receptor = kwargs.get('ciudad_receptor', '')
        
        # Items
        self.items = kwargs.get('items', [])
        validar_items(self.items)
        
        # Totales
        self.neto = 0
        self.exento = 0
        self.iva = 0
        self.total = 0
        
        # Calcular totales
        self._calcular_totales()
        
        # Forma de pago
        self.forma_pago = kwargs.get('forma_pago', '1')  # 1=Contado, 2=Crédito
        self.fecha_vencimiento = kwargs.get('fecha_vencimiento')
        
        # Observaciones
        self.observaciones = kwargs.get('observaciones', '')
        
        # Referencias (para NC, ND, etc)
        self.referencias = kwargs.get('referencias', [])
    
    def _calcular_totales(self):
        """
        Calcula los totales del documento basándose en los items
        """
        neto = 0
        exento = 0
        
        for item in self.items:
            cantidad = float(item.get('cantidad', 1))
            precio = float(item.get('precio', 0))
            descuento_monto = float(item.get('descuento_monto', 0))
            descuento_porcentaje = float(item.get('descuento_porcentaje', 0))
            
            # Calcular subtotal del item
            subtotal = cantidad * precio
            
            # Aplicar descuento
            if descuento_porcentaje > 0:
                descuento_monto = subtotal * descuento_porcentaje / 100
            
            subtotal -= descuento_monto
            
            # Guardar subtotal en el item
            item['subtotal'] = round(subtotal)
            
            # Determinar si es afecto o exento
            if item.get('exento', False) or self.tipo_dte == 34:
                exento += subtotal
            else:
                neto += subtotal
        
        self.neto = round(neto)
        self.exento = round(exento)
        self.iva = calcular_iva(self.neto)
        self.total = calcular_total(self.neto, self.iva, self.exento)
    
    def _crear_elemento_encabezado(self):
        """
        Crea el elemento Encabezado del DTE
        
        Returns:
            etree.Element: Elemento Encabezado
        """
        encabezado = etree.Element('Encabezado')
        
        # IdDoc
        id_doc = etree.SubElement(encabezado, 'IdDoc')
        etree.SubElement(id_doc, 'TipoDTE').text = str(self.tipo_dte)
        etree.SubElement(id_doc, 'Folio').text = str(self.folio)
        etree.SubElement(id_doc, 'FchEmis').text = self.fecha
        
        if self.forma_pago:
            etree.SubElement(id_doc, 'FmaPago').text = str(self.forma_pago)
        
        if self.fecha_vencimiento:
            etree.SubElement(id_doc, 'FchVenc').text = validar_fecha(self.fecha_vencimiento)
        
        # Emisor
        emisor = etree.SubElement(encabezado, 'Emisor')
        etree.SubElement(emisor, 'RUTEmisor').text = formatear_rut(self.rut_emisor, con_puntos=False)
        etree.SubElement(emisor, 'RznSoc').text = validar_texto(self.razon_social_emisor, 'Razón Social Emisor', max_length=100)
        etree.SubElement(emisor, 'GiroEmis').text = validar_texto(self.giro_emisor, 'Giro Emisor', max_length=80, requerido=False)
        
        if self.direccion_emisor:
            etree.SubElement(emisor, 'DirOrigen').text = self.direccion_emisor[:70]
        if self.comuna_emisor:
            etree.SubElement(emisor, 'CmnaOrigen').text = self.comuna_emisor[:20]
        if self.ciudad_emisor:
            etree.SubElement(emisor, 'CiudadOrigen').text = self.ciudad_emisor[:20]
        
        # Receptor (si aplica)
        if self.rut_receptor and validar_rut(self.rut_receptor):
            receptor = etree.SubElement(encabezado, 'Receptor')
            etree.SubElement(receptor, 'RUTRecep').text = formatear_rut(self.rut_receptor, con_puntos=False)
            etree.SubElement(receptor, 'RznSocRecep').text = validar_texto(self.razon_social_receptor, 'Razón Social Receptor', max_length=100)
            
            if self.giro_receptor:
                etree.SubElement(receptor, 'GiroRecep').text = self.giro_receptor[:40]
            if self.direccion_receptor:
                etree.SubElement(receptor, 'DirRecep').text = self.direccion_receptor[:70]
            if self.comuna_receptor:
                etree.SubElement(receptor, 'CmnaRecep').text = self.comuna_receptor[:20]
            if self.ciudad_receptor:
                etree.SubElement(receptor, 'CiudadRecep').text = self.ciudad_receptor[:20]
        
        # Totales
        totales = etree.SubElement(encabezado, 'Totales')
        
        if self.neto > 0:
            etree.SubElement(totales, 'MntNeto').text = str(int(self.neto))
        if self.exento > 0:
            etree.SubElement(totales, 'MntExe').text = str(int(self.exento))
        if self.iva > 0:
            etree.SubElement(totales, 'IVA').text = str(int(self.iva))
        
        etree.SubElement(totales, 'MntTotal').text = str(int(self.total))
        
        return encabezado
    
    def _crear_elemento_detalle(self):
        """
        Crea los elementos Detalle del DTE
        
        Returns:
            list: Lista de elementos Detalle
        """
        detalles = []
        
        for i, item in enumerate(self.items, 1):
            detalle = etree.Element('Detalle')
            
            etree.SubElement(detalle, 'NroLinDet').text = str(item.get('numero_linea', i))
            
            # Nombre del producto/servicio
            nombre = validar_texto(item['nombre'], f'Nombre item {i}', max_length=80)
            etree.SubElement(detalle, 'NmbItem').text = nombre
            
            # Descripción (opcional)
            if 'descripcion' in item and item['descripcion']:
                etree.SubElement(detalle, 'DscItem').text = item['descripcion'][:1000]
            
            # Cantidad
            cantidad = item.get('cantidad', 1)
            etree.SubElement(detalle, 'QtyItem').text = str(cantidad)
            
            # Unidad de medida (opcional)
            if 'unidad' in item:
                etree.SubElement(detalle, 'UnmdItem').text = item['unidad'][:4]
            
            # Precio unitario
            precio = int(round(float(item['precio'])))
            etree.SubElement(detalle, 'PrcItem').text = str(precio)
            
            # Descuento (opcional)
            if item.get('descuento_monto', 0) > 0 or item.get('descuento_porcentaje', 0) > 0:
                descuento_monto = item.get('descuento_monto', 0)
                if descuento_monto == 0 and item.get('descuento_porcentaje', 0) > 0:
                    descuento_monto = cantidad * precio * item['descuento_porcentaje'] / 100
                
                etree.SubElement(detalle, 'DescuentoMonto').text = str(int(round(descuento_monto)))
            
            # Monto total del item
            etree.SubElement(detalle, 'MontoItem').text = str(int(item['subtotal']))
            
            detalles.append(detalle)
        
        return detalles
    
    def _crear_elemento_referencias(self):
        """
        Crea los elementos Referencia del DTE (para NC, ND, etc)
        
        Returns:
            list: Lista de elementos Referencia
        """
        referencias_xml = []
        
        for i, ref in enumerate(self.referencias, 1):
            referencia = etree.Element('Referencia')
            
            etree.SubElement(referencia, 'NroLinRef').text = str(i)
            etree.SubElement(referencia, 'TpoDocRef').text = str(ref['tipo_documento'])
            etree.SubElement(referencia, 'FolioRef').text = str(ref['folio'])
            
            if 'fecha' in ref:
                etree.SubElement(referencia, 'FchRef').text = validar_fecha(ref['fecha'])
            
            if 'razon' in ref:
                etree.SubElement(referencia, 'RazonRef').text = ref['razon'][:90]
            
            if 'codigo_referencia' in ref:
                etree.SubElement(referencia, 'CodRef').text = str(ref['codigo_referencia'])
            
            referencias_xml.append(referencia)
        
        return referencias_xml
    
    def generar_xml(self):
        """
        Genera el XML del DTE
        
        Returns:
            str: XML del DTE como string
        """
        # Crear elemento raíz DTE
        dte = etree.Element('DTE', version='1.0')
        documento = etree.SubElement(dte, 'Documento', ID=f'DTE-{self.tipo_dte}-{self.folio}')
        
        # Agregar Encabezado
        documento.append(self._crear_elemento_encabezado())
        
        # Agregar Detalles
        for detalle in self._crear_elemento_detalle():
            documento.append(detalle)
        
        # Agregar Referencias (si existen)
        for referencia in self._crear_elemento_referencias():
            documento.append(referencia)
        
        # Convertir a string con formato
        xml_string = etree.tostring(
            dte,
            pretty_print=True,
            xml_declaration=True,
            encoding='ISO-8859-1'
        ).decode('ISO-8859-1')
        
        return xml_string
    
    def __str__(self):
        return f"{self.TIPOS_DTE[self.tipo_dte]} #{self.folio} - ${self.total:,.0f}"
