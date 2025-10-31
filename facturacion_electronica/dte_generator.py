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
    
    def __init__(self, empresa, documento, tipo_dte, folio, caf):
        """
        Inicializa el generador de DTE
        
        Args:
            empresa: Instancia de Empresa
            documento: Instancia de Venta o NotaCredito
            tipo_dte: Código del tipo de DTE (33, 39, etc.)
            folio: Número de folio asignado
            caf: Instancia de ArchivoCAF
        """
        self.empresa = empresa
        self.documento = documento
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
        if hasattr(self.documento, 'documento_referencia') and self.documento.documento_referencia:
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
        etree.SubElement(id_doc, "FchEmis").text = self.documento.fecha.strftime('%Y-%m-%d')
        
        # Indicador de servicio (solo para facturas de servicios)
        if self.tipo_dte in ['33', '34']:
            etree.SubElement(id_doc, "IndServicio").text = "3"  # 3 = Servicios y productos
        
        # Forma de pago
        from ventas.models import Venta
        if isinstance(self.documento, Venta) and hasattr(self.documento, 'forma_pago') and self.documento.forma_pago:
            # 1: Contado, 2: Crédito, 3: Sin costo
            forma_pago = "2" if self.documento.forma_pago.es_cuenta_corriente else "1"
            etree.SubElement(id_doc, "FmaPago").text = forma_pago
        
        # Fecha de vencimiento (si es crédito)
        from ventas.models import Venta
        if isinstance(self.documento, Venta) and hasattr(self.documento, 'fecha_vencimiento') and self.documento.fecha_vencimiento:
            etree.SubElement(id_doc, "FchVenc").text = self.documento.fecha_vencimiento.strftime('%Y-%m-%d')
        
        # Emisor
        self._generar_emisor(encabezado)
        
        # Receptor
        self._generar_receptor(encabezado)
        
        # Transporte (solo para guías de despacho)
        if incluir_transporte:
            self._generar_transporte(encabezado)
        
        return encabezado
    
    def _generar_transporte(self, encabezado):
        """Genera la sección de Transporte para Guías de Despacho (52).
        Se incluyen los campos mínimos para que el XML sea válido. Si no hay datos
        de transporte disponibles se agregan valores por defecto.
        """
        try:
            from lxml import etree
            # Contenedor Transporte
            transporte = etree.SubElement(encabezado, "Transporte")

            # Indicador de tipo de traslado (campo requerido)
            # 1=Operaciones con cambios de sujeto, 2=Operaciones sin cambios de sujeto, etc.
            ind_traslado = getattr(self.documento, 'tipo_despacho', None) or '1'
            etree.SubElement(transporte, "IndTraslado").text = str(ind_traslado)

            # Patente del vehículo (opcional). Si no existe, colocar genérico.
            patente = getattr(self.documento, 'patente', None) or 'ZZZZ99'
            etree.SubElement(transporte, "Patente").text = patente

            # RUT del transportista (opcional).
            rut_transp = getattr(self.documento, 'rut_transportista', None)
            if rut_transp:
                etree.SubElement(transporte, "RUTTransp").text = rut_transp
        except Exception as e:
            # No romper el flujo si falla: solo loguear.
            print(f"[WARN] Error al generar seccion Transporte: {e}")
    
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
        from ventas.models import Venta
        if isinstance(self.documento, Venta) and self.tipo_dte in ['39', '41'] and not self.documento.cliente:
            etree.SubElement(receptor, "RUTRecep").text = "66666666-6"
            etree.SubElement(receptor, "RznSocRecep").text = "Cliente Genérico"
            return
        
        # Cliente específico
        if self.documento.cliente:
            cliente = self.documento.cliente
            
            # RUT
            rut_receptor = cliente.rut.replace('.', '')
            etree.SubElement(receptor, "RUTRecep").text = rut_receptor
            
            # Razón Social
            razon_social = cliente.nombre
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
        else:
            # Fallback: usar datos de la empresa como receptor (traslado interno, guía 52 sin cliente)
            rut_receptor = self.empresa.rut.replace('.', '')
            etree.SubElement(receptor, "RUTRecep").text = rut_receptor
            razon_social = self.empresa.nombre
            etree.SubElement(receptor, "RznSocRecep").text = razon_social[:100]
            direccion = self.empresa.direccion or self.empresa.direccion_casa_matriz or ''
            if direccion:
                etree.SubElement(receptor, "DirRecep").text = direccion[:70]
            comuna = self.empresa.comuna or self.empresa.comuna_casa_matriz or ''
            if comuna:
                etree.SubElement(receptor, "CmnaRecep").text = comuna[:20]
            ciudad = self.empresa.ciudad or self.empresa.ciudad_casa_matriz or ''
            if ciudad:
                etree.SubElement(receptor, "CiudadRecep").text = ciudad[:20]
    
    def _generar_totales(self, encabezado):
        """Genera los totales del documento"""
        totales = etree.SubElement(encabezado, "Totales")
        
        # Monto Neto
        if self.tipo_dte not in ['34', '41']:  # No exentos
            # Para NC, el subtotal es el neto. Para Venta, hay que calcularlo.
            neto = self.documento.neto if hasattr(self.documento, 'neto') else self.documento.subtotal
            monto_neto = int(round(float(neto)))
            etree.SubElement(totales, "MntNeto").text = str(monto_neto)
        
        # Monto Exento
        if self.tipo_dte in ['34', '41']:  # Documentos exentos
            monto_exento = int(round(float(self.documento.total)))
            etree.SubElement(totales, "MntExe").text = str(monto_exento)
        
        # IVA
        if self.tipo_dte not in ['34', '41']:
            monto_iva = int(round(float(self.documento.iva)))
            etree.SubElement(totales, "IVA").text = str(monto_iva)
        
        # Monto Total
        monto_total = int(round(float(self.documento.total)))
        etree.SubElement(totales, "MntTotal").text = str(monto_total)
    
    def _generar_detalles(self, documento):
        """Genera los detalles (items) del documento"""
        from ventas.models import Venta, NotaCredito
        if isinstance(self.documento, Venta):
            items = self.documento.ventadetalle_set.all()
        elif isinstance(self.documento, NotaCredito):
            items = self.documento.items.all()
        else:
            # Soportar objetos genéricos (por ejemplo, transferencias con atributo 'items' o 'detalles')
            items = []
            if hasattr(self.documento, 'items') and self.documento.items is not None:
                try:
                    items = self.documento.items.all()
                except Exception:
                    items = self.documento.items
            elif hasattr(self.documento, 'detalles') and self.documento.detalles is not None:
                try:
                    items = self.documento.detalles.all()
                except Exception:
                    items = self.documento.detalles

        for index, item in enumerate(items, start=1):
            detalle = etree.SubElement(documento, "Detalle")
            
            # Número de línea
            etree.SubElement(detalle, "NroLinDet").text = str(index)
            
            # Indicador de exención (solo si es documento exento)
            if self.tipo_dte in ['34', '41']:
                etree.SubElement(detalle, "IndExe").text = "1"
            
            # Nombre del item
            nombre_item = item.articulo.nombre if hasattr(item, 'articulo') else getattr(item, 'descripcion', '')
            etree.SubElement(detalle, "NmbItem").text = nombre_item[:80]
            
            # Descripción adicional (opcional)
            if hasattr(item, 'descripcion') and item.descripcion:
                etree.SubElement(detalle, "DscItem").text = item.descripcion[:1000]
            
            # Cantidad
            cantidad = float(item.cantidad)
            etree.SubElement(detalle, "QtyItem").text = f"{cantidad:.4f}"
            
            # Unidad de medida
            unidad = "UN"  # Por defecto
            if hasattr(item, 'articulo') and item.articulo and hasattr(item.articulo, 'unidad_medida') and item.articulo.unidad_medida:
                if hasattr(item.articulo.unidad_medida, 'codigo_sii') and item.articulo.unidad_medida.codigo_sii:
                    unidad = item.articulo.unidad_medida.codigo_sii
            etree.SubElement(detalle, "UnmdItem").text = unidad

            # Precio unitario
            precio_unitario = int(round(float(item.precio_unitario)))
            etree.SubElement(detalle, "PrcItem").text = str(precio_unitario)

            # Monto total del ítem: usar precio_total si existe; si no, cantidad * precio_unitario
            try:
                monto_item = int(round(float(getattr(item, 'precio_total', item.cantidad * item.precio_unitario))))
            except Exception:
                monto_item = int(round(float(item.cantidad * item.precio_unitario)))
            etree.SubElement(detalle, "MontoItem").text = str(monto_item)
    
    def _generar_referencia(self, documento, obligatorio=False):
        """Genera referencias a otros documentos"""
        from ventas.models import Venta, NotaCredito

        # Caso para Nota de Crédito (referencia obligatoria)
        if isinstance(self.documento, NotaCredito):
            referencia = etree.SubElement(documento, "Referencia")
            etree.SubElement(referencia, "NroLinRef").text = "1"
            etree.SubElement(referencia, "TpoDocRef").text = self.documento.tipo_doc_afectado
            etree.SubElement(referencia, "FolioRef").text = self.documento.numero_doc_afectado
            etree.SubElement(referencia, "FchRef").text = self.documento.fecha_doc_afectado.strftime('%Y-%m-%d')
            
            cod_ref_map = {
                'ANULA': '1',
                'CORRIGE_TEXTO': '2',
                'CORRIGE_MONTO': '3',
            }
            cod_ref = cod_ref_map.get(self.documento.tipo_nc, '1')
            etree.SubElement(referencia, "CodRef").text = cod_ref

            etree.SubElement(referencia, "RazonRef").text = self.documento.motivo[:90]

        # Caso para Venta con referencia opcional (ej. Guía de Despacho)
        elif isinstance(self.documento, Venta) and hasattr(self.documento, 'documento_referencia') and self.documento.documento_referencia:
            ref = self.documento.documento_referencia
            referencia = etree.SubElement(documento, "Referencia")
            etree.SubElement(referencia, "NroLinRef").text = "1"
            if hasattr(ref, 'tipo_dte'):
                etree.SubElement(referencia, "TpoDocRef").text = ref.tipo_dte
            if hasattr(ref, 'folio'):
                etree.SubElement(referencia, "FolioRef").text = str(ref.folio)
            if hasattr(ref, 'fecha_emision'):
                etree.SubElement(referencia, "FchRef").text = ref.fecha_emision.strftime('%Y-%m-%d')
            if hasattr(self.documento, 'razon_referencia') and self.documento.razon_referencia:
                etree.SubElement(referencia, "RazonRef").text = self.documento.razon_referencia[:90]
