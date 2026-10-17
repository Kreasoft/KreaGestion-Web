"""
Generador de XML para Documentos Tributarios Electrónicos (DTE)
Según formato oficial del SII de Chile
"""
from lxml import etree
import re
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from facturacion_electronica.models import DocumentoTributarioElectronico


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

    @staticmethod
    def _monto_entero(valor):
        return int(round(float(valor or 0)))

    @staticmethod
    def extraer_totales_xml(xml_string):
        """Lee MntNeto / IVA / MntTotal del XML ya generado para alinear TED y BD."""
        import re
        xml = xml_string if isinstance(xml_string, str) else xml_string.decode('ISO-8859-1', errors='ignore')

        def _tag(nombre):
            m = re.search(r'<%s>([^<]+)</%s>' % (nombre, nombre), xml)
            if not m:
                return 0
            try:
                return int(round(float(m.group(1))))
            except (TypeError, ValueError):
                return 0

        return {
            'neto': _tag('MntNeto'),
            'exento': _tag('MntExe'),
            'iva': _tag('IVA'),
            'total': _tag('MntTotal'),
        }

    def _obtener_montos_documento(self):
        """Normaliza montos desde Venta, DTE, NotaCredito o NotaDebito."""
        monto_neto = getattr(self.documento, 'monto_neto', None)
        if monto_neto is None:
            monto_neto = getattr(self.documento, 'subtotal', None)
        if monto_neto is None:
            monto_neto = getattr(self.documento, 'neto', 0)

        monto_exento = getattr(self.documento, 'monto_exento', None)
        if monto_exento is None:
            monto_exento = getattr(self.documento, 'exento', 0)
        if monto_exento is None:
            monto_exento = 0

        monto_iva = getattr(self.documento, 'monto_iva', None)
        if monto_iva is None:
            monto_iva = getattr(self.documento, 'iva', 0)
        if monto_iva is None:
            monto_iva = 0

        monto_total = getattr(self.documento, 'monto_total', None)
        if monto_total is None:
            monto_total = getattr(self.documento, 'total', 0)
        if monto_total is None:
            monto_total = 0

        return (
            self._monto_entero(monto_neto),
            self._monto_entero(monto_exento),
            self._monto_entero(monto_iva),
            self._monto_entero(monto_total),
        )

    @staticmethod
    def _normalizar_rut(rut):
        return str(rut or '').replace('.', '').replace(' ', '').upper()

    def _rut_receptor_efectivo(self):
        rut = getattr(self.documento, 'rut_receptor', None)
        if rut:
            return rut
        from pedidos.models import OrdenDespacho
        if isinstance(self.documento, OrdenDespacho):
            cliente = getattr(getattr(self.documento, 'orden_pedido', None), 'cliente', None)
            if cliente:
                return cliente.rut
        venta = getattr(self.documento, 'venta', None)
        if venta and getattr(venta, 'cliente', None):
            return venta.cliente.rut
        cliente = getattr(self.documento, 'cliente', None)
        if cliente:
            return cliente.rut
        return ''

    def _es_guia_traslado_interno(self):
        """Traslado interno (IndTraslado=5) solo si el receptor es la misma empresa."""
        if str(self.tipo_dte) != '52':
            return False
        if str(getattr(self.documento, 'tipo_traslado', '') or getattr(self.documento, 'tipo_despacho', '') or '') != '5':
            return False
        rut_emp = self._normalizar_rut(getattr(self.empresa, 'rut', ''))
        rut_rec = self._normalizar_rut(self._rut_receptor_efectivo())
        if rut_rec and rut_emp and rut_rec != rut_emp:
            return False
        return True

    def _ind_traslado_efectivo(self):
        if str(self.tipo_dte) != '52':
            return ''
        ind = str(getattr(self.documento, 'tipo_traslado', '') or '')
        if not ind:
            ind = str(getattr(self.documento, 'tipo_despacho', '') or '')
        if ind == '5' and not self._es_guia_traslado_interno():
            return '1'
        return ind

    def _es_guia_sin_valoracion(self):
        """Guía que no es venta: el SII permite omitir precio (no enviar PrcItem=0)."""
        return self._ind_traslado_efectivo() in {'4', '5', '6', '8'}
        
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
        from ventas.models import Venta
        venta_obj = getattr(self.documento, 'venta', None) if not isinstance(self.documento, Venta) else self.documento
        tiene_refs = (hasattr(self.documento, 'documento_referencia') and self.documento.documento_referencia) or \
                     (venta_obj and hasattr(venta_obj, 'referencias') and venta_obj.referencias.exists())
        if tiene_refs:
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
        
        # Encabezado CON datos de transporte (OBLIGATORIO para Guías tipo 52)
        encabezado = self._generar_encabezado(documento, incluir_transporte=True)
        
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
        
        # Detalles
        sum_neto = self._generar_detalles(documento)

        # Referencia al documento original (OBLIGATORIO)
        self._generar_referencia(documento, obligatorio=True)
        
        # Totales (pasando sum_neto calculado)
        self._generar_totales(encabezado, sum_neto=sum_neto)
        
        return documento
    
    def _generar_nota_debito(self, root):
        """Genera XML para Nota de Débito Electrónica (56)"""
        documento = etree.SubElement(root, "Documento", ID=f"ND{self.folio}")
        
        # Encabezado
        encabezado = self._generar_encabezado(documento)
        
        # Detalles
        sum_neto = self._generar_detalles(documento)

        # Referencia al documento original (OBLIGATORIO)
        self._generar_referencia(documento, obligatorio=True)
        
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
        
        # PRIORIDAD DE FECHA PARA EL XML (CRÍTICO PARA CAJA)
        fecha_emision = None
        for campo_fecha in (
            'fecha_emision',
            'fecha',
            'fecha_pedido',
            'fecha_despacho',
            'fecha_creacion',
        ):
            if hasattr(self.documento, campo_fecha):
                fecha_emision = getattr(self.documento, campo_fecha)
                if fecha_emision:
                    break
            
        if fecha_emision:
            from django.utils import timezone
            import pytz
            
            # Asegurar que la fecha esté en la zona horaria de Chile
            chile_tz = pytz.timezone('America/Santiago')
            if hasattr(fecha_emision, 'astimezone'):
                fecha_chile = fecha_emision.astimezone(chile_tz).date()
                etree.SubElement(id_doc, "FchEmis").text = fecha_chile.strftime('%Y-%m-%d')
            else:
                etree.SubElement(id_doc, "FchEmis").text = fecha_emision.strftime('%Y-%m-%d')
        else:
            from django.utils import timezone
            fecha_chile = timezone.localdate()
            etree.SubElement(id_doc, "FchEmis").text = fecha_chile.strftime('%Y-%m-%d')
        
        # Indicador de servicio (OBLIGATORIO para boletas)
        if self.tipo_dte in ['39', '41']:
            etree.SubElement(id_doc, "IndServicio").text = "3"
        
        # Orden estricto SII para IdDoc:
        # TipoDTE, Folio, FchEmis, datos de guia 52, FmaPago, FchVenc.
        if self.tipo_dte == '52':
            tipo_despacho = str(getattr(self.documento, 'tipo_despacho_sii', None) or '').strip()
            if tipo_despacho not in ('1', '2', '3'):
                tipo_despacho = '2'
            etree.SubElement(id_doc, "TipoDespacho").text = tipo_despacho

            ind_traslado = '1'
            if hasattr(self.documento, 'tipo_traslado') and self.documento.tipo_traslado:
                ind_traslado = str(self.documento.tipo_traslado)
            elif hasattr(self.documento, 'tipo_despacho') and self.documento.tipo_despacho:
                ind_traslado = str(self.documento.tipo_despacho)
            if ind_traslado == '5' and not self._es_guia_traslado_interno():
                ind_traslado = '1'
            etree.SubElement(id_doc, "IndTraslado").text = ind_traslado

        if self.tipo_dte not in ['39', '41']:
            forma_pago = "1"
            if hasattr(self.documento, 'forma_pago') and self.documento.forma_pago:
                forma_pago = str(self.documento.forma_pago)
            elif hasattr(self.documento, 'venta') and self.documento.venta:
                v = self.documento.venta
                if hasattr(v, 'forma_pago') and v.forma_pago:
                    fp = v.forma_pago
                    nom_fp = (fp.nombre or '').lower()
                    es_cred = (
                        getattr(fp, 'es_cuenta_corriente', False)
                        or getattr(fp, 'es_credito', False)
                        or (('credito' in nom_fp or 'crédito' in nom_fp or 'cuenta corriente' in nom_fp) and 'tarjeta' not in nom_fp and 'transbank' not in nom_fp)
                    )
                    forma_pago = "2" if es_cred else "1"

            etree.SubElement(id_doc, "FmaPago").text = forma_pago

        if self._es_guia_traslado_interno():
            fecha_cancel = getattr(self.documento, 'fecha_emision', None)
            if fecha_cancel:
                etree.SubElement(id_doc, "FchCancel").text = fecha_cancel.strftime('%Y-%m-%d')

        if self.tipo_dte not in ['39', '41', '52']:
            fecha_venc = getattr(self.documento, 'fecha_vencimiento', None)
            if not fecha_venc:
                venta_doc = getattr(self.documento, 'venta', None)
                fecha_venc = getattr(venta_doc, 'fecha_vencimiento', None) if venta_doc else None
            if fecha_venc:
                etree.SubElement(id_doc, "FchVenc").text = fecha_venc.strftime('%Y-%m-%d')

        # Emisor, Receptor, Transporte
        self._generar_emisor(encabezado)
        self._generar_receptor(encabezado)
        if self._es_guia_traslado_interno() and getattr(self.documento, 'rut_solicita', None):
            etree.SubElement(encabezado, "RUTSolicita").text = str(self.documento.rut_solicita).replace('.', '')
        if incluir_transporte and self.tipo_dte == '52':
            self._generar_transporte(encabezado)
            
        return encabezado
    
    def _generar_transporte(self, encabezado):
        """Genera la sección de Transporte para Guías de Despacho (52).
        Se incluyen los campos mínimos para que el XML sea válido. Si no hay datos
        de transporte disponibles se agregan valores del receptor como destino.
        """
        try:
            from pedidos.models import OrdenDespacho
            from lxml import etree
            # Contenedor Transporte
            transporte = etree.SubElement(encabezado, "Transporte")
            documento_persistido = bool(getattr(self.documento, 'pk', None))

            orden = None
            if isinstance(self.documento, OrdenDespacho):
                orden = self.documento
            elif isinstance(self.documento, DocumentoTributarioElectronico) and documento_persistido:
                detalle_guia = self.documento.detalles_despacho_guia.select_related(
                    'orden_despacho__orden_pedido__cliente',
                    'orden_despacho__vehiculo',
                    'orden_despacho__chofer',
                ).first()
                if detalle_guia:
                    orden = detalle_guia.orden_despacho

            # 1. Patente del vehículo
            # En schema SII 2026 debe ir antes del bloque de destino.
            patente = getattr(self.documento, 'patente_transporte', None)
            if not patente and hasattr(self.documento, 'vehiculo') and self.documento.vehiculo:
                patente = self.documento.vehiculo.patente
            if not patente and orden and getattr(orden, 'vehiculo', None):
                patente = orden.vehiculo.patente
            
            if patente:
                etree.SubElement(transporte, "Patente").text = patente[:8].replace('-', '').upper()

            patente_carro = (getattr(self.documento, 'patente_carro', None) or '').strip()
            if patente_carro:
                etree.SubElement(transporte, "PatenteCarro").text = patente_carro[:8].replace('-', '').upper()

            # 2. RUT del transportista (schema SII: RUTTrans)
            rut_transp = getattr(self.documento, 'rut_transportista', None)
            if not rut_transp:
                rut_transp = getattr(self.empresa, 'rut', None)
            if rut_transp:
                etree.SubElement(transporte, "RUTTrans").text = str(rut_transp).replace('.', '')

            # 3. Chofer: el SII exige hijos RUTChofer + NombreChofer (no texto suelto).
            nombre_chofer, rut_chofer = self._datos_chofer()
            if nombre_chofer and rut_chofer:
                chofer_el = etree.SubElement(transporte, "Chofer")
                etree.SubElement(chofer_el, "RUTChofer").text = rut_chofer
                etree.SubElement(chofer_el, "NombreChofer").text = nombre_chofer[:30]

            # 4. Dirección de Destino (OBLIGATORIO para Guías)
            direccion = getattr(self.documento, 'direccion_receptor', '') or ''
            comuna = getattr(self.documento, 'comuna_receptor', '') or ''
            ciudad = getattr(self.documento, 'ciudad_receptor', '') or ''

            def _dir_invalida(valor):
                texto = (valor or '').strip().upper()
                return not texto or 'DESCONOCIDA' in texto or 'NO DISPONIBLE' in texto

            if _dir_invalida(direccion):
                direccion = getattr(self.documento, 'direccion_entrega', '') or direccion

            if orden:
                if _dir_invalida(direccion):
                    direccion = orden.direccion_entrega or direccion
                cliente_destino = getattr(getattr(orden, 'orden_pedido', None), 'cliente', None)
                if cliente_destino:
                    if _dir_invalida(direccion):
                        direccion = cliente_destino.direccion or direccion
                    if _dir_invalida(comuna):
                        comuna = cliente_destino.comuna if isinstance(cliente_destino.comuna, str) else comuna
                    if not ciudad:
                        ciudad = getattr(cliente_destino, 'ciudad', '') or ciudad

            # Si no hay datos en el documento, intentar desde la relación cliente o transferencia
            if _dir_invalida(direccion):
                if hasattr(self.documento, 'cliente') and self.documento.cliente:
                    direccion = self.documento.cliente.direccion
                    comuna = self.documento.cliente.comuna
                    ciudad = getattr(self.documento.cliente, 'ciudad', 'SANTIAGO')
                elif isinstance(self.documento, DocumentoTributarioElectronico) and documento_persistido:
                    transf = self.documento.transferencias.first()
                    if transf and transf.bodega_destino and transf.bodega_destino.sucursal:
                        suc = transf.bodega_destino.sucursal
                        direccion = suc.direccion
                        comuna = suc.comuna
                        ciudad = suc.ciudad

            etree.SubElement(transporte, "DirDest").text = (direccion or 'DIRECCION DESCONOCIDA')[:70]
            etree.SubElement(transporte, "CmnaDest").text = (comuna or 'COMUNA DESCONOCIDA')[:20]
            etree.SubElement(transporte, "CiudadDest").text = (ciudad or 'SANTIAGO')[:20]

            fecha_salida = getattr(self.documento, 'fecha_salida', None) or getattr(self.documento, 'fecha_emision', None)
            hora_salida = getattr(self.documento, 'hora_salida', None)
            fecha_llegada = getattr(self.documento, 'fecha_llegada', None) or fecha_salida
            if fecha_salida:
                try:
                    etree.SubElement(transporte, "FchSalida").text = fecha_salida.strftime('%Y-%m-%d')
                except Exception:
                    etree.SubElement(transporte, "FchSalida").text = str(fecha_salida)[:10]
            if hora_salida:
                try:
                    etree.SubElement(transporte, "HraSalida").text = hora_salida.strftime('%H:%M:%S')
                except Exception:
                    texto_hora = str(hora_salida).strip()
                    if len(texto_hora) == 5:
                        texto_hora += ':00'
                    etree.SubElement(transporte, "HraSalida").text = texto_hora[:8]
            elif fecha_salida:
                from django.utils import timezone as dj_tz
                etree.SubElement(transporte, "HraSalida").text = dj_tz.localtime().strftime('%H:%M:%S')
            if fecha_llegada:
                try:
                    etree.SubElement(transporte, "FchLlegada").text = fecha_llegada.strftime('%Y-%m-%d')
                except Exception:
                    etree.SubElement(transporte, "FchLlegada").text = str(fecha_llegada)[:10]

        except Exception as e:
            # No romper el flujo si falla: solo loguear.
            print(f"[WARN] Error al generar seccion Transporte: {e}")

    def _datos_chofer(self):
        """Nombre y RUT del chofer desde el DTE, la venta o el maestro de choferes."""
        nombre = (getattr(self.documento, 'nombre_chofer', None) or '').strip()
        rut = ''
        chofer = getattr(self.documento, 'chofer', None)
        if chofer:
            nombre = nombre or (chofer.nombre or '').strip()
            rut = str(chofer.rut or '').replace('.', '').strip()
        venta = getattr(self.documento, 'venta', None)
        if venta:
            venta_chofer = getattr(venta, 'chofer', None)
            if venta_chofer:
                nombre = nombre or (venta_chofer.nombre or '').strip()
                rut = rut or str(venta_chofer.rut or '').replace('.', '').strip()
        if (not nombre or not rut) and isinstance(self.documento, DocumentoTributarioElectronico) and getattr(self.documento, 'pk', None):
            detalle_guia = self.documento.detalles_despacho_guia.select_related(
                'orden_despacho__chofer'
            ).first()
            orden_chofer = getattr(getattr(detalle_guia, 'orden_despacho', None), 'chofer', None)
            if orden_chofer:
                nombre = nombre or (orden_chofer.nombre or '').strip()
                rut = rut or str(orden_chofer.rut or '').replace('.', '').strip()
        from pedidos.models import OrdenDespacho
        if (not nombre or not rut) and isinstance(self.documento, OrdenDespacho) and getattr(self.documento, 'chofer', None):
            orden_chofer = self.documento.chofer
            nombre = nombre or (orden_chofer.nombre or '').strip()
            rut = rut or str(orden_chofer.rut or '').replace('.', '').strip()
        if nombre and not rut:
            try:
                from pedidos.models_transporte import Chofer
                empresa = getattr(self.documento, 'empresa', None) or self.empresa
                encontrado = Chofer.objects.filter(empresa=empresa, nombre__iexact=nombre).first()
                if not encontrado:
                    encontrado = Chofer.objects.filter(empresa=empresa, nombre__icontains=nombre[:18]).first()
                if encontrado:
                    rut = str(encontrado.rut or '').replace('.', '').strip()
                    nombre = (encontrado.nombre or nombre).strip()
            except Exception:
                pass
        return nombre, rut
    
    def _generar_emisor(self, encabezado):
        """Genera datos del emisor"""
        emisor = etree.SubElement(encabezado, "Emisor")
        
        # RUT sin puntos
        rut_emisor = self.empresa.rut.replace('.', '')
        etree.SubElement(emisor, "RUTEmisor").text = rut_emisor
        
        # Para boletas (39/41) usar tags específicos, para facturas usar estándar
        if self.tipo_dte in ['39', '41']:
            # Esquema SII para boletas
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
        
        # Teléfono y CorreoEmisor - NO incluir en boletas (39/41). Guías 52 sí (estructura KreaDTE/SII).
        if self.tipo_dte not in ['39', '41']:
            etree.SubElement(emisor, "Telefono").text = (self.empresa.telefono or "")[:20]
            etree.SubElement(emisor, "CorreoEmisor").text = (self.empresa.email or "")[:80]
        
        if self.tipo_dte not in ['39', '41']:
            from facturacion_electronica.validacion_envio import MENSAJE_ACTECO_INVALIDO, normalizar_acteco
            acteco = normalizar_acteco(getattr(self.empresa, 'codigo_actividad_economica', None))
            if not acteco:
                raise ValueError(MENSAJE_ACTECO_INVALIDO)
            etree.SubElement(emisor, "Acteco").text = acteco
        
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
        documento_persistido = bool(getattr(self.documento, 'pk', None))

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

        # Si el documento es un DTE que proviene de una transferencia
        transf = None
        if isinstance(self.documento, DocumentoTributarioElectronico) and documento_persistido:
            transf = self.documento.transferencias.first()

        if transf and self._es_guia_traslado_interno():
            bodega_dest = transf.bodega_destino
            rut_receptor = rut_receptor or self.empresa.rut
            razon_social = razon_social or self.empresa.razon_social
            giro = giro or self.empresa.giro_sii or self.empresa.giro or 'TRASLADO INTERNO'

            if bodega_dest and bodega_dest.sucursal:
                direccion = direccion or bodega_dest.sucursal.direccion or ''
                comuna = comuna or bodega_dest.sucursal.comuna or ''
                ciudad_recep_transfer = bodega_dest.sucursal.ciudad or ''
            else:
                direccion = direccion or getattr(self.documento, 'direccion_receptor', '') or ''
                comuna = comuna or getattr(self.documento, 'comuna_receptor', '') or ''
                ciudad_recep_transfer = getattr(self.documento, 'ciudad_receptor', '') or ''

            if not direccion:
                direccion = getattr(self.documento, 'direccion_destino', '') or ''
            if not comuna:
                comuna = getattr(self.documento, 'comuna_destino', '') or ''
            if not ciudad_recep_transfer:
                ciudad_recep_transfer = getattr(self.documento, 'ciudad_destino', '') or ''
        else:
            ciudad_recep_transfer = ''

        if not rut_receptor and isinstance(self.documento, DocumentoTributarioElectronico) and documento_persistido:
            if transf:
                # El receptor es la bodega de destino
                bodega_dest = transf.bodega_destino
                if bodega_dest:
                    rut_receptor = self.empresa.rut # Transferencia interna, mismo RUT
                    razon_social = self.empresa.razon_social
                    giro = self.empresa.giro_sii or self.empresa.giro or 'TRASLADO INTERNO'
                    
                    # Primero intentar obtener dirección de la SUCURSAL de la bodega
                    if bodega_dest.sucursal:
                        # Si la sucursal tiene datos, usarlos
                        direccion = bodega_dest.sucursal.direccion or self.empresa.direccion
                        comuna = bodega_dest.sucursal.comuna or self.empresa.comuna
                    else:
                        # Fallback a datos de empresa (aunque usualmente las bodegas tienen sucursal)
                        direccion = self.empresa.direccion
                        comuna = self.empresa.comuna
        
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
        
        # GiroRecep - OBLIGATORIO para facturas y guías según SII y SII
        if self.tipo_dte not in ['39', '41']:
            giro_final = (giro or 'PARTICULAR').strip()
            if not giro_final:
                giro_final = 'PARTICULAR'
            etree.SubElement(receptor, "GiroRecep").text = giro_final[:40]
        
        # Contacto (opcional)
        contacto = ''
        if hasattr(self.documento, 'cliente') and self.documento.cliente:
            contacto = getattr(self.documento.cliente, 'telefono', '') or getattr(self.documento.cliente, 'celular', '')
        if contacto:
            etree.SubElement(receptor, "Contacto").text = str(contacto)[:80]
        
        # Dirección y Comuna (OBLIGATORIOS para facturas y guías)
        if not direccion:
            direccion = 'DIRECCION NO DISPONIBLE'
        if not comuna:
            comuna = 'COMUNA NO DISPONIBLE'
            
        etree.SubElement(receptor, "DirRecep").text = direccion[:70]
        etree.SubElement(receptor, "CmnaRecep").text = comuna[:20]
        # CiudadRecep - incluir para facturas y guías (KreaDTE)
        ciudad_recep = 'SANTIAGO'  # Default
        if hasattr(self.documento, 'cliente') and self.documento.cliente:
            ciudad_recep = getattr(self.documento.cliente, 'ciudad', '') or 'SANTIAGO'
        if hasattr(self.documento, 'ciudad_receptor') and self.documento.ciudad_receptor:
            ciudad_recep = self.documento.ciudad_receptor[:20]
        if ciudad_recep_transfer:
            ciudad_recep = ciudad_recep_transfer[:20]
        etree.SubElement(receptor, "CiudadRecep").text = (ciudad_recep or 'SANTIAGO')[:20]
    
    def _generar_totales(self, encabezado, sum_neto=None):
        """Genera los totales del documento"""
        totales = etree.SubElement(encabezado, "Totales")

        if self._es_guia_sin_valoracion():
            etree.SubElement(totales, "MntTotal").text = "0"
            return
        
        monto_neto, monto_exento, monto_iva, monto_total = self._obtener_montos_documento()

        # Boleta afecta: el detalle se mantiene en bruto, pero el SII repara
        # el documento si Totales no informa los parciales afectos.
        if self.tipo_dte == '39':
            monto_total_final = self._monto_entero(monto_total)
            monto_exento_final = self._monto_entero(monto_exento)
            monto_neto_final = self._monto_entero(monto_neto)
            if monto_neto_final <= 0 and monto_total_final > 0:
                monto_neto_final = int(round((monto_total_final - monto_exento_final) / 1.19))

            iva_final = self._monto_entero(monto_iva)
            if iva_final <= 0 or (monto_neto_final + monto_exento_final + iva_final) != monto_total_final:
                iva_final = monto_total_final - monto_neto_final - monto_exento_final
            if iva_final < 0:
                iva_final = 0

            etree.SubElement(totales, "MntNeto").text = str(monto_neto_final)
            if monto_exento_final > 0:
                etree.SubElement(totales, "MntExe").text = str(monto_exento_final)
            etree.SubElement(totales, "IVA").text = str(iva_final)
            etree.SubElement(totales, "MntTotal").text = str(monto_total_final)
            return
        
        # Si sum_neto está disponible (calculado desde los items), USARLO para MntNeto
        if sum_neto is not None and self.tipo_dte not in ['34', '41']:
            monto_neto = self._monto_entero(sum_neto)

        # Monto Neto - incluir para todos excepto exentos (34, 41)
        if self.tipo_dte not in ['34', '41']:
            etree.SubElement(totales, "MntNeto").text = str(int(round(monto_neto)))
        
        # Monto Exento - incluir para todos
        etree.SubElement(totales, "MntExe").text = str(int(round(monto_exento)))

        iva_final = 0
        if self.tipo_dte in ['33', '39', '52', '56', '61']:
            if self.tipo_dte == '52':
                iva_final = int(round(monto_neto * 0.19))
            elif self.tipo_dte in ['33', '56', '61']:
                # El SII exige IVA = round(Tasa * MntNeto). No reutilizar un IVA
                # calculado sobre precios brutos ni la suma de IVA por línea.
                iva_final = int(round(float(monto_neto) * 0.19)) if monto_neto else 0
            else:
                if monto_iva > 0:
                    iva_final = self._monto_entero(monto_iva)
                elif monto_total > 0:
                    iva_final = self._monto_entero(monto_total) - self._monto_entero(monto_neto) - self._monto_entero(monto_exento)
                if iva_final < 0:
                    iva_final = 0

        # TasaIVA - Solo para facturas y guías (NO boletas 39, 41)
        if self.tipo_dte in ['33', '34', '52', '56', '61'] and iva_final > 0:
            etree.SubElement(totales, "TasaIVA").text = "19"

        if self.tipo_dte in ['33', '39', '52', '56', '61'] and iva_final > 0:
            etree.SubElement(totales, "IVA").text = str(iva_final)

        monto_total_calculado = self._monto_entero(monto_neto) + self._monto_entero(monto_exento) + self._monto_entero(iva_final)
        etree.SubElement(totales, "MntTotal").text = str(int(round(monto_total_calculado)))

    @staticmethod
    def _numero_precio(valor):
        texto = str(valor if valor not in (None, '') else '0').strip()
        if not texto:
            return 0.0
        if ',' in texto:
            texto = texto.replace('.', '').replace(',', '.')
        try:
            return float(texto)
        except (TypeError, ValueError):
            return 0.0

    def _cantidad_precio_item(self, item):
        if hasattr(item, 'item_pedido') and hasattr(item.item_pedido, 'articulo'):
            articulo = item.item_pedido.articulo
            nombre = getattr(articulo, 'nombre', None) or 'Item sin nombre'
            cantidad = self._numero_precio(item.cantidad) or 1.0
            precio = self._numero_precio(item.item_pedido.precio_unitario)
        elif hasattr(item, 'articulo') and item.articulo:
            articulo = item.articulo
            nombre = articulo.nombre or getattr(item, 'descripcion', None) or 'Item sin nombre'
            cantidad = self._numero_precio(item.cantidad) or 1.0
            precio = self._numero_precio(item.precio_unitario)
        else:
            articulo = getattr(item, 'articulo', None)
            nombre = getattr(item, 'descripcion', None) or 'Item sin nombre'
            if not nombre:
                nombre = 'Item sin nombre'
            cantidad = self._numero_precio(getattr(item, 'cantidad', 1)) or 1.0
            precio = self._numero_precio(getattr(item, 'precio_unitario', 0))

        if precio <= 0:
            total = self._numero_precio(
                getattr(item, 'precio_total', 0) or getattr(item, 'total', 0)
            )
            if total > 0 and cantidad > 0:
                precio = total / cantidad
        if precio <= 0 and articulo:
            precio = self._numero_precio(getattr(articulo, 'precio_venta', 0))
            if precio <= 0:
                bruto = self._numero_precio(getattr(articulo, 'precio_final', 0))
                if bruto > 0:
                    precio = bruto / 1.19
        return cantidad, precio, articulo, nombre
    
    def _generar_detalles(self, documento):
        """Genera los detalles (items) del documento"""
        from ventas.models import Venta, NotaCredito, NotaDebito
        from pedidos.models import OrdenDespacho

        items = []
        documento_persistido = bool(getattr(self.documento, 'pk', None))
        # CRÍTICO: Verificar DocumentoTributarioElectronico PRIMERO porque tiene orden_despacho como ManyToMany
        if isinstance(self.documento, DocumentoTributarioElectronico):
            # Flujo desde POS/Despacho: los items vienen de la venta asociada al DTE
            # Primero intentar con la venta directa
            if hasattr(self.documento, 'venta') and self.documento.venta:
                venta_asociada = self.documento.venta
                if venta_asociada and hasattr(venta_asociada, 'ventadetalle_set'):
                    items = venta_asociada.ventadetalle_set.all()
            # Si no hay ninguna de las anteriores, intentar con transferencias
            elif documento_persistido and self.documento.transferencias.exists():
                transf = self.documento.transferencias.first()
                if transf:
                    items = transf.detalles.all()
            elif documento_persistido:
                if str(self.tipo_dte) in ['33', '34']:
                    items_fact = self.documento.detalles_despacho_factura.filter(cantidad__gt=0)
                    if items_fact.exists():
                        items = items_fact
                if not items:
                    items_guia = self.documento.detalles_despacho_guia.filter(cantidad__gt=0)
                    if items_guia.exists():
                        items = items_guia
        elif isinstance(self.documento, Venta):
            items = self.documento.ventadetalle_set.all()
        elif isinstance(self.documento, NotaCredito):
            items = self.documento.items.all()
        elif isinstance(self.documento, OrdenDespacho):
            # Flujo desde orden de despacho: omitir líneas en cero
            items = self.documento.items.filter(cantidad__gt=0)
        elif hasattr(self.documento, 'orden_despacho'):
            # Wrapper con orden_despacho (solo si NO es un ManyRelatedManager)
            # Verificar si orden_despacho es un objeto individual, no un ManyRelatedManager
            if isinstance(self.documento, DocumentoTributarioElectronico) and not documento_persistido:
                orden_despacho = None
            else:
                orden_despacho = self.documento.orden_despacho
            # Si tiene método .all(), es un ManyRelatedManager, usar .first()
            if hasattr(orden_despacho, 'all'):
                orden_despacho = orden_despacho.first()
            if orden_despacho and hasattr(orden_despacho, 'detalleordendespacho_set'):
                items = orden_despacho.detalleordendespacho_set.filter(cantidad__gt=0)
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

        items = [
            item for item in items
            if float(getattr(item, 'cantidad', 1) or 0) > 0
        ]
        if not items:
            raise ValueError("No hay líneas con cantidad mayor a 0 para generar el DTE")

        monto_total_doc = self._monto_entero(
            getattr(self.documento, 'monto_total', None)
            or getattr(self.documento, 'total', 0)
            or 0
        )
        monto_neto_doc = self._monto_entero(
            getattr(self.documento, 'monto_neto', None)
            or getattr(self.documento, 'subtotal', 0)
            or 0
        )

        total_items_raw = 0
        for item in items:
            cantidad_preview, precio_preview, _articulo, _nombre = self._cantidad_precio_item(item)
            total_items_raw += int(round(cantidad_preview * precio_preview))

        tolerancia_boleta = max(1, len(items) or 1)
        boleta_items_son_netos = False
        if self.tipo_dte == '39' and monto_total_doc > 0:
            if abs(total_items_raw - monto_total_doc) <= tolerancia_boleta:
                boleta_items_son_netos = False
            elif monto_neto_doc > 0 and abs(total_items_raw - monto_neto_doc) <= tolerancia_boleta:
                boleta_items_son_netos = True
            elif abs(int(round(total_items_raw * 1.19)) - monto_total_doc) <= (tolerancia_boleta * 2):
                boleta_items_son_netos = True

        # Factura/guía: si la suma de líneas ≈ neto, ya son netos (facturador directo / pedidos).
        # Si la suma ≈ total, son brutos (POS). Nunca asumir bruto solo porque hay IVA.
        factura_items_son_brutos = False
        if self.tipo_dte not in ['39', '41'] and total_items_raw > 0:
            if monto_neto_doc > 0 and abs(total_items_raw - monto_neto_doc) <= tolerancia_boleta:
                factura_items_son_brutos = False
            elif monto_total_doc > 0 and abs(total_items_raw - monto_total_doc) <= tolerancia_boleta:
                factura_items_son_brutos = True
            elif monto_neto_doc > 0 and abs(int(round(total_items_raw / 1.19)) - monto_neto_doc) <= tolerancia_boleta:
                factura_items_son_brutos = True

        total_neto_items = 0
        for index, item in enumerate(items, start=1):
            detalle = etree.SubElement(documento, "Detalle")
            
            # Número de línea
            etree.SubElement(detalle, "NroLinDet").text = str(index)
            
            # Indicador de exención (solo si es documento exento)
            if self.tipo_dte in ['34', '41']:
                etree.SubElement(detalle, "IndExe").text = "1"
            
            cantidad, precio_unitario, articulo, nombre_item = self._cantidad_precio_item(item)
            
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
            elif hasattr(item, 'comentario') and item.comentario:
                descripcion_item = item.comentario
            elif articulo and hasattr(articulo, 'descripcion') and articulo.descripcion:
                descripcion_item = articulo.descripcion
            # Solo incluir DscItem si es diferente del nombre (como KreaDTE: {% if detached.descripcion != detached.producto.nombre %})
            if descripcion_item and descripcion_item != nombre_item:
                etree.SubElement(detalle, "DscItem").text = descripcion_item[:1000]
            
            # Cantidad (sin decimales para SII)
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
            
            if self._es_guia_sin_valoracion():
                monto_final = 0
            elif es_boleta:
                # Para boleta afecta el XML debe ir en bruto. Si la venta viene
                # guardada en neto, la convertimos antes de serializar.
                if self.tipo_dte == '39' and boleta_items_son_netos:
                    precio_final = int(round(precio_unitario * 1.19))
                    monto_final = int(round(cantidad * precio_unitario * 1.19))
                else:
                    precio_final = int(round(precio_unitario))
                    monto_final = int(round(cantidad * precio_unitario))
            else:
                # Factura/Guía: el SII exige neto. El POS suele guardar BRUTO;
                # el facturador directo y los pedidos guardan NETO. No netear dos veces.
                if factura_items_son_brutos:
                    precio_neto = precio_unitario / 1.19
                    precio_final = int(round(precio_neto))
                    monto_final = int(round(cantidad * precio_neto))
                else:
                    precio_final = int(round(precio_unitario))
                    monto_final = int(round(cantidad * precio_unitario))

            if (
                not self._es_guia_sin_valoracion()
                and str(self.tipo_dte) in ('33', '34', '39', '41', '52', '56', '61')
                and (precio_final <= 0 or monto_final <= 0)
            ):
                raise ValueError(
                    f'El producto "{nombre_item}" tiene precio o total 0. '
                    'Este documento no puede emitirse así. '
                    'Corrija el precio del artículo. No se usará un folio.'
                )

            if not self._es_guia_sin_valoracion():
                etree.SubElement(detalle, "PrcItem").text = str(precio_final)
            etree.SubElement(detalle, "MontoItem").text = str(monto_final)
            
            total_neto_items += monto_final

        return total_neto_items
    
    def _generar_referencia(self, documento, obligatorio=False):
        """Genera referencias a otros documentos"""
        from ventas.models import Venta, NotaCredito, NotaDebito

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

        elif isinstance(self.documento, NotaDebito):
            if not (
                self.documento.tipo_doc_afectado and
                self.documento.numero_doc_afectado and
                self.documento.fecha_doc_afectado
            ):
                if obligatorio:
                    raise ValueError("La Nota de Débito requiere un documento de referencia válido")
                return

            referencia = etree.SubElement(documento, "Referencia")
            etree.SubElement(referencia, "NroLinRef").text = "1"
            etree.SubElement(referencia, "TpoDocRef").text = self.documento.tipo_doc_afectado
            etree.SubElement(referencia, "FolioRef").text = str(self.documento.numero_doc_afectado)
            etree.SubElement(referencia, "FchRef").text = self.documento.fecha_doc_afectado.strftime('%Y-%m-%d')

            cod_ref_map = {
                'CORRIGE_TEXTO': '2',
                'AUMENTA_MONTO': '3',
                'INTERESES': '3',
                'OTROS': '3',
            }
            etree.SubElement(referencia, "CodRef").text = cod_ref_map.get(self.documento.tipo_nd, '3')
            etree.SubElement(referencia, "RazonRef").text = (self.documento.motivo or 'Ajuste de documento')[:90]

        # Caso para Venta con modelo VentaReferencia (múltiples referencias o guías consolidadas)
        venta_obj = getattr(self.documento, 'venta', None) if not isinstance(self.documento, Venta) else self.documento
        if venta_obj and hasattr(venta_obj, 'referencias') and venta_obj.referencias.exists():
            nro_lin = 1
            for ref in venta_obj.referencias.all()[:40]:
                tpo_ref = str(ref.tipo_referencia).strip()
                raw_folio = str(ref.folio_referencia).strip()

                # SII exige que para documentos tributarios (tipos numéricos < 800 como 52, 33, 50, etc.)
                # el FolioRef sea estrictamente numérico positivo (> 0). Letras como 'T' causan rechazo RCH -3-821.
                es_doc_tributario = tpo_ref.isdigit() and int(tpo_ref) < 800
                if es_doc_tributario:
                    folio_numerico = re.sub(r'\D', '', raw_folio).lstrip('0')
                    if not folio_numerico:
                        continue
                    folio_final = folio_numerico[:18]
                else:
                    folio_final = raw_folio[:18]

                referencia = etree.SubElement(documento, "Referencia")
                etree.SubElement(referencia, "NroLinRef").text = str(nro_lin)
                etree.SubElement(referencia, "TpoDocRef").text = tpo_ref
                etree.SubElement(referencia, "FolioRef").text = folio_final
                fch = ref.fecha_referencia
                etree.SubElement(referencia, "FchRef").text = fch.strftime('%Y-%m-%d') if hasattr(fch, 'strftime') else str(fch)[:10]
                if ref.razon_referencia:
                    etree.SubElement(referencia, "RazonRef").text = str(ref.razon_referencia)[:90]
                nro_lin += 1

        # Caso para Venta con referencia opcional (ej. Guía de Despacho legacy)
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

        elif obligatorio:
            raise ValueError("El documento requiere al menos una referencia tributaria válida")

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
        from ventas.models import Venta
        venta_obj = getattr(self.documento, 'venta', None) if not isinstance(self.documento, Venta) else self.documento
        tiene_refs = (hasattr(self.documento, 'documento_referencia') and self.documento.documento_referencia) or \
                     (venta_obj and hasattr(venta_obj, 'referencias') and venta_obj.referencias.exists())
        if tiene_refs:
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
        mnt_ted = 0 if self._es_guia_sin_valoracion() else int(self.documento.monto_total)
        etree.SubElement(dd, "MNT").text = str(mnt_ted)
        etree.SubElement(dd, "IT1").text = "DTE" 

        # Agregar CAF placeholder (REQUERIDO por SII en Boletas)
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
