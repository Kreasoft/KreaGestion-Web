"""
Servicio integrador para generación, firma y envío de DTE
"""
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from .models import DocumentoTributarioElectronico, ArchivoCAF, EnvioDTE
from .dte_generator import DTEXMLGenerator  # Usar para boletas
from .firma_electronica import FirmadorDTE
from .cliente_sii import ClienteSII
from .generador_envio import generar_envio_dte
from .sii_crypto import obtener_rut_certificado
from .ted_sii import construir_ted
from .services import FolioService
from .validacion_envio import (
    errores_emisor_para_dte,
    validar_dte_antes_envio,
    validar_precios_items_venta,
    xml_tiene_acteco_invalido,
)
from .pdf417_generator import PDF417Generator
import os
import re
from lxml import etree


def normalizar_error_envio_sii(error):
    """Devuelve un mensaje claro para errores genericos del gateway SII."""
    mensaje = str(error or '').strip()
    if '<RECEPCIONDTE' in mensaje or '<STATUS>' in mensaje:
        errores = re.findall(r'<ERROR>(.*?)</ERROR>', mensaje, flags=re.DOTALL | re.IGNORECASE)
        if errores:
            return ' '.join(e.strip() for e in errores)[:500]
    mensaje_lower = mensaje.lower()
    if (
        (
            'pangal.sii.cl/recursos/v1/boleta.electronica.envio' in mensaje_lower
            or 'error http 500 al enviar boleta al sii' in mensaje_lower
        )
        and ('500 server error' in mensaje_lower or 'error 500' in mensaje_lower)
    ):
        return (
            'Error HTTP 500 al enviar boleta al SII: el endpoint REST de boletas '
            'devolvio Error 500 sin Track ID. El API de consulta/token responde, '
            'por lo que el caso queda aislado al upload/gateway de boletas o al '
            'rango CAF usado en el envio.'
        )
    return mensaje


