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
        documento = etree.SubElement(root, "Documento", ID=f"F{self.folio}T{self.tipo_dte}")
        
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
        # IMPORTANTE: El ID usa prefijo F (igual que facturas) según KreaDTE
        documento = etree.SubElement(root, "Documento", ID=f"F{self.folio}T{self.tipo_dte}")
        
        # Encabezado
        encabezado = self._generar_encabezado(documento)
        
        # Totales
        self._generar_totales(encabezado)
        
        # Detalles
        self._generar_detalles(documento)
        
        return documento
    
    def _generar_guia(self, root):
        """Genera XML para Guía de Despacho Electrónica (52)"""
        # IMPORTANTE: Usar formato F{folio}T{tipo_dte} como en el ejemplo que funciona
        documento = etree.SubElement(root, "Documento", ID=f"F{self.folio}T{self.tipo_dte}")
        
        # Encabezado SIN datos de transporte (opcional, y el ejemplo que funciona no lo incluye)
        encabezado = self._generar_encabezado(documento, incluir_transporte=False)
        
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
        
        # Obtener fecha de emisión según el tipo de documento
        from ventas.models import Venta
        from pedidos.models import OrdenDespacho
        from facturacion_electronica.models import DocumentoTributarioElectronico
        
        if isinstance(self.documento, OrdenDespacho):
            fecha_emision = self.documento.fecha_despacho
        elif isinstance(self.documento, DocumentoTributarioElectronico):
            fecha_emision = self.documento.fecha_emision
        elif isinstance(self.documento, Venta):
            fecha_emision = getattr(self.documento, 'fecha', None) or getattr(self.documento, 'fecha_creacion', None)
        else:
            fecha_emision = getattr(self.documento, 'fecha', None) or getattr(self.documento, 'fecha_emision', None) or getattr(self.documento, 'fecha_creacion', None)
        
        if fecha_emision:
            # Si la fecha es un datetime con timezone, convertir a fecha de Chile
            from django.utils import timezone
            import pytz
            
            if hasattr(fecha_emision, 'tzinfo') and fecha_emision.tzinfo:
                # Es un datetime con timezone, convertir a Chile
                chile_tz = pytz.timezone('America/Santiago')
                fecha_chile = fecha_emision.astimezone(chile_tz).date()
                etree.SubElement(id_doc, "FchEmis").text = fecha_chile.strftime('%Y-%m-%d')
            else:
                # Es una fecha simple o datetime naive
                etree.SubElement(id_doc, "FchEmis").text = fecha_emision.strftime('%Y-%m-%d')
        else:
            # Si no hay fecha, usar la fecha actual en zona horaria de Chile
            from django.utils import timezone
            import pytz
            
            # Obtener la fecha actual en Chile
            chile_tz = pytz.timezone('America/Santiago')
            fecha_chile = timezone.now().astimezone(chile_tz).date()
            
            etree.SubElement(id_doc, "FchEmis").text = fecha_chile.strftime('%Y-%m-%d')
        
        # Indicador de servicio (OBLIGATORIO para boletas, opcional para facturas)
        # 3 = Boletas de venta y servicios
        if self.tipo_dte in ['39', '41']:
            etree.SubElement(id_doc, "IndServicio").text = "3"  # Obligatorio para boletas
        
        # Forma de pago - NO incluir para boletas (39, 41)
        # Para facturas y notas: 1=Contado, 2=Crédito
        if self.tipo_dte not in ['39', '41']:
            from ventas.models import Venta
            from facturacion_electronica.models import DocumentoTributarioElectronico
            forma_pago = "1"  # Default: Contado
            
            # Intentar obtener desde la venta asociada
            if isinstance(self.documento, Venta) and hasattr(self.documento, 'forma_pago') and self.documento.forma_pago:
                forma_pago = "2" if self.documento.forma_pago.es_cuenta_corriente else "1"
            elif isinstance(self.documento, DocumentoTributarioElectronico):
                # Si es un DTE, buscar la venta asociada
                if hasattr(self.documento, 'venta') and self.documento.venta:
                    venta = self.documento.venta
                    if hasattr(venta, 'forma_pago') and venta.forma_pago:
                        forma_pago = "2" if venta.forma_pago.es_cuenta_corriente else "1"
            
            etree.SubElement(id_doc, "FmaPago").text = forma_pago
        
        # Fecha de vencimiento (si es crédito)
        from ventas.models import Venta
        if isinstance(self.documento, Venta) and hasattr(self.documento, 'fecha_vencimiento') and self.documento.fecha_vencimiento:
            etree.SubElement(id_doc, "FchVenc").text = self.documento.fecha_vencimiento.strftime('%Y-%m-%d')
        
        # IndTraslado (OBLIGATORIO para Guías de Despacho tipo 52)
        # Debe ir en IdDoc, NO en Transporte
        if self.tipo_dte == '52':
            # Buscar el tipo de traslado en diferentes campos posibles
            ind_traslado = None
            
            # 1. Intentar desde tipo_traslado (DocumentoTributarioElectronico)
            if hasattr(self.documento, 'tipo_traslado') and self.documento.tipo_traslado:
                ind_traslado = self.documento.tipo_traslado
                print(f"[DTE Generator] IndTraslado desde tipo_traslado: {ind_traslado}")
            
            # 2. Intentar desde tipo_despacho (Venta)
            elif hasattr(self.documento, 'tipo_despacho') and self.documento.tipo_despacho:
                ind_traslado = self.documento.tipo_despacho
                print(f"[DTE Generator] IndTraslado desde tipo_despacho: {ind_traslado}")
            
            # 3. Intentar desde venta asociada (si el documento es un DTE)
            elif hasattr(self.documento, 'venta') and self.documento.venta:
                if hasattr(self.documento.venta, 'tipo_despacho') and self.documento.venta.tipo_despacho:
                    ind_traslado = self.documento.venta.tipo_despacho
                    print(f"[DTE Generator] IndTraslado desde venta.tipo_despacho: {ind_traslado}")
            
            # 4. ERROR CRÍTICO: NO usar valor por defecto
            if not ind_traslado:
                error_msg = (
                    "ERROR CRÍTICO: No se pudo determinar el tipo de traslado (IndTraslado) para la Guía de Despacho. "
                    "Este campo es OBLIGATORIO y afecta las obligaciones tributarias. "
                    "DEBE seleccionar el tipo de guía en el formulario: "
                    "1=Venta, 2=Venta por efectuar, 3=Consignación, 4=Devolución, "
                    "5=Traslado interno, 6=Transformación, 7=Entrega gratuita, 8=Otros"
                )
                print(f"[DTE Generator] {error_msg}")
                raise ValueError(error_msg)
            
            etree.SubElement(id_doc, "IndTraslado").text = str(ind_traslado)

        
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
        
        # Razón Social (RznSoc según estándar SII)
        razon_social = self.empresa.razon_social_sii or self.empresa.razon_social
        etree.SubElement(emisor, "RznSoc").text = razon_social[:100]  # Máximo 100 caracteres
        
        # Giro (GiroEmis según estándar SII)
        giro = self.empresa.giro_sii or self.empresa.giro or "Comercio"
        etree.SubElement(emisor, "GiroEmis").text = giro[:80]  # Máximo 80 caracteres
        
        # Teléfono (opcional pero recomendado)
        if self.empresa.telefono:
            etree.SubElement(emisor, "Telefono").text = self.empresa.telefono[:20]
        
        # Correo Electrónico Emisor (igual que KreaDTE)
        if self.empresa.email:
            etree.SubElement(emisor, "CorreoEmisor").text = self.empresa.email[:80]
        
        # Actividad Económica (OBLIGATORIO)
        acteco = self.empresa.codigo_actividad_economica
        if not acteco:
            # Si no está configurado, usar un código genérico
            acteco = "0"
        etree.SubElement(emisor, "Acteco").text = str(acteco)
        
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
        
        # Código del vendedor (opcional pero útil para DTEBox)
        codigo_vendedor = getattr(self.empresa, 'codigo_vendedor', None) or 'OFICINA'
        etree.SubElement(emisor, "CdgVendedor").text = codigo_vendedor[:60]
        
    def _generar_receptor(self, encabezado):
        """Genera datos del receptor de forma robusta."""
        receptor = etree.SubElement(encabezado, "Receptor")

        # Obtener datos del receptor desde el objeto DTE (self.documento)
        rut_receptor = getattr(self.documento, 'rut_receptor', None)
        razon_social = getattr(self.documento, 'razon_social_receptor', None)
        giro = getattr(self.documento, 'giro_receptor', '')
        direccion = getattr(self.documento, 'direccion_receptor', '')
        comuna = getattr(self.documento, 'comuna_receptor', '')

        # Si el documento es una OrdenDespacho, obtener datos desde orden_pedido.cliente
        from pedidos.models import OrdenDespacho
        if isinstance(self.documento, OrdenDespacho):
            if hasattr(self.documento, 'orden_pedido') and self.documento.orden_pedido:
                cliente = self.documento.orden_pedido.cliente
                rut_receptor = cliente.rut
                razon_social = cliente.nombre
                giro = getattr(cliente, 'giro', '')
                direccion = cliente.direccion or ''
                comuna = cliente.comuna if isinstance(cliente.comuna, str) else ''

        # Si no hay datos en el DTE, intentar obtenerlos desde la relación 'cliente'
        if not rut_receptor and hasattr(self.documento, 'cliente') and self.documento.cliente:
            cliente = self.documento.cliente
            rut_receptor = cliente.rut
            razon_social = cliente.nombre
            giro = getattr(cliente, 'giro', '')
            direccion = cliente.direccion
            comuna = cliente.comuna

        # Caso especial para boletas sin cliente: usar datos genéricos
        if self.tipo_dte in ['39', '41'] and not rut_receptor:
            rut_receptor = "66666666-6"
            razon_social = "Cliente Genérico"
            giro = ''
            direccion = ''
            comuna = ''

        # Validar que tenemos los datos mínimos
        if not rut_receptor or not razon_social:
            raise ValueError("No se pudieron determinar los datos del receptor para el DTE.")

        # Escribir los datos en el XML
        etree.SubElement(receptor, "RUTRecep").text = rut_receptor.replace('.', '')
        etree.SubElement(receptor, "RznSocRecep").text = razon_social[:100]
        if giro:
            etree.SubElement(receptor, "GiroRecep").text = giro[:40]
        
        # Contacto (opcional pero recomendado)
        contacto = ''
        if hasattr(self.documento, 'cliente') and self.documento.cliente:
            contacto = getattr(self.documento.cliente, 'telefono', '') or getattr(self.documento.cliente, 'celular', '')
        if contacto:
            etree.SubElement(receptor, "Contacto").text = str(contacto)[:80]
        
        if direccion:
            etree.SubElement(receptor, "DirRecep").text = direccion[:70]
        if comuna:
            etree.SubElement(receptor, "CmnaRecep").text = comuna[:20]
        # CiudadRecep siempre (requerido por DTEBox)
        ciudad_recep = 'SANTIAGO'  # Default
        if hasattr(self.documento, 'cliente') and self.documento.cliente:
            ciudad_recep = getattr(self.documento.cliente, 'ciudad', '') or 'SANTIAGO'
        etree.SubElement(receptor, "CiudadRecep").text = ciudad_recep[:20]
    
    def _generar_totales(self, encabezado):
        """Genera los totales del documento"""
        totales = etree.SubElement(encabezado, "Totales")
        
        # Obtener los montos desde el objeto DTE (self.documento)
        monto_neto = getattr(self.documento, 'monto_neto', 0)
        monto_exento = getattr(self.documento, 'monto_exento', 0)
        monto_iva = getattr(self.documento, 'monto_iva', 0)
        monto_total = getattr(self.documento, 'monto_total', 0)

        # Monto Neto (si aplica)
        if self.tipo_dte not in ['34', '41']:
            etree.SubElement(totales, "MntNeto").text = str(int(round(monto_neto)))
        
        # Monto Exento (siempre incluir, DTEBox lo requiere)
        etree.SubElement(totales, "MntExe").text = str(int(round(monto_exento)))
        
        # TasaIVA e IVA (si aplica)
        if self.tipo_dte not in ['34', '41'] and monto_iva > 0:
            etree.SubElement(totales, "TasaIVA").text = "19"
            etree.SubElement(totales, "IVA").text = str(int(round(monto_iva)))
        
        # Monto Total
        etree.SubElement(totales, "MntTotal").text = str(int(round(monto_total)))
    
    def _generar_detalles(self, documento):
        """Genera los detalles (items) del documento"""
        from ventas.models import Venta, NotaCredito
        from facturacion_electronica.models import DocumentoTributarioElectronico
        from pedidos.models import OrdenDespacho

        items = []
        # CRÍTICO: Verificar DocumentoTributarioElectronico PRIMERO porque tiene orden_despacho como ManyToMany
        if isinstance(self.documento, DocumentoTributarioElectronico):
            # Flujo desde POS/Despacho: los items vienen de la venta asociada al DTE
            # Primero intentar con la venta directa
            if hasattr(self.documento, 'venta') and self.documento.venta:
                items = self.documento.venta.ventadetalle_set.all()
            # Si no hay venta directa, intentar con orden_despacho
            elif self.documento.orden_despacho.exists():
                venta_asociada = self.documento.orden_despacho.first()
                if venta_asociada and hasattr(venta_asociada, 'ventadetalle_set'):
                    items = venta_asociada.ventadetalle_set.all()
        elif isinstance(self.documento, Venta):
            items = self.documento.ventadetalle_set.all()
        elif isinstance(self.documento, NotaCredito):
            items = self.documento.items.all()
        elif isinstance(self.documento, OrdenDespacho):
            # Flujo desde orden de despacho: obtener items desde la relación 'items'
            items = self.documento.items.all()
        elif hasattr(self.documento, 'orden_despacho'):
            # Wrapper con orden_despacho (solo si NO es un ManyRelatedManager)
            # Verificar si orden_despacho es un objeto individual, no un ManyRelatedManager
            orden_despacho = self.documento.orden_despacho
            # Si tiene método .all(), es un ManyRelatedManager, usar .first()
            if hasattr(orden_despacho, 'all'):
                orden_despacho = orden_despacho.first()
            if orden_despacho and hasattr(orden_despacho, 'detalleordendespacho_set'):
                items = orden_despacho.detalleordendespacho_set.all()
        else:
            # Soportar otros objetos genéricos
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
            
            # Nombre del item - soportar tanto VentaDetalle como DetalleOrdenDespacho
            if hasattr(item, 'item_pedido') and hasattr(item.item_pedido, 'articulo'):
                # Es un DetalleOrdenDespacho
                nombre_item = item.item_pedido.articulo.nombre
                articulo = item.item_pedido.articulo
                cantidad = float(item.cantidad)
                precio_unitario = float(item.item_pedido.precio_unitario)
            elif hasattr(item, 'articulo'):
                # Es un VentaDetalle
                nombre_item = item.articulo.nombre
                articulo = item.articulo
                cantidad = float(item.cantidad)
                precio_unitario = float(item.precio_unitario)
            else:
                # Fallback genérico
                nombre_item = getattr(item, 'descripcion', 'Item sin nombre')
                articulo = None
                cantidad = float(getattr(item, 'cantidad', 1))
                precio_unitario = float(getattr(item, 'precio_unitario', 0))
            
            # Código del item (requerido por DTEBox)
            codigo_item = None
            if articulo:
                codigo_item = getattr(articulo, 'codigo', None) or getattr(articulo, 'sku', None) or str(articulo.id)
            if codigo_item:
                cdg_item = etree.SubElement(detalle, "CdgItem")
                etree.SubElement(cdg_item, "TpoCodigo").text = "INT"  # Código interno
                etree.SubElement(cdg_item, "VlrCodigo").text = str(codigo_item)[:35]
            
            etree.SubElement(detalle, "NmbItem").text = nombre_item[:80]
            
            # Descripción adicional (recomendado por DTEBox)
            descripcion_item = None
            if hasattr(item, 'descripcion') and item.descripcion:
                descripcion_item = item.descripcion
            elif articulo and hasattr(articulo, 'descripcion') and articulo.descripcion:
                descripcion_item = articulo.descripcion
            else:
                descripcion_item = nombre_item  # Usar nombre como descripción si no hay otra
            if descripcion_item:
                etree.SubElement(detalle, "DscItem").text = descripcion_item[:1000]
            
            # Cantidad (sin decimales para DTEBox)
            if cantidad == int(cantidad):
                etree.SubElement(detalle, "QtyItem").text = str(int(cantidad))
            else:
                etree.SubElement(detalle, "QtyItem").text = f"{cantidad:.2f}"

            # Precio unitario
            precio_unitario_int = int(round(precio_unitario))
            etree.SubElement(detalle, "PrcItem").text = str(precio_unitario_int)

            # Monto total del ítem: cantidad * precio_unitario
            monto_item = int(round(cantidad * precio_unitario))
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

    def generar_xml_desde_dte(self):
        """
        Genera el XML completo para un DTE ya existente en la base de datos.
        Este método es usado por flujos que primero crean el objeto DTE y luego el XML, 
        como el POS o la creación de guías desde pedidos.
        """
        # Crear el documento raíz
        root = etree.Element("DTE", version="1.0", nsmap={None: self.NS_SII})
        
        # KreaDTE usa F para todos los tipos (F46T33, F208T39, etc.)
        documento_xml = etree.SubElement(root, "Documento", ID=f"F{self.folio}T{self.tipo_dte}")
        
        # Generar Encabezado
        # El objeto 'documento' que usa _generar_encabezado es el DTE mismo
        encabezado = self._generar_encabezado(documento_xml, incluir_transporte=(self.tipo_dte == '52'))
        
        # Generar Totales
        self._generar_totales(encabezado)
        
        # Generar Detalles
        self._generar_detalles(documento_xml)
        
        # Generar Referencias si aplica
        if hasattr(self.documento, 'documento_referencia') and self.documento.documento_referencia:
            self._generar_referencia(documento_xml)

        # Convertir a string con formato
        xml_string = etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding='ISO-8859-1'
        ).decode('ISO-8859-1')
        
        return xml_string
