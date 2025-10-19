"""
Generador de XML para Documentos Tributarios Electrónicos (DTE)
Según formato oficial del SII de Chile
"""
from lxml import etree
from datetime import datetime
from decimal import Decimal
from django.utils import timezone


class DTEXMLGenerator:
    """Generador de XML para DTE según formato SII"""
    
    # Namespace del SII
    NS_SII = "http://www.sii.cl/SiiDte"
    
    def __init__(self, empresa, venta, tipo_dte, folio, caf):
        """
        Inicializa el generador de DTE
        
        Args:
            empresa: Instancia de Empresa
            venta: Instancia de Venta
            tipo_dte: Código del tipo de DTE (33, 39, etc.)
            folio: Número de folio asignado
            caf: Instancia de ArchivoCAF
        """
        self.empresa = empresa
        self.venta = venta
        self.tipo_dte = tipo_dte
        self.folio = folio
        self.caf = caf
        
    def generar_xml(self):
        """
        Genera el XML completo del DTE
        
        Returns:
            str: XML del DTE sin firmar
        """
        # Crear el documento raíz
        root = etree.Element("DTE", version="1.0", nsmap={None: self.NS_SII})
        
        # Agregar el documento según el tipo
        if self.tipo_dte in ['33', '34']:  # Facturas
            documento = self._generar_factura(root)
        elif self.tipo_dte in ['39', '41']:  # Boletas
            documento = self._generar_boleta(root)
        elif self.tipo_dte == '52':  # Guía de Despacho
            documento = self._generar_guia(root)
        elif self.tipo_dte == '56':  # Nota de Débito
            documento = self._generar_nota_debito(root)
        elif self.tipo_dte == '61':  # Nota de Crédito
            documento = self._generar_nota_credito(root)
        else:
            raise ValueError(f"Tipo de DTE no soportado: {self.tipo_dte}")
        
        # Convertir a string con formato
        xml_string = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='ISO-8859-1'
        ).decode('ISO-8859-1')
        
        return xml_string
    
    def _generar_factura(self, root):
        """Genera XML para Factura Electrónica (33) o Factura Exenta (34)"""
        documento = etree.SubElement(root, "Documento", ID=f"F{self.folio}")
        
        # Encabezado
        encabezado = self._generar_encabezado(documento)
        
        # Totales
        self._generar_totales(encabezado)
        
        # Detalles (items de la venta)
        self._generar_detalles(documento)
        
        # Referencia (si aplica)
        if hasattr(self.venta, 'documento_referencia') and self.venta.documento_referencia:
            self._generar_referencia(documento)
        
        # TED (Timbre Electrónico) - se agregará después de firmar
        
        return documento
    
    def _generar_boleta(self, root):
        """Genera XML para Boleta Electrónica (39) o Boleta Exenta (41)"""
        documento = etree.SubElement(root, "Documento", ID=f"B{self.folio}")
        
        # Encabezado
        encabezado = self._generar_encabezado(documento)
        
        # Totales
        self._generar_totales(encabezado)
        
        # Detalles
        self._generar_detalles(documento)
        
        return documento
    
    def _generar_guia(self, root):
        """Genera XML para Guía de Despacho Electrónica (52)"""
        documento = etree.SubElement(root, "Documento", ID=f"G{self.folio}")
        
        # Encabezado con datos de transporte
        encabezado = self._generar_encabezado(documento, incluir_transporte=True)
        
        # Totales
        self._generar_totales(encabezado)
        
        # Detalles
        self._generar_detalles(documento)
        
        return documento
    
    def _generar_nota_credito(self, root):
        """Genera XML para Nota de Crédito Electrónica (61)"""
        documento = etree.SubElement(root, "Documento", ID=f"NC{self.folio}")
        
        # Encabezado
        encabezado = self._generar_encabezado(documento)
        
        # Referencia al documento original (OBLIGATORIO)
        self._generar_referencia(documento, obligatorio=True)
        
        # Totales
        self._generar_totales(encabezado)
        
        # Detalles
        self._generar_detalles(documento)
        
        return documento
    
    def _generar_nota_debito(self, root):
        """Genera XML para Nota de Débito Electrónica (56)"""
        documento = etree.SubElement(root, "Documento", ID=f"ND{self.folio}")
        
        # Encabezado
        encabezado = self._generar_encabezado(documento)
        
        # Referencia al documento original (OBLIGATORIO)
        self._generar_referencia(documento, obligatorio=True)
        
        # Totales
        self._generar_totales(encabezado)
        
        # Detalles
        self._generar_detalles(documento)
        
        return documento
    
    def _generar_encabezado(self, documento, incluir_transporte=False):
        """Genera el encabezado del DTE"""
        encabezado = etree.SubElement(documento, "Encabezado")
        
        # IdDoc - Identificación del Documento
        id_doc = etree.SubElement(encabezado, "IdDoc")
        etree.SubElement(id_doc, "TipoDTE").text = self.tipo_dte
        etree.SubElement(id_doc, "Folio").text = str(self.folio)
        etree.SubElement(id_doc, "FchEmis").text = self.venta.fecha.strftime('%Y-%m-%d')
        
        # Indicador de servicio (solo para facturas de servicios)
        if self.tipo_dte in ['33', '34']:
            etree.SubElement(id_doc, "IndServicio").text = "3"  # 3 = Servicios y productos
        
        # Forma de pago
        if hasattr(self.venta, 'forma_pago'):
            forma_pago = "1" if self.venta.forma_pago == 'contado' else "2"
            etree.SubElement(id_doc, "FmaPago").text = forma_pago
        
        # Fecha de vencimiento (si es crédito)
        if hasattr(self.venta, 'fecha_vencimiento') and self.venta.fecha_vencimiento:
            etree.SubElement(id_doc, "FchVenc").text = self.venta.fecha_vencimiento.strftime('%Y-%m-%d')
        
        # Emisor
        self._generar_emisor(encabezado)
        
        # Receptor
        self._generar_receptor(encabezado)
        
        # Transporte (solo para guías de despacho)
        if incluir_transporte:
            self._generar_transporte(encabezado)
        
        return encabezado
    
    def _generar_emisor(self, encabezado):
        """Genera datos del emisor"""
        emisor = etree.SubElement(encabezado, "Emisor")
        
        # RUT sin puntos, con guión
        rut_emisor = self.empresa.rut.replace('.', '')
        etree.SubElement(emisor, "RUTEmisor").text = rut_emisor
        
        # Razón Social
        razon_social = self.empresa.razon_social_sii or self.empresa.razon_social
        etree.SubElement(emisor, "RznSoc").text = razon_social[:100]  # Máximo 100 caracteres
        
        # Giro
        giro = self.empresa.giro_sii or self.empresa.giro or "Comercio"
        etree.SubElement(emisor, "GiroEmis").text = giro[:80]  # Máximo 80 caracteres
        
        # Actividad Económica
        if self.empresa.codigo_actividad_economica:
            etree.SubElement(emisor, "Acteco").text = self.empresa.codigo_actividad_economica
        
        # Dirección
        direccion = self.empresa.direccion_casa_matriz or self.empresa.direccion
        if direccion:
            etree.SubElement(emisor, "DirOrigen").text = direccion[:70]
        
        # Comuna
        comuna = self.empresa.comuna_casa_matriz or self.empresa.comuna
        if comuna:
            etree.SubElement(emisor, "CmnaOrigen").text = comuna[:20]
        
        # Ciudad
        ciudad = self.empresa.ciudad_casa_matriz or self.empresa.ciudad
        if ciudad:
            etree.SubElement(emisor, "CiudadOrigen").text = ciudad[:20]
        
    def _generar_receptor(self, encabezado):
        """Genera datos del receptor"""
        receptor = etree.SubElement(encabezado, "Receptor")
        
        # Si es boleta y no hay cliente, usar datos genéricos
        if self.tipo_dte in ['39', '41'] and not self.venta.cliente:
            etree.SubElement(receptor, "RUTRecep").text = "66666666-6"
            etree.SubElement(receptor, "RznSocRecep").text = "Cliente Genérico"
            return
        
        # Cliente específico
        if self.venta.cliente:
            cliente = self.venta.cliente
            
            # RUT
            rut_receptor = cliente.rut.replace('.', '')
            etree.SubElement(receptor, "RUTRecep").text = rut_receptor
            
            # Razón Social
            razon_social = cliente.razon_social or cliente.nombre
            etree.SubElement(receptor, "RznSocRecep").text = razon_social[:100]
            
            # Giro
            if hasattr(cliente, 'giro') and cliente.giro:
                etree.SubElement(receptor, "GiroRecep").text = cliente.giro[:40]
            
            # Dirección
            if cliente.direccion:
                etree.SubElement(receptor, "DirRecep").text = cliente.direccion[:70]
            
            # Comuna
            if cliente.comuna:
                etree.SubElement(receptor, "CmnaRecep").text = cliente.comuna[:20]
            
            # Ciudad
            if hasattr(cliente, 'ciudad') and cliente.ciudad:
                etree.SubElement(receptor, "CiudadRecep").text = cliente.ciudad[:20]
    
    def _generar_totales(self, encabezado):
        """Genera los totales del documento"""
        totales = etree.SubElement(encabezado, "Totales")
        
        # Monto Neto
        if self.tipo_dte not in ['34', '41']:  # No exentos
            monto_neto = int(round(float(self.venta.subtotal)))
            etree.SubElement(totales, "MntNeto").text = str(monto_neto)
        
        # Monto Exento
        if self.tipo_dte in ['34', '41']:  # Documentos exentos
            monto_exento = int(round(float(self.venta.total)))
            etree.SubElement(totales, "MntExe").text = str(monto_exento)
        
        # IVA
        if self.tipo_dte not in ['34', '41']:
            monto_iva = int(round(float(self.venta.iva)))
            etree.SubElement(totales, "IVA").text = str(monto_iva)
        
        # Monto Total
        monto_total = int(round(float(self.venta.total)))
        etree.SubElement(totales, "MntTotal").text = str(monto_total)
    
    def _generar_detalles(self, documento):
        """Genera los detalles (items) del documento"""
        for index, item in enumerate(self.venta.items.all(), start=1):
            detalle = etree.SubElement(documento, "Detalle")
            
            # Número de línea
            etree.SubElement(detalle, "NroLinDet").text = str(index)
            
            # Indicador de exención (solo si es documento exento)
            if self.tipo_dte in ['34', '41']:
                etree.SubElement(detalle, "IndExe").text = "1"
            
            # Nombre del item
            nombre_item = item.articulo.nombre if hasattr(item, 'articulo') else item.descripcion
            etree.SubElement(detalle, "NmbItem").text = nombre_item[:80]
            
            # Descripción adicional (opcional)
            if hasattr(item, 'descripcion') and item.descripcion:
                etree.SubElement(detalle, "DscItem").text = item.descripcion[:1000]
            
            # Cantidad
            cantidad = float(item.cantidad)
            etree.SubElement(detalle, "QtyItem").text = f"{cantidad:.4f}"
            
            # Unidad de medida
            unidad = "UN"  # Por defecto unidad
            if hasattr(item, 'articulo') and hasattr(item.articulo, 'unidad_medida'):
                unidad = item.articulo.unidad_medida.codigo_sii or "UN"
            etree.SubElement(detalle, "UnmdItem").text = unidad
            
            # Precio unitario
            precio_unitario = int(round(float(item.precio_unitario)))
            etree.SubElement(detalle, "PrcItem").text = str(precio_unitario)
            
            # Monto total del item
            monto_item = int(round(float(item.subtotal)))
            etree.SubElement(detalle, "MontoItem").text = str(monto_item)
    
    def _generar_transporte(self, encabezado):
        """Genera información de transporte (para guías de despacho)"""
        transporte = etree.SubElement(encabezado, "Transporte")
        
        # Patente del vehículo
        if hasattr(self.venta, 'patente_vehiculo') and self.venta.patente_vehiculo:
            etree.SubElement(transporte, "Patente").text = self.venta.patente_vehiculo[:8]
        
        # RUT del transportista
        if hasattr(self.venta, 'rut_transportista') and self.venta.rut_transportista:
            etree.SubElement(transporte, "RUTTrans").text = self.venta.rut_transportista
        
        # Dirección de destino
        if hasattr(self.venta, 'direccion_destino') and self.venta.direccion_destino:
            etree.SubElement(transporte, "DirDest").text = self.venta.direccion_destino[:70]
        
        # Comuna de destino
        if hasattr(self.venta, 'comuna_destino') and self.venta.comuna_destino:
            etree.SubElement(transporte, "CmnaDest").text = self.venta.comuna_destino[:20]
    
    def _generar_referencia(self, documento, obligatorio=False):
        """Genera referencias a otros documentos"""
        # Para notas de crédito/débito debe referenciar el documento original
        if hasattr(self.venta, 'documento_referencia') and self.venta.documento_referencia:
            ref = self.venta.documento_referencia
            
            referencia = etree.SubElement(documento, "Referencia")
            
            # Número de línea de referencia
            etree.SubElement(referencia, "NroLinRef").text = "1"
            
            # Tipo de documento referenciado
            if hasattr(ref, 'tipo_dte'):
                etree.SubElement(referencia, "TpoDocRef").text = ref.tipo_dte
            
            # Folio del documento referenciado
            if hasattr(ref, 'folio'):
                etree.SubElement(referencia, "FolioRef").text = str(ref.folio)
            
            # Fecha del documento referenciado
            if hasattr(ref, 'fecha_emision'):
                etree.SubElement(referencia, "FchRef").text = ref.fecha_emision.strftime('%Y-%m-%d')
            
            # Razón de la referencia
            if hasattr(self.venta, 'razon_referencia') and self.venta.razon_referencia:
                etree.SubElement(referencia, "RazonRef").text = self.venta.razon_referencia[:90]