class DTEService:
    """Servicio principal para gestión de DTE"""
    
    def __init__(self, empresa):
        """
        Inicializa el servicio de DTE
        
        Args:
            empresa: Instancia de Empresa
        """
        self.empresa = empresa
        
        # Verificar que la empresa tenga FE activada
        if not empresa.facturacion_electronica:
            raise ValueError("La empresa no tiene facturación electrónica activada")
        
        # Verificar certificado digital
        if not empresa.certificado_digital:
            raise ValueError("La empresa no tiene certificado digital configurado")
        
        print(f"DTEService inicializado para: {empresa.nombre}")

    @staticmethod
    def _normalizar_tipo_traslado(valor):
        valor = str(valor or '').strip()
        return valor if valor in {'1', '2', '3', '4', '5', '6', '7', '8', '9'} else ''

    @staticmethod
    def _normalizar_rut(rut):
        return str(rut or '').replace('.', '').replace(' ', '').upper()

    def _aplicar_transporte_res154(self, dte, venta=None, **transport_data):
        """Completa TipoDespacho, carro, salida/llegada y RUTTrans (Res. 154 / anexo 2.5)."""
        from datetime import datetime
        from django.utils import timezone
        from core.fechas import parse_fecha

        tipo_despacho_sii = str(transport_data.get('tipo_despacho_sii') or getattr(dte, 'tipo_despacho_sii', '') or '').strip()
        if tipo_despacho_sii not in ('1', '2', '3'):
            tipo_despacho_sii = '2'
        dte.tipo_despacho_sii = tipo_despacho_sii

        patente_carro = (transport_data.get('patente_carro') or getattr(dte, 'patente_carro', '') or '').strip().upper().replace('-', '')[:8]
        dte.patente_carro = patente_carro or None

        fecha_salida = parse_fecha(transport_data.get('fecha_salida')) or getattr(dte, 'fecha_salida', None)
        if not fecha_salida:
            fecha_salida = getattr(venta, 'fecha', None) or getattr(dte, 'fecha_emision', None)
        dte.fecha_salida = fecha_salida

        hora_raw = transport_data.get('hora_salida') or getattr(dte, 'hora_salida', None)
        hora = None
        if hasattr(hora_raw, 'hour') and not hasattr(hora_raw, 'year'):
            hora = hora_raw
        elif hora_raw:
            texto = str(hora_raw).strip()
            for fmt in ('%H:%M:%S', '%H:%M'):
                try:
                    hora = datetime.strptime(texto, fmt).time()
                    break
                except ValueError:
                    continue
        dte.hora_salida = hora or timezone.localtime().time().replace(microsecond=0)
        dte.fecha_llegada = parse_fecha(transport_data.get('fecha_llegada')) or getattr(dte, 'fecha_llegada', None) or fecha_salida

        if not (dte.rut_transportista or '').strip():
            dte.rut_transportista = self._normalizar_rut(self.empresa.rut)
        return dte

    def _receptor_es_cliente_externo(self, dte=None, venta=None, orden_despacho=None):
        rut_emp = self._normalizar_rut(getattr(self.empresa, 'rut', ''))
        rut_rec = ''
        if dte is not None:
            rut_rec = self._normalizar_rut(getattr(dte, 'rut_receptor', ''))
            if not rut_rec:
                cliente_venta = getattr(getattr(dte, 'venta', None), 'cliente', None)
                if cliente_venta:
                    rut_rec = self._normalizar_rut(cliente_venta.rut)
        if not rut_rec and venta is not None:
            cliente_venta = getattr(venta, 'cliente', None)
            if cliente_venta:
                rut_rec = self._normalizar_rut(cliente_venta.rut)
        if not rut_rec and orden_despacho is not None:
            cliente = getattr(getattr(orden_despacho, 'orden_pedido', None), 'cliente', None)
            if cliente:
                rut_rec = self._normalizar_rut(cliente.rut)
        if not rut_emp or not rut_rec:
            return False
        return rut_rec != rut_emp

    def _exigir_emisor_valido(self, tipo_dte):
        errores = errores_emisor_para_dte(self.empresa, tipo_dte)
        if errores:
            raise ValueError(errores[0])

    def _resolver_tipo_traslado_guia(self, venta=None, dte=None, orden_despacho=None):
        for valor in (
            getattr(dte, 'tipo_traslado', None),
            getattr(venta, 'tipo_despacho', None),
            getattr(orden_despacho, 'tipo_traslado', None),
        ):
            tipo = self._normalizar_tipo_traslado(valor)
            if tipo:
                break
        else:
            tipo = ''

        if not tipo and dte is not None:
            xml = (getattr(dte, 'xml_firmado', '') or '') or (getattr(dte, 'xml_dte', '') or '')
            match = re.search(r'<IndTraslado>(\d+)</IndTraslado>', xml)
            if match:
                tipo = self._normalizar_tipo_traslado(match.group(1))

        tipo = tipo or '1'
        if tipo == '5' and self._receptor_es_cliente_externo(dte=dte, venta=venta, orden_despacho=orden_despacho):
            return '1'
        return tipo
    
    def generar_dte_desde_venta(self, venta, tipo_dte='39', **transport_data):
        """
        Genera un DTE completo desde una venta
        
        Args:
            venta: Instancia de Venta
            tipo_dte: Código del tipo de DTE (33, 39, etc.)
            **transport_data: Datos opcionales de transporte (patente_transporte, rut_transportista, nombre_chofer)
            
        Returns:
            DocumentoTributarioElectronico: DTE generado y firmado
        """
        try:
            self._exigir_emisor_valido(tipo_dte)
            error_precios = validar_precios_items_venta(
                venta,
                tipo_dte,
                getattr(venta, 'tipo_despacho', None),
            )
            if error_precios:
                raise ValueError(error_precios)
            with transaction.atomic():
                # 1. Obtener folio - IMPORTANTE: Usar la sucursal de la venta para picking de CAF
                sucursal_venta = getattr(venta, 'sucursal', None)
                print(f"\nPaso 1: Obteniendo folio para tipo {tipo_dte} en sucursal {sucursal_venta}")
                folio, caf = FolioService.obtener_siguiente_folio(self.empresa, tipo_dte, sucursal=sucursal_venta)

                if folio is None:
                    raise ValueError(f"No hay folios disponibles para tipo de documento {tipo_dte}")

                print(f"Folio asignado: {folio}")

                # 2. Generar XML del DTE
                print(f"\nPaso 2: Generando XML del DTE")
                
                # Para boletas (39), guías (52) y facturas (33), usar DTEXMLGenerator con formato compatible SII directo
                if tipo_dte in ['33', '34', '39', '41', '52', '56', '61']:
                    print(f"[DTE] Usando DTEXMLGenerator directo SII para tipo {tipo_dte}")
                    
                    # Crear objeto DTE temporal para el generador
                    from facturacion_electronica.models import DocumentoTributarioElectronico
                    dte_temp = DocumentoTributarioElectronico(
                        empresa=self.empresa,
                        tipo_dte=tipo_dte,
                        folio=folio,
                        fecha_emision=venta.fecha,
                        rut_emisor=self.empresa.rut,
                        razon_social_emisor=self.empresa.razon_social_sii or self.empresa.razon_social,
                        giro_emisor=self.empresa.giro_sii or self.empresa.giro,
                        direccion_emisor=self.empresa.direccion_casa_matriz or self.empresa.direccion,
                        comuna_emisor=self.empresa.comuna_casa_matriz or self.empresa.comuna,
                        rut_receptor=venta.cliente.rut if venta.cliente else '66666666-6',
                        razon_social_receptor=venta.get_cliente_nombre() if hasattr(venta, 'get_cliente_nombre') else (venta.cliente.nombre if venta.cliente else 'Cliente Genérico'),
                        direccion_receptor=venta.cliente.direccion if venta.cliente else '',
                        comuna_receptor=venta.cliente.comuna if venta.cliente else '',
                        giro_receptor=venta.cliente.giro if (venta.cliente and venta.cliente.giro) else 'PARTICULAR',
                        # IndTraslado obligatorio para guias (52). Se guarda en el DTE temporal
                        # para que el XML, la base de datos y la impresion usen el mismo valor.
                        tipo_traslado=self._resolver_tipo_traslado_guia(venta=venta) if tipo_dte == '52' else None,
                        monto_neto=int(venta.neto),
                        monto_iva=int(venta.iva),
                        monto_total=int(venta.total),
                        # Agregar datos de transporte al temporal
                        patente_transporte=transport_data.get('patente_transporte') or (
                            venta.vehiculo.patente if getattr(venta, 'vehiculo', None) else None
                        ),
                        rut_transportista=transport_data.get('rut_transportista'),
                        nombre_chofer=transport_data.get('nombre_chofer') or (
                            venta.chofer.nombre if getattr(venta, 'chofer', None) else None
                        ),
                    )
                    dte_temp.venta = venta  # Asociar venta
                    from core.fechas import calcular_fecha_vencimiento
                    fecha_venc = getattr(venta, 'fecha_vencimiento', None)
                    if not fecha_venc:
                        dias = getattr(venta.cliente, 'plazo_pago', 0) if getattr(venta, 'cliente', None) else 0
                        fecha_venc = calcular_fecha_vencimiento(venta.fecha, dias)
                    dte_temp.fecha_vencimiento = fecha_venc
                    dte_temp.chofer = getattr(venta, 'chofer', None)
                    dte_temp.vehiculo = getattr(venta, 'vehiculo', None)
                    if tipo_dte == '52':
                        if venta and getattr(venta, 'cliente', None) and getattr(venta.cliente, 'ciudad', None):
                            dte_temp.ciudad_receptor = venta.cliente.ciudad
                        self._aplicar_transporte_res154(dte_temp, venta=venta, **transport_data)
                        dte_temp.rut_solicita = obtener_rut_certificado(
                            self.empresa.certificado_digital.path,
                            self.empresa.password_certificado,
                        ) or self.empresa.rut
                    
                    # Generar XML con DTEXMLGenerator (usamos generar_xml para obtener XML limpio sin TED)
                    generator = DTEXMLGenerator(self.empresa, dte_temp, tipo_dte, folio, caf)
                    xml_sin_firmar = generator.generar_xml()
                    totales_xml = DTEXMLGenerator.extraer_totales_xml(xml_sin_firmar)
                    if totales_xml.get('total') or totales_xml.get('neto'):
                        dte_temp.monto_neto = totales_xml['neto']
                        dte_temp.monto_iva = totales_xml['iva']
                        dte_temp.monto_total = totales_xml['total']
                        transport_data['monto_neto'] = totales_xml['neto']
                        transport_data['monto_iva'] = totales_xml['iva']
                        transport_data['monto_total'] = totales_xml['total']
                else:
                    raise ValueError(f"Tipo DTE {tipo_dte} no soportado por el generador SII local")

                print(f"XML generado ({len(xml_sin_firmar)} bytes)")

                # 3. Generar TED (Timbre Electronico)
                print(f"\nPaso 3: Generando TED")
                firmador = self._obtener_firmador()
                ted_xml = self._generar_ted(
                    venta, tipo_dte, folio, caf, firmador,
                    monto_total=transport_data.get('monto_total'),
                )
                xml_sin_firmar = self._insertar_ted_y_tmstfirma(xml_sin_firmar, ted_xml)

                print(f"TED generado e insertado en XML")

                # 4. Firmar el XML completo (Documento ya contiene TED/TmstFirma)
                print(f"\nPaso 4: Firmando XML")
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                print(f"XML firmado")

                # 5. Generar datos para PDF417
                print(f"\nPaso 5: Generando datos PDF417")
                pdf417_data = firmador.generar_datos_pdf417(ted_xml)
                
                # 6. Crear registro del DTE (ahora SIEMPRE guardamos, incluso en modo reutilizacion)
                print(f"\nPaso 6: Guardando DTE en base de datos")
                dte = self._crear_registro_dte(
                    venta=venta,
                    tipo_dte=tipo_dte,
                    folio=folio,
                    caf=caf,
                    xml_sin_firmar=xml_sin_firmar,
                    xml_firmado=xml_firmado,
                    ted_xml=ted_xml,
                    pdf417_data=pdf417_data,
                    **transport_data
                )

                print(f"DTE guardado - ID: {dte.id}")

                # 7. Generar imagen PDF417 del timbre
                print(f"\nPaso 7: Generando imagen PDF417")
                PDF417Generator.guardar_pdf417_en_dte(dte)

                print(f"\nDTE generado exitosamente: Tipo {tipo_dte}, Folio {folio}")
                
                return dte
                
        except Exception as e:
            print(f"\nError al generar DTE: {str(e)}")
            raise

    def procesar_dte_existente(self, dte):
        """
        Procesa un DTE ya creado, generando XML, firmando y timbrando.
        """
        try:
            with transaction.atomic():
                venta = dte.venta
                transferencia = None
                nota_credito = None
                nota_debito = None
                orden_despacho = None
                documento_fuente = dte

                if not venta:
                    transferencia = dte.transferencias.first()
                    from pedidos.models_despacho import DetalleOrdenDespacho
                    detalle_despacho = (
                        DetalleOrdenDespacho.objects.filter(guia_despacho=dte, cantidad__gt=0)
                        .select_related('orden_despacho', 'orden_despacho__orden_pedido__cliente')
                        .first()
                    )
                    if not detalle_despacho:
                        detalle_despacho = (
                            DetalleOrdenDespacho.objects.filter(guia_despacho=dte)
                            .select_related('orden_despacho', 'orden_despacho__orden_pedido__cliente')
                            .first()
                        )
                    if not detalle_despacho:
                        detalle_despacho = (
                            DetalleOrdenDespacho.objects.filter(factura=dte, cantidad__gt=0)
                            .select_related('orden_despacho', 'orden_despacho__orden_pedido__cliente')
                            .first()
                        )
                    if not detalle_despacho:
                        detalle_despacho = (
                            DetalleOrdenDespacho.objects.filter(factura=dte)
                            .select_related('orden_despacho', 'orden_despacho__orden_pedido__cliente')
                            .first()
                        )
                    if detalle_despacho:
                        orden_despacho = detalle_despacho.orden_despacho

                if dte.tipo_dte == '61':
                    nota_credito = dte.notas_credito.first()
                    if nota_credito:
                        documento_fuente = nota_credito
                        dte.fecha_emision = nota_credito.fecha
                        dte.rut_receptor = nota_credito.cliente.rut
                        dte.razon_social_receptor = nota_credito.cliente.nombre
                        dte.direccion_receptor = nota_credito.cliente.direccion or ''
                        dte.comuna_receptor = nota_credito.cliente.comuna or ''
                        dte.ciudad_receptor = getattr(nota_credito.cliente, 'ciudad', '') or ''
                        dte.giro_receptor = getattr(nota_credito.cliente, 'giro', '') or ''
                        dte.monto_neto = nota_credito.subtotal
                        dte.monto_iva = nota_credito.iva
                        dte.monto_total = nota_credito.total
                elif dte.tipo_dte == '56':
                    nota_debito = dte.notas_debito.first()
                    if nota_debito:
                        documento_fuente = nota_debito
                        dte.fecha_emision = nota_debito.fecha
                        dte.rut_receptor = nota_debito.cliente.rut
                        dte.razon_social_receptor = nota_debito.cliente.nombre
                        dte.direccion_receptor = nota_debito.cliente.direccion or ''
                        dte.comuna_receptor = nota_debito.cliente.comuna or ''
                        dte.ciudad_receptor = getattr(nota_debito.cliente, 'ciudad', '') or ''
                        dte.giro_receptor = getattr(nota_debito.cliente, 'giro', '') or ''
                        dte.monto_neto = nota_debito.subtotal
                        dte.monto_iva = nota_debito.iva
                        dte.monto_total = nota_debito.total

                if venta:
                    documento_fuente = dte
                elif transferencia:
                    documento_fuente = dte
                elif orden_despacho:
                    cliente = getattr(getattr(orden_despacho, 'orden_pedido', None), 'cliente', None)
                    campos = []
                    if cliente:
                        if not (dte.giro_receptor or '').strip():
                            dte.giro_receptor = getattr(cliente, 'giro', '') or 'SIN GIRO'
                            campos.append('giro_receptor')
                        dir_actual = (dte.direccion_receptor or '').strip()
                        if not dir_actual or 'DESCONOCIDA' in dir_actual.upper() or 'NO DISPONIBLE' in dir_actual.upper():
                            dte.direccion_receptor = (orden_despacho.direccion_entrega or cliente.direccion or '')[:200]
                            campos.append('direccion_receptor')
                        comuna_actual = (dte.comuna_receptor or '').strip()
                        if not comuna_actual or 'DESCONOCIDA' in comuna_actual.upper() or 'NO DISPONIBLE' in comuna_actual.upper():
                            dte.comuna_receptor = (cliente.comuna if isinstance(cliente.comuna, str) else '')[:20]
                            campos.append('comuna_receptor')
                        if not (dte.ciudad_receptor or '').strip():
                            dte.ciudad_receptor = getattr(cliente, 'ciudad', '') or ''
                            campos.append('ciudad_receptor')
                        if not (dte.rut_receptor or '').strip() and cliente.rut:
                            dte.rut_receptor = cliente.rut
                            campos.append('rut_receptor')
                        if not (dte.razon_social_receptor or '').strip():
                            dte.razon_social_receptor = cliente.nombre
                            campos.append('razon_social_receptor')
                    if getattr(orden_despacho, 'chofer', None):
                        dte.chofer = orden_despacho.chofer
                        dte.nombre_chofer = orden_despacho.chofer.nombre
                        campos.extend(['chofer', 'nombre_chofer'])
                    if getattr(orden_despacho, 'vehiculo', None):
                        dte.vehiculo = orden_despacho.vehiculo
                        dte.patente_transporte = orden_despacho.vehiculo.patente
                        campos.extend(['vehiculo', 'patente_transporte'])
                    if campos:
                        dte.save(update_fields=list(dict.fromkeys(campos)))
                    documento_fuente = dte
                elif not nota_credito and not nota_debito:
                    raise NotImplementedError(
                        "Solo se soporta regenerar DTE desde Venta, Transferencia, Orden de Despacho, Nota de Crédito o Nota de Débito"
                    )
                
                if dte.tipo_dte == '52':
                    tipo_traslado = self._resolver_tipo_traslado_guia(
                        venta=venta, dte=dte, orden_despacho=orden_despacho
                    )
                    actualizar_dte = dte.tipo_traslado != tipo_traslado
                    dte.tipo_traslado = tipo_traslado
                    dte.rut_solicita = obtener_rut_certificado(
                        self.empresa.certificado_digital.path,
                        self.empresa.password_certificado,
                    ) or self.empresa.rut
                    if actualizar_dte:
                        dte.save(update_fields=['tipo_traslado'])
                    if venta and not venta.tipo_despacho:
                        venta.tipo_despacho = tipo_traslado
                        venta.save(update_fields=['tipo_despacho'])

                # Para boletas (39), guias (52) y facturas (33), usar DTEXMLGenerator
                if dte.tipo_dte in ['33', '34', '39', '41', '52', '56', '61']:
                    print(f"[DTE] Regenerando documento {dte.tipo_dte} folio {dte.folio} con DTEXMLGenerator directo SII")
                    
                    # Para notas usar la nota asociada, ya que el generador toma ítems y referencias desde ese modelo.
                    generator = DTEXMLGenerator(self.empresa, documento_fuente, dte.tipo_dte, dte.folio, dte.caf_utilizado)
                    xml_sin_firmar = generator.generar_xml()
                    totales_xml = DTEXMLGenerator.extraer_totales_xml(xml_sin_firmar)
                    if totales_xml.get('total') or totales_xml.get('neto'):
                        dte.monto_neto = totales_xml['neto']
                        dte.monto_iva = totales_xml['iva']
                        dte.monto_exento = totales_xml.get('exento') or 0
                        dte.monto_total = totales_xml['total']
                else:
                    raise ValueError(f"Tipo DTE {dte.tipo_dte} no soportado por el generador SII local")

                # 2. Generar TED e insertarlo en Documento antes de firmar
                firmador = self._obtener_firmador()
                ted_xml = self._generar_ted_desde_dte(dte, firmador)
                xml_sin_firmar = self._insertar_ted_y_tmstfirma(xml_sin_firmar, ted_xml)

                # 3. Firmar el XML completo
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                # 4. Generar datos para PDF417
                pdf417_data = firmador.generar_datos_pdf417(ted_xml)

                # 5. Actualizar registro del DTE
                dte.xml_dte = xml_sin_firmar
                dte.xml_firmado = xml_firmado
                dte.timbre_electronico = ted_xml
                dte.datos_pdf417 = pdf417_data
                dte.estado_sii = 'generado'
                dte.save()

                # 6. Generar imagen PDF417 del timbre
                PDF417Generator.guardar_pdf417_en_dte(dte)

                return dte
        except Exception as e:
            print(f"\nError al procesar DTE existente: {str(e)}")
            raise

    def generar_dte_desde_nota_credito(self, nota_credito, items):
        """
        Genera un DTE de Nota de Crédito (tipo 61)
        """
        TIPO_DTE_NC = '61'
        try:
            self._exigir_emisor_valido(TIPO_DTE_NC)
            with transaction.atomic():
                # 1. Obtener folio y asignarlo como número de la nota de crédito
                folio, caf = FolioService.obtener_siguiente_folio(self.empresa, TIPO_DTE_NC)
                if folio is None:
                    raise ValueError("No hay folios disponibles para Notas de Crédito (61)")
                
                nota_credito.numero = folio
                nota_credito.save() # Guardar la nota de crédito para obtener un ID

                # 2. Guardar los items y asociarlos a la nota de crédito
                for item in items:
                    item.nota_credito = nota_credito
                    # Completar datos del artículo si no están
                    if not item.codigo:
                        item.codigo = item.articulo.codigo
                    if not item.descripcion:
                        item.descripcion = item.articulo.nombre
                    item.save()
                
                # 3. Calcular totales ahora que los items están guardados
                nota_credito.calcular_totales()
                nota_credito.save()

                # 4. Generar XML (generador SII local)
                items_dte = []
                for item in items:
                    items_dte.append({
                        'nombre': item.descripcion,
                        'cantidad': float(item.cantidad),
                        'precio': float(item.precio_unitario), # Verificar si es neto
                        'exento': False,
                        'unidad': item.articulo.unidad_medida.simbolo if (item.articulo and item.articulo.unidad_medida) else '',
                    })
                
                referencias = []
                # Intentar extraer referencia de los campos del modelo
                if nota_credito.tipo_doc_afectado and nota_credito.numero_doc_afectado:
                    # Mapear código de referencia según tipo_nc
                    # 1: ANULA, 2: CORRIGE TEXTO, 3: CORRIGE MONTO
                    map_codigo_ref = {
                        'ANULA': '1',
                        'CORRIGE_TEXTO': '2',
                        'CORRIGE_MONTO': '3',
                    }
                    codigo_ref = map_codigo_ref.get(nota_credito.tipo_nc, '1')
                    
                    referencias.append({
                        'tipo_documento': nota_credito.tipo_doc_afectado,
                        'folio': int(nota_credito.numero_doc_afectado),
                        'fecha': nota_credito.fecha_doc_afectado.strftime('%Y-%m-%d') if nota_credito.fecha_doc_afectado else nota_credito.fecha.strftime('%Y-%m-%d'),
                        'codigo_referencia': codigo_ref,
                        'razon': nota_credito.motivo[:90] if nota_credito.motivo else 'Corrección/Anulación de documento',
                    })
                elif hasattr(nota_credito, 'factura') and nota_credito.factura:
                     # Fallback para compatibilidad con código antiguo
                     referencias.append({
                         'tipo_documento': '33',
                         'folio': nota_credito.factura.numero,
                         'fecha': nota_credito.factura.fecha.strftime('%Y-%m-%d'),
                         'codigo_referencia': '1',
                         'razon': 'Anula factura',
                     })
                generator = DTEXMLGenerator(self.empresa, nota_credito, TIPO_DTE_NC, folio, caf)
                xml_sin_firmar = generator.generar_xml()

                # 5. Generar TED e insertarlo antes de firmar
                firmador = self._obtener_firmador()
                ted_xml = self._generar_ted_nc(nota_credito, TIPO_DTE_NC, folio, caf, firmador)
                xml_sin_firmar = self._insertar_ted_y_tmstfirma(xml_sin_firmar, ted_xml)

                # 6. Firmar el XML completo
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                # 7. Generar datos para PDF417
                pdf417_data = firmador.generar_datos_pdf417(ted_xml)

                # 8. Crear registro del DTE
                dte = self._crear_registro_dte_nc(
                    nota_credito=nota_credito,
                    tipo_dte=TIPO_DTE_NC,
                    folio=folio,
                    caf=caf,
                    xml_sin_firmar=xml_sin_firmar,
                    xml_firmado=xml_firmado,
                    ted_xml=ted_xml,
                    pdf417_data=pdf417_data
                )

                # 9. Generar imagen PDF417 del timbre
                PDF417Generator.guardar_pdf417_en_dte(dte)

                # 10. Asociar DTE a la Nota de Crédito (ya está asociada en _crear_registro_dte_nc)
                nota_credito.dte = dte
                nota_credito.save(update_fields=['dte'])

                return dte
        except Exception as e:
            print(f"\nError al generar DTE de Nota de Crédito: {str(e)}")
            raise
    
    def generar_dte_desde_nota_debito(self, nota_debito, items):
        """
        Genera un DTE de Nota de Débito (tipo 56)
        """
        TIPO_DTE_ND = '56'
        try:
            self._exigir_emisor_valido(TIPO_DTE_ND)
            with transaction.atomic():
                # 1. Obtener folio y asignarlo como número de la nota de débito
                folio, caf = FolioService.obtener_siguiente_folio(self.empresa, TIPO_DTE_ND)
                if folio is None:
                    raise ValueError("No hay folios disponibles para Notas de Débito (56)")
                
                nota_debito.numero = folio
                nota_debito.save() # Guardar la nota de débito para obtener un ID

                # 2. Guardar los items y asociarlos a la nota de débito
                for item in items:
                    item.nota_debito = nota_debito
                    # Completar datos del artículo si no están
                    if not item.codigo and item.articulo:
                        item.codigo = item.articulo.codigo
                    if not item.descripcion and item.articulo:
                        item.descripcion = item.articulo.nombre
                    item.save()
                
                # 3. Calcular totales ahora que los items están guardados
                nota_debito.calcular_totales()
                nota_debito.save()

                # 4. Generar XML (generador SII local)
                items_dte = []
                for item in items:
                    items_dte.append({
                        'nombre': item.descripcion,
                        'cantidad': float(item.cantidad),
                        'precio': float(item.precio_unitario),
                        'exento': False,
                        'unidad': getattr(item.articulo, 'unidad_medida', '') if item.articulo else '',
                    })
                
                referencias = []
                if nota_debito.tipo_doc_afectado and nota_debito.numero_doc_afectado:
                    # Código de referencia para nota de débito: usualmente '3' para corrección de montos
                    referencias.append({
                        'tipo_documento': nota_debito.tipo_doc_afectado,
                        'folio': int(nota_debito.numero_doc_afectado),
                        'fecha': nota_debito.fecha_doc_afectado.strftime('%Y-%m-%d') if nota_debito.fecha_doc_afectado else nota_debito.fecha.strftime('%Y-%m-%d'),
                        'codigo_referencia': '3', 
                        'razon': nota_debito.motivo[:90] if nota_debito.motivo else 'Corrección de monto',
                    })
                generator = DTEXMLGenerator(self.empresa, nota_debito, TIPO_DTE_ND, folio, caf)
                xml_sin_firmar = generator.generar_xml()

                # 5. Generar TED e insertarlo antes de firmar
                firmador = self._obtener_firmador()
                ted_xml = self._generar_ted_nd(nota_debito, TIPO_DTE_ND, folio, caf, firmador)
                xml_sin_firmar = self._insertar_ted_y_tmstfirma(xml_sin_firmar, ted_xml)

                # 6. Firmar el XML completo
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                # 7. Generar datos para PDF417
                pdf417_data = firmador.generar_datos_pdf417(ted_xml)

                # 8. Crear registro del DTE
                dte = self._crear_registro_dte_nd(
                    nota_debito=nota_debito,
                    tipo_dte=TIPO_DTE_ND,
                    folio=folio,
                    caf=caf,
                    xml_sin_firmar=xml_sin_firmar,
                    xml_firmado=xml_firmado,
                    ted_xml=ted_xml,
                    pdf417_data=pdf417_data
                )

                # 9. Generar imagen PDF417 del timbre
                PDF417Generator.guardar_pdf417_en_dte(dte)

                # 10. Asociar DTE a la Nota de Débito
                nota_debito.dte = dte
                nota_debito.save(update_fields=['dte'])

                return dte
        except Exception as e:
            print(f"\nError al generar DTE de Nota de Débito: {str(e)}")
            raise
    
    def enviar_dte_al_sii(self, dte):
        """
        Envia un DTE directamente al SII, sin intermediarios.
        """
        try:
            print(f"\n[DTE] Enviando directo al SII - Tipo {dte.tipo_dte}, Folio {dte.folio}")

            if not self.empresa.certificado_digital:
                raise ValueError(f"La empresa {self.empresa.nombre} no tiene certificado digital configurado")
            if not self.empresa.password_certificado:
                raise ValueError(f"La empresa {self.empresa.nombre} no tiene contrasena de certificado configurada")

            if dte.tipo_dte in ['52', '56', '61']:
                try:
                    print(f"[ENVIO] Regenerando XML de DTE {dte.tipo_dte} folio {dte.folio} antes del envio para asegurar estructura vigente.")
                    self.procesar_dte_existente(dte)
                    dte.refresh_from_db()
                except Exception as e:
                    print(f"[ERROR PRE-ENVIO] No se pudo regenerar el DTE antes del envio: {e}")

                giro_recep = getattr(dte, 'giro_receptor', '') or ''
                if dte.tipo_dte == '52' and not giro_recep:
                    try:
                        if dte.venta and dte.venta.cliente and getattr(dte.venta.cliente, 'giro', None):
                            dte.giro_receptor = dte.venta.cliente.giro
                        else:
                            transf = dte.transferencias.first()
                            if transf and transf.empresa:
                                dte.giro_receptor = transf.empresa.giro_sii or transf.empresa.giro or 'TRASLADO INTERNO'
                            else:
                                dte.giro_receptor = 'SIN GIRO'
                        dte.save(update_fields=['giro_receptor'])
                        self.procesar_dte_existente(dte)
                        dte.refresh_from_db()
                    except Exception as e:
                        print(f"[ERROR PRE-ENVIO] No se pudo asegurar GiroRecep: {e}")

            xml_para_enviar = (dte.xml_firmado or '').strip() or (dte.xml_dte or '').strip()
            xml_incompleto = not xml_para_enviar
            if not xml_incompleto and xml_tiene_acteco_invalido(xml_para_enviar):
                xml_incompleto = True
                print(f"[ENVIO] XML de DTE {dte.folio} tiene Acteco invalido. Regenerando.")
            if not xml_incompleto and dte.tipo_dte == '52' and '<DirRecep' not in xml_para_enviar:
                xml_incompleto = True
                print(f"[ENVIO] XML de guia {dte.folio} no contiene direccion del receptor. Regenerando.")
            if not xml_incompleto and dte.tipo_dte == '52' and '<Chofer>' in xml_para_enviar and '<RUTChofer>' not in xml_para_enviar:
                xml_incompleto = True
                print(f"[ENVIO] XML de guia {dte.folio} tiene Chofer invalido (sin RUTChofer). Regenerando.")
                if not (dte.nombre_chofer or '').strip():
                    match_chofer = re.search(r'<Chofer>([^<]+)</Chofer>', xml_para_enviar)
                    if match_chofer:
                        dte.nombre_chofer = match_chofer.group(1).strip()[:100]
                        dte.save(update_fields=['nombre_chofer'])
            if not xml_incompleto and dte.tipo_dte == '52' and re.search(r'<QtyItem>\s*0(\.0+)?\s*</QtyItem>', xml_para_enviar):
                xml_incompleto = True
                print(f"[ENVIO] XML de guia {dte.folio} tiene QtyItem=0. Regenerando.")

            if xml_incompleto:
                self.procesar_dte_existente(dte)
                dte.refresh_from_db()
                xml_para_enviar = (dte.xml_firmado or '').strip() or (dte.xml_dte or '').strip()

            if not xml_para_enviar:
                raise ValueError(f"No se puede enviar el DTE {dte.folio} porque el XML esta vacio")

            if '<TED' not in xml_para_enviar or '<TmstFirma>' not in xml_para_enviar:
                print(f"[ENVIO] XML de DTE {dte.folio} no contiene TED/TmstFirma. Regenerando.")
                self.procesar_dte_existente(dte)
                dte.refresh_from_db()
                xml_para_enviar = (dte.xml_firmado or '').strip() or (dte.xml_dte or '').strip()

            es_valido, error_validacion = validar_dte_antes_envio(dte)
            if not es_valido:
                raise ValueError(error_validacion)

            return self._enviar_sii_directo(dte, xml_para_enviar)

        except Exception as e:
            mensaje_error = normalizar_error_envio_sii(e)
            print(f"Error al enviar DTE directo al SII: {mensaje_error}")
            modo_reutilizacion = getattr(self.empresa, 'modo_reutilizacion_folios', False)
            es_certificacion = self.empresa.ambiente_sii == 'certificacion'
            if not (modo_reutilizacion and es_certificacion):
                with transaction.atomic():
                    from .clasificacion_sii import es_espera_reintento_sii, extraer_track_id
                    dte.estado_sii = 'error_envio'
                    dte.error_envio = mensaje_error
                    campos = ['estado_sii', 'error_envio']
                    if es_espera_reintento_sii(mensaje_error):
                        dte.estado_sii = 'enviado'
                        dte.glosa_sii = mensaje_error[:500]
                        campos.append('glosa_sii')
                        track_glosa = extraer_track_id(mensaje_error)
                        if track_glosa and not str(dte.track_id or '').strip():
                            dte.track_id = track_glosa
                            campos.append('track_id')
                    dte.save(update_fields=campos)
            raise Exception(mensaje_error) from e

    def _enviar_sii_directo(self, dte, xml_para_enviar):
        """Construye el sobre oficial y lo sube directamente al SII."""
        certificado_path = self.empresa.certificado_digital.path
        password = self.empresa.password_certificado
        ambiente = (self.empresa.ambiente_sii or 'certificacion').upper()
        ambiente_sii = 'PRODUCCION' if ambiente == 'PRODUCCION' else 'CERTIFICACION'
        cliente_sii = ClienteSII(
            ambiente=ambiente_sii,
            pfx_path=certificado_path,
            pfx_password=password,
        )

        rut_envia = obtener_rut_certificado(certificado_path, password) or self.empresa.rut
        fecha_resolucion = self.empresa.resolucion_fecha
        numero_resolucion = int(self.empresa.resolucion_numero or 0)

        # En certificacion, la caratula debe usar exactamente la resolucion
        # registrada por el SII para el contribuyente, o el envio cae en CRT-3-19.
        if ambiente_sii == 'CERTIFICACION':
            datos_resolucion = cliente_sii.obtener_datos_resolucion_empresa(self.empresa.rut)
            if datos_resolucion:
                fecha_resolucion = datos_resolucion['fecha']
                numero_resolucion = int(datos_resolucion['numero'] or 0)

                if (
                    self.empresa.resolucion_fecha != fecha_resolucion
                    or int(self.empresa.resolucion_numero or 0) != numero_resolucion
                ):
                    self.empresa.resolucion_fecha = fecha_resolucion
                    self.empresa.resolucion_numero = numero_resolucion
                    self.empresa.save(update_fields=['resolucion_fecha', 'resolucion_numero'])

        fecha_resolucion_str = fecha_resolucion.strftime('%Y-%m-%d') if fecha_resolucion else '2014-08-22'

        xml_envio = generar_envio_dte(
            [xml_para_enviar],
            self.empresa.rut,
            rut_envia,
            certificado_path,
            password,
            fecha_resolucion_str,
            numero_resolucion,
        )
        from .clasificacion_sii import es_espera_reintento_sii, extraer_track_id

        tipo_envio = 'BOLETA' if str(dte.tipo_dte) in ['39', '41'] else 'DTE'
        resultado = cliente_sii.enviar_dte(
            xml_envio,
            rut_emisor=self.empresa.rut,
            rut_envia=rut_envia,
            tipo_envio=tipo_envio,
        )

        xml_respuesta = resultado.get('xml_respuesta') or ''
        if not resultado.get('success') and es_espera_reintento_sii(xml_respuesta, resultado.get('estado')):
            track_espera = extraer_track_id(xml_respuesta, resultado.get('estado')) or resultado.get('track_id')
            if track_espera:
                resultado = {
                    'success': True,
                    'track_id': track_espera,
                    'xml_respuesta': xml_respuesta,
                    'estado': resultado.get('estado'),
                }

        if resultado.get('success'):
            track_id = resultado.get('track_id')
            print(f"DTE enviado exitosamente directo al SII - Track ID: {track_id}")
            with transaction.atomic():
                dte.estado_sii = 'enviado'
                dte.track_id = track_id
                dte.fecha_envio_sii = timezone.now()
                dte.respuesta_sii = resultado.get('xml_respuesta', '')
                dte.error_envio = ''
                dte.save()

            # EPR solo confirma recepción. Consultar si el DTE fue RCH/RPR/DOK.
            try:
                estado = self.consultar_estado_dte(dte)
                dte.refresh_from_db()
            except Exception as e_est:
                print(f"[ENVIO] Enviado (track {track_id}) pero no se pudo consultar estado: {e_est}")

            return {
                'success': True,
                'track_id': track_id,
                'xml_respuesta': resultado.get('xml_respuesta'),
                'estado_sii': dte.estado_sii,
            }

        raise Exception(resultado.get('xml_respuesta') or resultado.get('estado') or 'El SII no devolvio Track ID')

    def consultar_estado_dte(self, dte):
        """
        Consulta el estado de un DTE en el SII
        
        Args:
            dte: Instancia de DocumentoTributarioElectronico
            
        Returns:
            dict: Estado del DTE
        """
        try:
            print(f"\nConsultando estado del DTE - Track ID: {dte.track_id}")

            # Inicializar cliente SII con certificado para poder consultar estado real
            cliente_sii = ClienteSII(
                ambiente=self.empresa.ambiente_sii,
                pfx_path=self.empresa.certificado_digital.path,
                pfx_password=self.empresa.password_certificado,
            )

            # Consultar estado según tipo de documento
            if dte.tipo_dte in ['39', '41']:
                if not dte.track_id:
                    raise ValueError("La boleta no tiene Track ID para consulta en SII.")
                estado = cliente_sii.consultar_estado_boleta(
                    track_id=dte.track_id,
                    rut_emisor=self.empresa.rut,
                    folio=dte.folio,
                )
            else:
                if not dte.track_id:
                    raise ValueError("El DTE no tiene Track ID. Debe ser enviado primero.")
                # Obtener firmador y token para la consulta SOAP de DTE
                firmador = self._obtener_firmador()
                semilla = cliente_sii.obtener_semilla()
                token = cliente_sii.obtener_token(semilla, firmador)
                estado = cliente_sii.consultar_estado_dte(
                    track_id=dte.track_id,
                    token=token,
                    rut_emisor=self.empresa.rut
                )
                estado_up = str(estado.get('estado') or '').strip()
                if estado_up in {'-11', 'FAU', ''} or not (estado.get('aceptados') or estado.get('rechazados') or estado.get('reparos')):
                    try:
                        por_folio = cliente_sii.consultar_estado_por_folio(
                            self.empresa.rut,
                            dte.rut_receptor,
                            dte.tipo_dte,
                            dte.folio,
                            dte.fecha_emision,
                            dte.monto_total,
                        )
                        if por_folio.get('estado') or por_folio.get('glosa'):
                            estado['detalle_estado'] = por_folio.get('estado')
                            if por_folio.get('glosa'):
                                estado['glosa'] = por_folio.get('glosa')
                            if por_folio.get('estado') and estado_up in {'-11', ''}:
                                estado['estado'] = por_folio.get('estado')
                            if por_folio.get('xml_respuesta'):
                                estado['xml_respuesta'] = (
                                    (estado.get('xml_respuesta') or '') + '\n' + por_folio['xml_respuesta']
                                )
                    except Exception as exc:
                        print(f"[CONSULTA] getEstDte no disponible para folio {dte.folio}: {exc}")

            # Actualizar estado del DTE (solo si NO está en modo prueba)
            modo_reutilizacion = self.empresa.modo_reutilizacion_folios
            es_certificacion = self.empresa.ambiente_sii == 'certificacion'

            if not (modo_reutilizacion and es_certificacion):
                with transaction.atomic():
                    estado_sii = str(estado.get('estado') or '').strip().upper()
                    glosa_original = str(estado.get('glosa') or '').strip()
                    glosa_sii = glosa_original.upper()
                    estado_texto = f"{estado_sii} {glosa_sii} {estado.get('detalle_estado') or ''}"
                    aceptados = int(estado.get('aceptados') or 0)
                    rechazados = int(estado.get('rechazados') or 0)
                    reparos = int(estado.get('reparos') or 0)
                    detalle_estado = str(estado.get('detalle_estado') or '').strip().upper()

                    from .clasificacion_sii import (
                        contiene_codigo_estado,
                        es_dte_no_recibido_sii,
                        es_espera_reintento_sii,
                        es_glosa_envio_procesado,
                        evidencia_rechazo_tributario,
                        extraer_track_id,
                    )

                    if es_espera_reintento_sii(estado_texto):
                        dte.estado_sii = 'enviado'
                        track_glosa = extraer_track_id(estado_texto)
                        if track_glosa and not str(dte.track_id or '').strip():
                            dte.track_id = track_glosa
                    elif detalle_estado in {'RCH', 'RSC'} or rechazados > 0 or evidencia_rechazo_tributario(estado_texto):
                        dte.estado_sii = 'rechazado'
                        if not glosa_original:
                            glosa_original = 'Rechazado por SII (RCH)'
                    elif detalle_estado in {'RLV', 'RPR', 'RPC'} or reparos > 0:
                        dte.estado_sii = 'aceptado_reparos'
                    elif aceptados > 0:
                        dte.estado_sii = 'aceptado'
                    elif any(token in estado_texto for token in ['ACEPTADO CON REPAROS', 'ACEPTADA CON REPAROS']) or contiene_codigo_estado(estado_texto, ('RPR', 'RPC', 'RLV')):
                        dte.estado_sii = 'aceptado_reparos'
                    elif any(token in estado_texto for token in ['ACEPTADO', 'ACEPTADA', 'DTE ACEPTADO']) or contiene_codigo_estado(estado_texto, ('EOK', 'DOK', 'SOK')):
                        dte.estado_sii = 'aceptado'
                    elif es_glosa_envio_procesado(estado_texto) or estado_sii in {'EPR'}:
                        dte.estado_sii = 'enviado'

                    glosa_previa = (dte.glosa_sii or '').strip()
                    if es_dte_no_recibido_sii(estado_texto) and not glosa_original:
                        glosa_original = f'{estado_sii}: DTE No Recibido'.strip(': ')
                    elif es_dte_no_recibido_sii(estado_texto) and 'NO RECIBIDO' not in glosa_original.upper():
                        glosa_original = f'{glosa_original} ({estado_sii})'.strip()

                    # No borrar glosa útil (espera 900s / track) si la consulta nueva viene vacía o es FAU sintético.
                    if glosa_original:
                        if es_espera_reintento_sii(glosa_previa) and not evidencia_rechazo_tributario(glosa_original, estado_texto):
                            if es_dte_no_recibido_sii(estado_texto) or es_espera_reintento_sii(glosa_original):
                                pass
                            else:
                                dte.glosa_sii = glosa_original
                        else:
                            dte.glosa_sii = glosa_original
                    dte.fecha_consulta_estado = timezone.now()
                    if estado.get('xml_respuesta'):
                        dte.respuesta_sii = estado.get('xml_respuesta')
                    fecha_recepcion = estado.get('fecha_recepcion')
                    if fecha_recepcion and not dte.fecha_respuesta_sii:
                        try:
                            naive = datetime.strptime(str(fecha_recepcion).strip(), '%d/%m/%Y %H:%M:%S')
                            dte.fecha_respuesta_sii = timezone.make_aware(naive, timezone.get_current_timezone())
                        except Exception:
                            pass
                    dte.save()
                    dte.corregir_falso_rechazo_espera()

            print(f"Estado consultado: {estado['estado']}")

            return estado
            
        except Exception as e:
            print(f"Error al consultar estado: {str(e)}")
            raise
    
    def _insertar_ted_y_tmstfirma(self, xml_sin_firmar, ted_xml):
        """Inserta TED y TmstFirma dentro de Documento antes de firmar el DTE."""
        import re

        xml = xml_sin_firmar if isinstance(xml_sin_firmar, str) else xml_sin_firmar.decode('ISO-8859-1')
        ted = ted_xml if isinstance(ted_xml, str) else ted_xml.decode('ISO-8859-1')
        ted = re.sub(r'^\s*<\?xml[^?]*\?>\s*', '', ted).strip()

        xml = re.sub(
            r'\s*<(?:\w+:)?Signature\b[^>]*>.*?</(?:\w+:)?Signature>\s*',
            '\n',
            xml,
            flags=re.DOTALL,
        )
        xml = re.sub(r'\s*<TED\b[^>]*>.*?</TED>\s*', '\n', xml, flags=re.DOTALL)
        xml = re.sub(r'\s*<TmstFirma>.*?</TmstFirma>\s*', '\n', xml, flags=re.DOTALL)

        tmst = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M:%S')
        bloque = f"\n{ted}\n<TmstFirma>{tmst}</TmstFirma>\n"
        xml, count = re.subn(r'\s*</Documento>', bloque + '</Documento>', xml, count=1)
        if count != 1:
            raise ValueError("No se encontro cierre Documento para insertar TED/TmstFirma")
        return xml

    def _obtener_firmador(self):
        """Obtiene una instancia del firmador con el certificado de la empresa"""
        certificado_path = self.empresa.certificado_digital.path
        password = self.empresa.password_certificado
        
        return FirmadorDTE(certificado_path, password)

    def _monto_ted_para_documento(self, documento, tipo_dte=None):
        """Obtiene el monto que debe firmarse en el TED.

        Para guias de traslado interno (`IndTraslado=5`) el SII espera que el
        monto del TED sea coherente con la guia sin valorizacion, por lo que el
        timbre debe ir con monto cero.
        """
        tipo_dte_str = str(tipo_dte or getattr(documento, 'tipo_dte', '') or '')
        if tipo_dte_str == '52':
            tipo_traslado = str(getattr(documento, 'tipo_traslado', '') or '').strip()
            if not tipo_traslado and hasattr(documento, 'tipo_despacho'):
                tipo_traslado = str(getattr(documento, 'tipo_despacho', '') or '').strip()
            if tipo_traslado in ('4', '5', '6', '8'):
                if tipo_traslado != '5':
                    return 0
                rut_emp = self._normalizar_rut(getattr(self.empresa, 'rut', ''))
                rut_rec = self._normalizar_rut(getattr(documento, 'rut_receptor', ''))
                if not rut_rec or rut_rec == rut_emp:
                    return 0
        return int(getattr(documento, 'monto_total', getattr(documento, 'total', 0)) or 0)

    def _obtener_it1_documento(self, documento):
        """Obtiene la glosa IT1 del TED desde el primer item real del documento."""
        candidatos = []

        venta_rel = getattr(documento, 'venta', None)
        if venta_rel and hasattr(venta_rel, 'ventadetalle_set'):
            candidatos = list(venta_rel.ventadetalle_set.all().order_by('id')[:1])
        elif hasattr(documento, 'ventadetalle_set'):
            candidatos = list(documento.ventadetalle_set.all().order_by('id')[:1])

        if not candidatos and hasattr(documento, 'detalles_despacho_guia'):
            try:
                candidatos = list(
                    documento.detalles_despacho_guia.filter(cantidad__gt=0).order_by('id')[:1]
                )
            except Exception:
                candidatos = []

        if not candidatos and hasattr(documento, 'detalles_despacho_factura'):
            try:
                candidatos = list(
                    documento.detalles_despacho_factura.filter(cantidad__gt=0).order_by('id')[:1]
                )
            except Exception:
                candidatos = []

        if not candidatos and hasattr(documento, 'items'):
            try:
                qs = documento.items.all()
                if hasattr(qs, 'filter'):
                    try:
                        qs = qs.filter(cantidad__gt=0)
                    except Exception:
                        pass
                candidatos = list(qs.order_by('id')[:1])
            except Exception:
                candidatos = []

        if not candidatos and hasattr(documento, 'detalles'):
            try:
                candidatos = list(documento.detalles.all().order_by('id')[:1])
            except Exception:
                candidatos = []

        if candidatos:
            item = candidatos[0]
            articulo = getattr(item, 'articulo', None)
            item_pedido = getattr(item, 'item_pedido', None)
            if articulo and getattr(articulo, 'nombre', None):
                return str(articulo.nombre)[:40]
            if item_pedido and getattr(item_pedido, 'articulo', None) and getattr(item_pedido.articulo, 'nombre', None):
                return str(item_pedido.articulo.nombre)[:40]
            for attr in ('nombre', 'descripcion', 'comentario'):
                valor = getattr(item, attr, None)
                if valor:
                    return str(valor)[:40]

        return 'Documento Tributario Electronico'
    
    def _generar_ted(self, venta, tipo_dte, folio, caf, firmador, monto_total=None):
        """Genera el TED (Timbre Electronico Digital) usando RSASK del CAF."""
        fecha_emision = venta.fecha.strftime('%Y-%m-%d')
        rut_receptor = venta.cliente.rut if venta.cliente else '66666666-6'
        razon_receptor = (
            venta.get_cliente_nombre() if hasattr(venta, 'get_cliente_nombre')
            else (venta.cliente.nombre if venta.cliente else 'Cliente Generico')
        )
        monto_ted = monto_total
        if monto_ted is None:
            monto_ted = self._monto_ted_para_documento(venta, tipo_dte=tipo_dte)
        return construir_ted(
            self.empresa.rut,
            tipo_dte,
            folio,
            fecha_emision,
            rut_receptor,
            razon_receptor,
            int(monto_ted or 0),
            self._obtener_it1_documento(venta),
            caf,
        )

    def _parsear_datos_caf(self, caf):
        """Extrae módulo y exponente del XML del CAF"""
        try:
            # Obtener contenido XML
            if caf.contenido_caf:
                content = caf.contenido_caf
            elif caf.archivo_xml:
                with open(caf.archivo_xml.path, 'r', encoding='ISO-8859-1') as f:
                    content = f.read()
            else:
                raise ValueError("CAF sin contenido XML")
            
            # Parsear
            if isinstance(content, str):
                # Si es string, lxml prefiere bytes si hay declaración de encoding
                content = content.encode('ISO-8859-1')
            
            # Usar un parser que ignore errores de encoding si es necesario o especificarlo
            parser = etree.XMLParser(encoding='ISO-8859-1', recover=True)
            root = etree.fromstring(content, parser=parser)
            
            # Buscar RSAPK
            rsapk = root.find('.//RSAPK')
            if rsapk is None:
                # Intentar con namespace
                rsapk = root.find('.//{http://www.sii.cl/SiiDte}RSAPK')
            
            if rsapk is None:
                raise ValueError("No se encontró clave RSA en el CAF")
            
            m = rsapk.find('M')
            if m is None: m = rsapk.find('{http://www.sii.cl/SiiDte}M')
            
            e = rsapk.find('E')
            if e is None: e = rsapk.find('{http://www.sii.cl/SiiDte}E')
            
            return {
                'M': m.text,
                'E': e.text
            }
        except Exception as e:
            print(f"Error parseando CAF: {e}")
            # Fallback a placeholders para no romper si el XML está mal formado, 
            # pero el TED será inválido.
            return {'M': 'ERROR_PARSING_CAF', 'E': 'ERROR_PARSING_CAF'}

    def _generar_ted_nc(self, nota, tipo_dte, folio, caf, firmador):
        """Genera el TED para una Nota de Credito usando RSASK del CAF."""
        return construir_ted(
            self.empresa.rut,
            tipo_dte,
            folio,
            nota.fecha.strftime('%Y-%m-%d'),
            nota.cliente.rut,
            nota.cliente.nombre,
            self._monto_ted_para_documento(nota, tipo_dte=tipo_dte),
            'Nota de Credito Electronica',
            caf,
        )
    
    def _crear_registro_dte(self, venta, tipo_dte, folio, caf, xml_sin_firmar, 
                           xml_firmado, ted_xml, pdf417_data, **transport_data):
        """Crea el registro del DTE en la base de datos"""
        
        # Datos del receptor
        if venta.cliente:
            rut_receptor = venta.cliente.rut
            razon_social_receptor = venta.get_cliente_nombre() if hasattr(venta, 'get_cliente_nombre') else (venta.cliente.nombre if venta.cliente else 'Cliente Genérico')
            direccion_receptor = venta.cliente.direccion or ''
            comuna_receptor = venta.cliente.comuna or ''
            giro_receptor = getattr(venta.cliente, 'giro', '') or ''
            ciudad_receptor = getattr(venta.cliente, 'ciudad', '') or ''
        else:
            rut_receptor = '66666666-6'
            razon_social_receptor = venta.get_cliente_nombre() if hasattr(venta, 'get_cliente_nombre') else 'Cliente Genérico'
            direccion_receptor = ''
            comuna_receptor = ''
            giro_receptor = ''
            ciudad_receptor = ''
        
        # Verificar si ya existe un DTE con este folio
        dte_existente = DocumentoTributarioElectronico.objects.filter(
            empresa=self.empresa,
            tipo_dte=tipo_dte,
            folio=folio
        ).first()
        
        if dte_existente:
            print(f"[WARN] ADVERTENCIA: Ya existe DTE con folio {folio}")
            print(f"   DTE existente ID: {dte_existente.id}")
            print(f"   Venta asociada: {dte_existente.venta.id if dte_existente.venta else 'N/A'}")
            try:
                from tesoreria.services import sincronizar_venta_credito_en_tesoreria
                sincronizar_venta_credito_en_tesoreria(
                    venta,
                    dte=dte_existente,
                    usuario=venta.usuario_creacion,
                    descripcion=f"Documento a crédito DTE {dte_existente.tipo_dte}-{dte_existente.folio}",
                )
            except Exception as exc:
                print(f"[WARN] No se pudo sincronizar la cuenta corriente del cliente: {exc}")
            print(f"   Reutilizando DTE existente")
            return dte_existente
        
        tipo_traslado_guia = self._resolver_tipo_traslado_guia(venta=venta) if tipo_dte == '52' else None
        if tipo_traslado_guia and getattr(venta, 'tipo_despacho', None) != tipo_traslado_guia:
            venta.tipo_despacho = tipo_traslado_guia
            venta.save(update_fields=['tipo_despacho'])

        # Crear el DTE
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=self.empresa,
            venta=venta,
            caf_utilizado=caf,
            tipo_dte=tipo_dte,
            folio=folio,
            fecha_emision=venta.fecha,  # Usar venta.fecha (ya actualizada)
            usuario_creacion=venta.usuario_creacion if venta.usuario_creacion else None,
            
            # Emisor
            rut_emisor=self.empresa.rut,
            razon_social_emisor=self.empresa.razon_social_sii or self.empresa.razon_social,
            giro_emisor=self.empresa.giro_sii or self.empresa.giro,
            direccion_emisor=self.empresa.direccion_casa_matriz or self.empresa.direccion,
            comuna_emisor=self.empresa.comuna_casa_matriz or self.empresa.comuna,
            
            # Receptor
            rut_receptor=rut_receptor,
            razon_social_receptor=razon_social_receptor,
            direccion_receptor=direccion_receptor,
            comuna_receptor=comuna_receptor,
            giro_receptor=giro_receptor,
            ciudad_receptor=ciudad_receptor,
            
            # Tipo de traslado (solo para guias tipo 52)
            tipo_traslado=tipo_traslado_guia,

            # Campos de transporte (Opcionales)
            chofer=getattr(venta, 'chofer', None),
            vehiculo=getattr(venta, 'vehiculo', None),
            patente_transporte=transport_data.get('patente_transporte') or (
                venta.vehiculo.patente if getattr(venta, 'vehiculo', None) else None
            ),
            rut_transportista=transport_data.get('rut_transportista') or self.empresa.rut,
            nombre_chofer=transport_data.get('nombre_chofer') or (
                venta.chofer.nombre if getattr(venta, 'chofer', None) else None
            ),
            
            # Montos
            monto_neto=transport_data.get('monto_neto', venta.neto),
            monto_iva=transport_data.get('monto_iva', venta.iva),
            monto_total=transport_data.get('monto_total', venta.total),
            
            # XML y Timbre
            xml_dte=xml_sin_firmar,
            xml_firmado=xml_firmado,
            timbre_electronico=ted_xml,
            datos_pdf417=pdf417_data,
            
            # Estado
            estado_sii='generado',
        )
        if tipo_dte == '52':
            self._aplicar_transporte_res154(dte, venta=venta, **transport_data)
            dte.save(update_fields=[
                'tipo_despacho_sii', 'patente_carro', 'fecha_salida',
                'hora_salida', 'fecha_llegada', 'rut_transportista',
            ])

        try:
            from tesoreria.services import sincronizar_venta_credito_en_tesoreria
            sincronizar_venta_credito_en_tesoreria(
                venta,
                dte=dte,
                usuario=venta.usuario_creacion,
                descripcion=f"Documento a crédito DTE {dte.tipo_dte}-{dte.folio}",
            )
        except Exception as exc:
            print(f"[WARN] No se pudo sincronizar la cuenta corriente del cliente: {exc}")
        
        return dte

    def _crear_registro_dte_nc(self, nota_credito, tipo_dte, folio, caf, xml_sin_firmar, 
                               xml_firmado, ted_xml, pdf417_data):
        """Crea el registro del DTE para una Nota de Crédito"""
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=self.empresa,
            caf_utilizado=caf,
            tipo_dte=tipo_dte,
            folio=folio,
            fecha_emision=nota_credito.fecha,
            usuario_creacion=nota_credito.usuario_creacion,
            
            # Emisor
            rut_emisor=self.empresa.rut,
            razon_social_emisor=self.empresa.razon_social_sii or self.empresa.razon_social,
            giro_emisor=self.empresa.giro_sii or self.empresa.giro,
            direccion_emisor=self.empresa.direccion_casa_matriz or self.empresa.direccion,
            comuna_emisor=self.empresa.comuna_casa_matriz or self.empresa.comuna,
            
            # Receptor
            rut_receptor=nota_credito.cliente.rut,
            razon_social_receptor=nota_credito.cliente.nombre,
            direccion_receptor=nota_credito.cliente.direccion or '',
            comuna_receptor=nota_credito.cliente.comuna or '',
            
            # Montos
            monto_neto=nota_credito.subtotal, # Asumiendo que subtotal es neto
            monto_iva=nota_credito.iva,
            monto_total=nota_credito.total,
            
            # XML y Timbre
            xml_dte=xml_sin_firmar,
            xml_firmado=xml_firmado,
            timbre_electronico=ted_xml,
            datos_pdf417=pdf417_data,
            
            estado_sii='generado',
        )
        return dte
    
    def _generar_ted_nd(self, nota, tipo_dte, folio, caf, firmador):
        """Genera el TED para una Nota de Debito usando RSASK del CAF."""
        return construir_ted(
            self.empresa.rut,
            tipo_dte,
            folio,
            nota.fecha.strftime('%Y-%m-%d'),
            nota.cliente.rut,
            nota.cliente.nombre,
            self._monto_ted_para_documento(nota, tipo_dte=tipo_dte),
            'Nota de Debito Electronica',
            caf,
        )
    
    def _crear_registro_dte_nd(self, nota_debito, tipo_dte, folio, caf, xml_sin_firmar, 
                               xml_firmado, ted_xml, pdf417_data):
        """Crea el registro del DTE para una Nota de Débito"""
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=self.empresa,
            caf_utilizado=caf,
            tipo_dte=tipo_dte,
            folio=folio,
            fecha_emision=nota_debito.fecha,
            usuario_creacion=nota_debito.usuario_creacion,
            
            # Emisor
            rut_emisor=self.empresa.rut,
            razon_social_emisor=self.empresa.razon_social_sii or self.empresa.razon_social,
            giro_emisor=self.empresa.giro_sii or self.empresa.giro,
            direccion_emisor=self.empresa.direccion_casa_matriz or self.empresa.direccion,
            comuna_emisor=self.empresa.comuna_casa_matriz or self.empresa.comuna,
            
            # Receptor
            rut_receptor=nota_debito.cliente.rut,
            razon_social_receptor=nota_debito.cliente.nombre,
            direccion_receptor=nota_debito.cliente.direccion or '',
            comuna_receptor=nota_debito.cliente.comuna or '',
            
            # Montos
            monto_neto=nota_debito.subtotal,
            monto_iva=nota_debito.iva,
            monto_total=nota_debito.total,
            
            # XML y Timbre
            xml_dte=xml_sin_firmar,
            xml_firmado=xml_firmado,
            timbre_electronico=ted_xml,
            datos_pdf417=pdf417_data,
            
            estado_sii='generado',
        )
        return dte

    def _generar_ted_desde_dte(self, dte, firmador):
        """Genera el TED para un DTE ya existente usando RSASK del CAF."""
        return construir_ted(
            dte.rut_emisor,
            dte.tipo_dte,
            dte.folio,
            dte.fecha_emision.strftime('%Y-%m-%d'),
            dte.rut_receptor,
            dte.razon_social_receptor,
            self._monto_ted_para_documento(dte),
            self._obtener_it1_documento(dte),
            dte.caf_utilizado,
        )
