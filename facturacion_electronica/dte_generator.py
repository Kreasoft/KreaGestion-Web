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
        
        # Detalles (items de la venta)
        sum_neto = self._generar_detalles(documento)
        
        # Totales
        self._generar_totales(encabezado, sum_neto=sum_neto)
        
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
        
        # Detalles
        sum_neto = self._generar_detalles(documento)
        
        # Totales (pasando sum_neto calculado)
        self._generar_totales(encabezado, sum_neto=sum_neto)
        
        return documento
    
    def _generar_guia(self, root):
        """Genera XML para Guía de Despacho Electrónica (52)"""
        # IMPORTANTE: Usar formato F{folio}T{tipo_dte} como en el ejemplo que funciona
        documento = etree.SubElement(root, "Documento", ID=f"F{self.folio}T{self.tipo_dte}")
        
        # Encabezado SIN datos de transporte (opcional, y el ejemplo que funciona no lo incluye)
        encabezado = self._generar_encabezado(documento, incluir_transporte=False)
        
        # Detalles
        sum_neto = self._generar_detalles(documento)
        
        # Totales (pasando sum_neto calculado)
        self._generar_totales(encabezado, sum_neto=sum_neto)
        
        return documento
    
    def _generar_nota_credito(self, root):
        """Genera XML para Nota de Crédito Electrónica (61)"""
        documento = etree.SubElement(root, "Documento", ID=f"NC{self.folio}")
        
        # Encabezado
        encabezado = self._generar_encabezado(documento)
        
        # Referencia al documento original (OBLIGATORIO)
        self._generar_referencia(documento, obligatorio=True)
        
        # Detalles
        sum_neto = self._generar_detalles(documento)
        
        # Totales (pasando sum_neto calculado)
        self._generar_totales(encabezado, sum_neto=sum_neto)
        
        return documento
    
    def _generar_nota_debito(self, root):
        """Genera XML para Nota de Débito Electrónica (56)"""
        documento = etree.SubElement(root, "Documento", ID=f"ND{self.folio}")
        
        # Encabezado
        encabezado = self._generar_encabezado(documento)
        
        # Referencia al documento original (OBLIGATORIO)
        self._generar_referencia(documento, obligatorio=True)
        
        # Detalles
        sum_neto = self._generar_detalles(documento)
        
        # Totales (pasando sum_neto calculado)
        self._generar_totales(encabezado, sum_neto=sum_neto)
        
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
        
        # Campos de guía de despacho (tipo 52): TipoDespacho e IndTraslado
        # Ambos deben ir en IdDoc y son independientes
        if self.tipo_dte == '52':
            tipo_despacho = None
            ind_traslado = None
            
            # TipoDespacho: desde venta o del propio documento si existiera
            if hasattr(self.documento, 'venta') and self.documento.venta and hasattr(self.documento.venta, 'tipo_despacho'):
                tipo_despacho = self.documento.venta.tipo_despacho
                print(f"[DTE Generator] TipoDespacho desde venta.tipo_despacho: {tipo_despacho}")
            elif hasattr(self.documento, 'tipo_despacho') and self.documento.tipo_despacho:
                tipo_despacho = self.documento.tipo_despacho
                print(f"[DTE Generator] TipoDespacho desde documento.tipo_despacho: {tipo_despacho}")
            
            # IndTraslado: prioridad documento.tipo_traslado, luego selección de la UI en venta.tipo_despacho
            if hasattr(self.documento, 'tipo_traslado') and self.documento.tipo_traslado:
                ind_traslado = self.documento.tipo_traslado
                print(f"[DTE Generator] IndTraslado desde documento.tipo_traslado: {ind_traslado}")
            elif hasattr(self.documento, 'venta') and self.documento.venta and hasattr(self.documento.venta, 'tipo_despacho') and self.documento.venta.tipo_despacho:
                ind_traslado = self.documento.venta.tipo_despacho
                print(f"[DTE Generator] IndTraslado desde venta.tipo_despacho: {ind_traslado}")
            else:
                # Fallback: '1' (Venta) si no hay selección disponible
                ind_traslado = '1'
                print(f"[DTE Generator] IndTraslado por defecto asignado: {ind_traslado}")
            
            # Normalizar valores permitidos
            if tipo_despacho not in ['1', '2', None]:
                tipo_despacho = '1'
            if ind_traslado not in ['1', '2', '3', '4']:
                ind_traslado = '1'
            
            # FmaPago en guías, para compatibilidad con KreaDTE/DTEBox (usar Contado por defecto)
            etree.SubElement(id_doc, "FmaPago").text = "1"
            
            # Escribir en XML si existen; TipoDespacho puede omitirse si no se definió
            if tipo_despacho:
                etree.SubElement(id_doc, "TipoDespacho").text = str(tipo_despacho)
            etree.SubElement(id_doc, "IndTraslado").text = str(ind_traslado)
        
        # Forma de pago - NO incluir para boletas (39, 41) NI para guías (52) - solo facturas/notas
        # Para facturas y notas: 1=Contado, 2=Crédito
        if self.tipo_dte not in ['39', '41', '52']:
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
        
        # Fecha de vencimiento (si es crédito) - NO incluir en tipo 52 según ejemplo exitoso
        from ventas.models import Venta
        if self.tipo_dte != '52' and isinstance(self.documento, Venta) and hasattr(self.documento, 'fecha_vencimiento') and self.documento.fecha_vencimiento:
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
        
        # RUT sin puntos
        rut_emisor = self.empresa.rut.replace('.', '')
        etree.SubElement(emisor, "RUTEmisor").text = rut_emisor
        
        # Para boletas (39/41) usar tags específicos, para facturas usar estándar
        if self.tipo_dte in ['39', '41']:
            # Esquema GDExpress para boletas
            razon_social = self.empresa.razon_social_sii or self.empresa.razon_social
            etree.SubElement(emisor, "RznSocEmisor").text = razon_social[:100]
            
            giro = self.empresa.giro_sii or self.empresa.giro or "Comercio"
            etree.SubElement(emisor, "GiroEmisor").text = giro[:80]
        else:
            # Esquema estándar para facturas
            razon_social = self.empresa.razon_social_sii or self.empresa.razon_social
            etree.SubElement(emisor, "RznSoc").text = razon_social[:100]
            
            giro = self.empresa.giro_sii or self.empresa.giro or "Comercio"
            etree.SubElement(emisor, "GiroEmis").text = giro[:80]
        
        # Teléfono y CorreoEmisor - NO incluir en boletas (39/41). Guías 52 sí (estructura KreaDTE/DTEBox).
        if self.tipo_dte not in ['39', '41']:
            etree.SubElement(emisor, "Telefono").text = (self.empresa.telefono or "")[:20]
            etree.SubElement(emisor, "CorreoEmisor").text = (self.empresa.email or "")[:80]
        
        # Acteco - NO incluir en boletas. Guías 52 sí (estructura KreaDTE/DTEBox).
        if self.tipo_dte not in ['39', '41']:
            acteco = self.empresa.codigo_actividad_economica or ("722000" if self.tipo_dte == '52' else "0")
            etree.SubElement(emisor, "Acteco").text = str(acteco)
        
        # Dirección
        direccion = self.empresa.direccion_casa_matriz or self.empresa.direccion
        if direccion:
            etree.SubElement(emisor, "DirOrigen").text = direccion[:70]
        
        # Comuna
        comuna = self.empresa.comuna_casa_matriz or self.empresa.comuna
        if comuna:
            etree.SubElement(emisor, "CmnaOrigen").text = comuna[:20]
        
        # Ciudad - incluir para facturas y guías (KreaDTE tiene CiudadOrigen siempre)
        ciudad = self.empresa.ciudad_casa_matriz or self.empresa.ciudad
        if ciudad:
            etree.SubElement(emisor, "CiudadOrigen").text = ciudad[:20]
        
        # Código vendedor - NO incluir en boletas. Guías 52 sí (KreaDTE: CdgVendedor OFICINA).
        if self.tipo_dte not in ['39', '41']:
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
        
        # GiroRecep
        # - Obligatorio para guías (52) según DTEBox/KreaDTE-Cloud
        # - Opcional en otros tipos (no incluir en boletas 39, 41)
        if self.tipo_dte == '52':
            giro_val = (giro or 'SIN GIRO')[:40]
            etree.SubElement(receptor, "GiroRecep").text = giro_val
        elif giro and self.tipo_dte not in ['39', '41']:
            etree.SubElement(receptor, "GiroRecep").text = giro[:40]
        
        # Contacto (opcional)
        contacto = ''
        if hasattr(self.documento, 'cliente') and self.documento.cliente:
            contacto = getattr(self.documento.cliente, 'telefono', '') or getattr(self.documento.cliente, 'celular', '')
        if contacto:
            etree.SubElement(receptor, "Contacto").text = str(contacto)[:80]
        
        if direccion:
            etree.SubElement(receptor, "DirRecep").text = direccion[:70]
        if comuna:
            etree.SubElement(receptor, "CmnaRecep").text = comuna[:20]
        # CiudadRecep - incluir para facturas y guías (KreaDTE)
        ciudad_recep = 'SANTIAGO'  # Default
        if hasattr(self.documento, 'cliente') and self.documento.cliente:
            ciudad_recep = getattr(self.documento.cliente, 'ciudad', '') or 'SANTIAGO'
        if hasattr(self.documento, 'ciudad_receptor') and self.documento.ciudad_receptor:
            ciudad_recep = self.documento.ciudad_receptor[:20]
        etree.SubElement(receptor, "CiudadRecep").text = (ciudad_recep or 'SANTIAGO')[:20]
    
    def _generar_totales(self, encabezado, sum_neto=None):
        """Genera los totales del documento"""
        totales = etree.SubElement(encabezado, "Totales")
        
        # Obtener los montos desde el objeto DTE (self.documento)
        monto_neto = getattr(self.documento, 'monto_neto', 0) or 0
        monto_exento = getattr(self.documento, 'monto_exento', 0) or 0
        monto_iva = getattr(self.documento, 'monto_iva', 0) or 0
        monto_total = getattr(self.documento, 'monto_total', 0) or 0
        
        # Si sum_neto está disponible (calculado desde los items), USARLO para MntNeto
        if sum_neto is not None and self.tipo_dte not in ['34', '41']:
            monto_neto = sum_neto

        # Para boletas (tipo 39): los precios al cliente INCLUYEN IVA.
        # El SII requiere que MntNeto = precio sin IVA = MntTotal / 1.19
        # Si monto_neto == monto_total (precios con IVA almacenados como neto), recalcular.
        if self.tipo_dte in ['39'] and monto_iva > 0:
            monto_total_real = int(round(float(monto_total)))
            monto_neto_real = int(round(monto_total_real / 1.19))
            monto_iva_real = monto_total_real - monto_neto_real
            monto_neto = monto_neto_real
            monto_iva = monto_iva_real

        # Monto Neto - incluir para todos excepto exentos (34, 41)
        # IMPORTANTE: Para boletas afectas (39) se ENVIA MntNeto pero NO IVA/TasaIVA en el esquema estricto
        if self.tipo_dte not in ['34', '41']:
            etree.SubElement(totales, "MntNeto").text = str(int(round(monto_neto)))
        
        # Monto Exento - incluir para todos
        etree.SubElement(totales, "MntExe").text = str(int(round(monto_exento)))
        
        # TasaIVA - Solo para facturas y guías (NO boletas 39, 41)
        if self.tipo_dte in ['33', '34', '52', '56', '61'] and monto_iva > 0:
            etree.SubElement(totales, "TasaIVA").text = "19"
        
        # IVA - Incluir en Facturas (33), Boletas Afectas (39) y Guías (52)
        # Para guías tipo 52: calcular IVA como 19% del neto (como KreaDTE-Cloud)
        iva_final = 0
        if self.tipo_dte in ['33', '39', '52', '56', '61'] and monto_total > 0:
            if self.tipo_dte == '52':
                # Para guías: IVA = 19% del neto (sum_neto si está disponible)
                iva_final = int(round(monto_neto * 0.19))
            else:
                # Para otros: usar IVA del documento o calcular como diferencia
                iva_final = int(round(float(monto_iva))) if monto_iva > 0 else (int(round(float(monto_total))) - int(round(float(monto_neto))) - int(round(float(monto_exento))))
                if iva_final < 0: iva_final = 0
            etree.SubElement(totales, "IVA").text = str(iva_final)
        
        # Monto Total - Para guías tipo 52: recalcular si usamos sum_neto
        if self.tipo_dte == '52' and sum_neto is not None:
            # Recalcular total = neto + IVA (calculado arriba)
            monto_total_final = monto_neto + iva_final + monto_exento
            etree.SubElement(totales, "MntTotal").text = str(int(round(monto_total_final)))
        else:
            etree.SubElement(totales, "MntTotal").text = str(int(round(float(monto_total))))

    
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
            elif hasattr(self.documento, 'venta') and self.documento.venta:
                # Caso extremo: el documento tiene una relación venta
                items = self.documento.venta.ventadetalle_set.all()

        total_neto_items = 0
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
            elif hasattr(item, 'articulo') and item.articulo:
                # Es un VentaDetalle
                nombre_item = item.articulo.nombre
                articulo = item.articulo
                cantidad = float(item.cantidad)
                precio_unitario = float(item.precio_unitario)
            else:
                # Fallback genérico
                nombre_item = getattr(item, 'descripcion', 'Item sin nombre')
                if not nombre_item: nombre_item = "Item sin nombre"
                articulo = getattr(item, 'articulo', None)
                cantidad = float(getattr(item, 'cantidad', 1))
                precio_unitario = float(getattr(item, 'precio_unitario', 0))
            
            # Código del item - incluir para todos (KreaDTE incluye CdgItem para guías también)
            codigo_item = None
            if articulo:
                codigo_item = getattr(articulo, 'codigo', None) or getattr(articulo, 'sku', None) or str(articulo.id)
            if not codigo_item:
                codigo_item = "GENERICO"  # Default como KreaDTE
            if codigo_item:
                cdg_item = etree.SubElement(detalle, "CdgItem")
                etree.SubElement(cdg_item, "TpoCodigo").text = "INT"  # Código interno
                etree.SubElement(cdg_item, "VlrCodigo").text = str(codigo_item)[:35]
            
            etree.SubElement(detalle, "NmbItem").text = nombre_item[:80]
            
            # Descripción adicional - incluir para todos (KreaDTE incluye DscItem para guías también)
            descripcion_item = None
            if hasattr(item, 'descripcion') and item.descripcion:
                descripcion_item = item.descripcion
            elif articulo and hasattr(articulo, 'descripcion') and articulo.descripcion:
                descripcion_item = articulo.descripcion
            # Solo incluir DscItem si es diferente del nombre (como KreaDTE: {% if detached.descripcion != detached.producto.nombre %})
            if descripcion_item and descripcion_item != nombre_item:
                etree.SubElement(detalle, "DscItem").text = descripcion_item[:1000]
            
            # Cantidad (sin decimales para DTEBox)
            if cantidad == int(cantidad):
                etree.SubElement(detalle, "QtyItem").text = str(int(cantidad))
            else:
                etree.SubElement(detalle, "QtyItem").text = f"{cantidad:.2f}"

            # Unidad de medida (opcional)
            unidad = None
            if hasattr(item, 'articulo') and item.articulo and item.articulo.unidad_medida:
                unidad = item.articulo.unidad_medida.simbolo
            elif hasattr(item, 'unidad_medida') and item.unidad_medida:
                unidad = item.unidad_medida
            
            if unidad:
                etree.SubElement(detalle, "UnmdItem").text = str(unidad)[:4]

            # Precio unitario y Monto: SII requiere NETO para Facturas/Guías, y BRUTO para Boletas
            es_boleta = self.tipo_dte in ['39', '41']
            
            if es_boleta:
                # Caso Boleta: Usar precios brutos (tal como vienen si son del POS)
                precio_final = int(round(precio_unitario))
                monto_final = int(round(cantidad * precio_unitario))
            else:
                # Caso Factura/Guía: SII requiere precios NETOS
                # Si sospechamos que el precio es bruto (comparando con los totales del documento), lo convertimos
                monto_total_doc = float(getattr(self.documento, 'monto_total', 0) or 0)
                monto_neto_doc = float(getattr(self.documento, 'monto_neto', 0) or 0)
                
                # Si el total coincide con la suma de precios unitarios * cantidades, es muy probable que sean brutos
                # O si neto + iva == total y el precio_unitario es alto
                if monto_total_doc > 0 and monto_neto_doc > 0 and monto_total_doc != monto_neto_doc:
                    # El documento tiene IVA. Los precios unitarios de los items deben ser netos.
                    # Asumimos que si vienen del POS son brutos y los neteamos.
                    precio_neto = precio_unitario / 1.19
                    precio_final = int(round(precio_neto))
                    # El monto del item también debe ser neto
                    monto_final = int(round(cantidad * precio_neto))
                else:
                    # Ya parecen ser netos o el documento es exento
                    precio_final = int(round(precio_unitario))
                    monto_final = int(round(cantidad * precio_unitario))

            etree.SubElement(detalle, "PrcItem").text = str(precio_final)
            etree.SubElement(detalle, "MontoItem").text = str(monto_final)
            
            total_neto_items += monto_final

        return total_neto_items
    
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
        """
        # Crear el documento raíz
        root = etree.Element("DTE", version="1.0", nsmap={None: self.NS_SII})
        
        # KreaDTE usa F para todos los tipos (F46T33, F208T39, etc.)
        documento_xml = etree.SubElement(root, "Documento", ID=f"F{self.folio}T{self.tipo_dte}")
        
        # Generar Encabezado
        encabezado = self._generar_encabezado(documento_xml, incluir_transporte=(self.tipo_dte == '52'))
        
        # Generar Totales
        self._generar_totales(encabezado)
        
        # Generar Detalles (OBLIGATORIO ANTES DE TED)
        self._generar_detalles(documento_xml)
        
        # Generar Referencias si aplica
        if hasattr(self.documento, 'documento_referencia') and self.documento.documento_referencia:
            self._generar_referencia(documento_xml)

        # TED y Firma: 
        # RE, TD, F, FE, RR, RSR, MNT, IT1, CAF, TSTP
        ted = etree.SubElement(documento_xml, "TED")
        ted.set("version", "1.0")
        dd = etree.SubElement(ted, "DD")
        
        etree.SubElement(dd, "RE").text = self.empresa.rut.replace('.', '')
        etree.SubElement(dd, "TD").text = str(self.tipo_dte)
        etree.SubElement(dd, "F").text = str(self.folio)
        etree.SubElement(dd, "FE").text = self.documento.fecha_emision.strftime('%Y-%m-%d')
        etree.SubElement(dd, "RR").text = self.documento.rut_receptor.replace('.', '')
        etree.SubElement(dd, "RSR").text = self.documento.razon_social_receptor[:40]
        etree.SubElement(dd, "MNT").text = str(int(self.documento.monto_total))
        etree.SubElement(dd, "IT1").text = "DTE" 

        # Agregar CAF placeholder (REQUERIDO por DTEBox en Boletas)
        if self.caf:
            caf_element = etree.SubElement(dd, "CAF", version="1.0")
            da = etree.SubElement(caf_element, "DA")
            etree.SubElement(da, "RE").text = self.empresa.rut.replace('.', '')
            etree.SubElement(da, "RS").text = self.empresa.razon_social[:100]
            etree.SubElement(da, "TD").text = str(self.tipo_dte)
            rng = etree.SubElement(da, "RNG")
            etree.SubElement(rng, "D").text = "1"
            etree.SubElement(rng, "H").text = "10000"
            etree.SubElement(da, "FA").text = "2024-01-01"
            rsapk = etree.SubElement(da, "RSAPK")
            etree.SubElement(rsapk, "M").text = "AAAA"
            etree.SubElement(rsapk, "E").text = "AAAA"
            etree.SubElement(caf_element, "FRMA", algoritmo="SHA1withRSA").text = "AAAA"
            
        # Agregar TSTED (TIMESTAMP DEL TIMBRE) - REQUERIDO antes de FRMT
        etree.SubElement(dd, "TSTED").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Placeholder para FRMT
        frmt = etree.SubElement(ted, "FRMT")
        frmt.set("algoritmo", "SHA1withRSA")

        if self.tipo_dte in ['39', '41']:
            # Para boletas, TmstFirma es REQUERIDO y va AL FINAL del Documento
            tmst = etree.SubElement(documento_xml, "TmstFirma")
            tmst.text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        # Convertir a string con formato
        xml_string = etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding='ISO-8859-1'
        ).decode('ISO-8859-1')
        
        return xml_string
