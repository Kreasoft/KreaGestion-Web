"""
Servicio integrador para generación, firma y envío de DTE
"""
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from .models import DocumentoTributarioElectronico, ArchivoCAF, EnvioDTE
from .dte_generator import DTEXMLGenerator  # Usar para boletas
from dte_gdexpress import GeneradorFactura, GeneradorGuia, GeneradorNotaCredito, GeneradorNotaDebito, ClienteGDExpress, GestorCAF
from .firma_electronica import FirmadorDTE
# from .cliente_sii import ClienteSII  # Reemplazado por ClienteGDExpress
from .services import FolioService
from .pdf417_generator import PDF417Generator
import os
from lxml import etree


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
    
    def generar_dte_desde_venta(self, venta, tipo_dte='39'):
        """
        Genera un DTE completo desde una venta
        
        Args:
            venta: Instancia de Venta
            tipo_dte: Código del tipo de DTE (33, 39, etc.)
            
        Returns:
            DocumentoTributarioElectronico: DTE generado y firmado
        """
        try:
            with transaction.atomic():
                # 1. Obtener folio
                print(f"\nPaso 1: Obteniendo folio para tipo {tipo_dte}")
                folio, caf = FolioService.obtener_siguiente_folio(self.empresa, tipo_dte)

                if folio is None:
                    raise ValueError(f"No hay folios disponibles para tipo de documento {tipo_dte}")

                print(f"Folio asignado: {folio}")

                # 2. Generar XML del DTE
                print(f"\nPaso 2: Generando XML del DTE")
                
                # Para boletas (39) y guías (52), usar DTEXMLGenerator con formato compatible DTEBox
                if tipo_dte in ['39', '52']:
                    print(f"[DTE] Usando DTEXMLGenerator para tipo {tipo_dte}")
                    
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
                        razon_social_receptor=venta.cliente.nombre if venta.cliente else 'Cliente Genérico',
                        direccion_receptor=venta.cliente.direccion if venta.cliente else '',
                        comuna_receptor=venta.cliente.comuna if venta.cliente else '',
                        # Para guías (52), NO derivar tipo_traslado desde tipo_despacho.
                        # Se determinará en el generador; por defecto '1' (Venta) si no está definido explícitamente.
                        tipo_traslado=None if tipo_dte == '52' else None,
                        monto_neto=int(venta.neto),
                        monto_iva=int(venta.iva),
                        monto_total=int(venta.total),
                    )
                    dte_temp.venta = venta  # Asociar venta
                    
                    # Generar XML con DTEXMLGenerator (usamos generar_xml para obtener XML limpio sin TED)
                    generator = DTEXMLGenerator(self.empresa, dte_temp, tipo_dte, folio, caf)
                    xml_sin_firmar = generator.generar_xml()
                    
                else:
                    # Para otros tipos, usar dte_gdexpress
                    print(f"[DTE] Usando dte_gdexpress para tipo {tipo_dte}")
                    
                    # Preparar items para el generador
                    items_dte = []
                    for item in venta.ventadetalle_set.all():
                        items_dte.append({
                            'nombre': item.articulo.nombre if item.articulo else item.descripcion,
                            'cantidad': float(item.cantidad),
                            'precio': float(item.precio_unitario),
                            'exento': False,
                            'unidad': item.articulo.unidad_medida.simbolo if (item.articulo and item.articulo.unidad_medida) else '',
                        })
                    
                    # Seleccionar generador según tipo
                    if tipo_dte == '33':
                        GeneratorClass = GeneradorFactura
                    elif tipo_dte == '52':
                        # Este caso ahora se maneja arriba con DTEXMLGenerator, 
                        # pero dejamos el placeholder por si acaso
                        GeneratorClass = GeneradorGuia
                    else:
                        raise ValueError(f"Tipo DTE {tipo_dte} no soportado")
                    
                    # Instanciar generador
                    rut_receptor = venta.cliente.rut if venta.cliente else '66666666-6'
                    razon_receptor = venta.cliente.nombre if venta.cliente else 'Cliente Genérico'
                    direccion_receptor = venta.cliente.direccion if venta.cliente else 'Sin Dirección'
                    comuna_receptor = venta.cliente.comuna if venta.cliente else 'Santiago'
                    
                    generator = GeneratorClass(
                        folio=folio,
                        fecha=venta.fecha.strftime('%Y-%m-%d'),
                        rut_emisor=self.empresa.rut,
                        razon_social_emisor=self.empresa.razon_social_sii or self.empresa.razon_social,
                        giro_emisor=self.empresa.giro_sii or self.empresa.giro,
                        direccion_emisor=self.empresa.direccion_casa_matriz or self.empresa.direccion,
                        comuna_emisor=self.empresa.comuna_casa_matriz or self.empresa.comuna,
                        rut_receptor=rut_receptor,
                        razon_social_receptor=razon_receptor,
                        direccion_receptor=direccion_receptor,
                        comuna_receptor=comuna_receptor,
                        items=items_dte,
                        forma_pago='1' if not hasattr(venta, 'forma_pago') else ('2' if getattr(venta.forma_pago, 'es_credito', False) else '1')
                    )
                    
                    xml_sin_firmar = generator.generar_xml()

                print(f"XML generado ({len(xml_sin_firmar)} bytes)")

                # 3. Firmar el XML
                print(f"\nPaso 3: Firmando XML")
                firmador = self._obtener_firmador()
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                print(f"XML firmado")

                # 4. Generar TED (Timbre Electrónico)
                print(f"\nPaso 4: Generando TED")
                ted_xml = self._generar_ted(venta, tipo_dte, folio, caf, firmador)

                print(f"TED generado")

                # 5. Generar datos para PDF417
                print(f"\nPaso 5: Generando datos PDF417")
                pdf417_data = firmador.generar_datos_pdf417(ted_xml)
                
                # 6. Crear registro del DTE (ahora SIEMPRE guardamos, incluso en modo reutilización)
                print(f"\nPaso 6: Guardando DTE en base de datos")
                dte = self._crear_registro_dte(
                    venta=venta,
                    tipo_dte=tipo_dte,
                    folio=folio,
                    caf=caf,
                    xml_sin_firmar=xml_sin_firmar,
                    xml_firmado=xml_firmado,
                    ted_xml=ted_xml,
                    pdf417_data=pdf417_data
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
                if not venta:
                    raise NotImplementedError("Solo se soporta regenerar DTE desde Venta")
                
                # Para boletas (39) y guías (52), usar DTEXMLGenerator
                if dte.tipo_dte in ['39', '52']:
                    print(f"[DTE] Regenerando documento {dte.tipo_dte} folio {dte.folio} con DTEXMLGenerator")
                    
                    # El DTE ya existe, usarlo directamente
                    generator = DTEXMLGenerator(self.empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
                    xml_sin_firmar = generator.generar_xml()
                    
                else:
                    # Para otros tipos, usar dte_gdexpress
                    print(f"[DTE] Regenerando DTE tipo {dte.tipo_dte} con dte_gdexpress")
                    
                    items_dte = []
                    for item in venta.ventadetalle_set.all():
                        items_dte.append({
                            'nombre': item.articulo.nombre if item.articulo else item.descripcion,
                            'cantidad': float(item.cantidad),
                            'precio': float(item.precio_unitario),
                            'exento': False,
                            'unidad': item.articulo.unidad_medida.simbolo if (item.articulo and item.articulo.unidad_medida) else '',
                        })
                    
                    if dte.tipo_dte == '33':
                        GeneratorClass = GeneradorFactura
                    else:
                        raise ValueError(f"Tipo DTE {dte.tipo_dte} no soportado en regeneración")

                    generator = GeneratorClass(
                        folio=dte.folio,
                        fecha=dte.fecha_emision.strftime('%Y-%m-%d'),
                        rut_emisor=dte.rut_emisor,
                        razon_social_emisor=dte.razon_social_emisor,
                        giro_emisor=dte.giro_emisor,
                        direccion_emisor=dte.direccion_emisor,
                        comuna_emisor=dte.comuna_emisor,
                        rut_receptor=dte.rut_receptor,
                        razon_social_receptor=dte.razon_social_receptor,
                        direccion_receptor=dte.direccion_receptor,
                        comuna_receptor=dte.comuna_receptor,
                        items=items_dte,
                        forma_pago='1'
                    )
                    
                    xml_sin_firmar = generator.generar_xml()

                # 2. Firmar el XML
                firmador = self._obtener_firmador()
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                # 3. Generar TED
                ted_xml = self._generar_ted_desde_dte(dte, firmador)

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

                # 4. Generar XML (dte_gdexpress)
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
                # Intentar extraer referencia de la nota de crédito
                if hasattr(nota_credito, 'factura') and nota_credito.factura:
                     referencias.append({
                         'tipo_documento': '33', # Asumimos factura
                         'folio': nota_credito.factura.numero, # O folio
                         'fecha': nota_credito.factura.fecha.strftime('%Y-%m-%d'),
                         'codigo_referencia': '1', # Anula documento
                         'razon': 'Anula factura',
                     })

                generator = GeneradorNotaCredito(
                    folio=folio,
                    fecha=nota_credito.fecha.strftime('%Y-%m-%d'),
                    rut_emisor=self.empresa.rut,
                    razon_social_emisor=self.empresa.razon_social_sii or self.empresa.razon_social,
                    giro_emisor=self.empresa.giro_sii or self.empresa.giro,
                    direccion_emisor=self.empresa.direccion_casa_matriz or self.empresa.direccion,
                    comuna_emisor=self.empresa.comuna_casa_matriz or self.empresa.comuna,
                    rut_receptor=nota_credito.cliente.rut,
                    razon_social_receptor=nota_credito.cliente.nombre,
                    direccion_receptor=nota_credito.cliente.direccion or '',
                    comuna_receptor=nota_credito.cliente.comuna or '',
                    items=items_dte,
                    referencias=referencias,
                    forma_pago='1'
                )
                xml_sin_firmar = generator.generar_xml()

                # 5. Firmar el XML
                firmador = self._obtener_firmador()
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                # 6. Generar TED
                ted_xml = self._generar_ted_nc(nota_credito, TIPO_DTE_NC, folio, caf, firmador)

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

                # 4. Generar XML (dte_gdexpress)
                items_dte = []
                for item in items:
                    items_dte.append({
                        'nombre': item.descripcion,
                        'cantidad': float(item.cantidad),
                        'precio': float(item.precio_unitario),
                        'exento': False,
                        'unidad': getattr(item.articulo, 'unidad_medida', '') if item.articulo else '',
                    })
                
                referencias = [] # TODO: Extraer referencias si aplica

                generator = GeneradorNotaDebito(
                    folio=folio,
                    fecha=nota_debito.fecha.strftime('%Y-%m-%d'),
                    rut_emisor=self.empresa.rut,
                    razon_social_emisor=self.empresa.razon_social_sii or self.empresa.razon_social,
                    giro_emisor=self.empresa.giro_sii or self.empresa.giro,
                    direccion_emisor=self.empresa.direccion_casa_matriz or self.empresa.direccion,
                    comuna_emisor=self.empresa.comuna_casa_matriz or self.empresa.comuna,
                    rut_receptor=nota_debito.cliente.rut,
                    razon_social_receptor=nota_debito.cliente.nombre,
                    direccion_receptor=nota_debito.cliente.direccion or '',
                    comuna_receptor=nota_debito.cliente.comuna or '',
                    items=items_dte,
                    referencias=referencias,
                    forma_pago='1'
                )
                xml_sin_firmar = generator.generar_xml()

                # 5. Firmar el XML
                firmador = self._obtener_firmador()
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                # 6. Generar TED
                ted_xml = self._generar_ted_nd(nota_debito, TIPO_DTE_ND, folio, caf, firmador)

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
        Envía un DTE al SII usando DTEBox
        """
        try:
            print(f"\n[DTE] Enviando DTE a DTEBox - Tipo {dte.tipo_dte}, Folio {dte.folio}")

            if not getattr(self.empresa, 'dtebox_habilitado', False):
                 raise ValueError(f"La empresa {self.empresa.nombre} no tiene habilitado DTEBox.")
            
            # Validación previa para guías: asegurar GiroRecep y XML actualizado
            if dte.tipo_dte == '52':
                giro_recep = getattr(dte, 'giro_receptor', '') or ''
                if not giro_recep:
                    try:
                        # Intentar completar giro desde la venta/cliente y regenerar XML completo
                        if dte.venta and dte.venta.cliente and getattr(dte.venta.cliente, 'giro', None):
                            dte.giro_receptor = dte.venta.cliente.giro
                        else:
                            dte.giro_receptor = 'SIN GIRO'
                        dte.save(update_fields=['giro_receptor'])
                        self.procesar_dte_existente(dte)
                        dte.refresh_from_db()
                        print(f"[PRE-ENVÍO] GiroRecep asegurado para guía {dte.folio}: {dte.giro_receptor}")
                    except Exception as _:
                        pass
            
            from .dtebox_service import DTEBoxService
            dtebox = DTEBoxService(self.empresa)
            
            # En algunos boxes, se espera XML firmado. Probar con xml_firmado prioritario.
            xml_para_enviar = (dte.xml_firmado or '').strip() or (dte.xml_dte or '').strip()
            resultado = dtebox.timbrar_dte(xml_para_enviar, dte.tipo_dte)

            if resultado['success']:
                # El track_id en DTEBox viene dentro del XML de respuesta o es el ID del proceso
                # Intentar extraer track_id del XML de respuesta
                track_id = 'DTEBOX-' + str(dte.folio)
                try:
                    import xml.etree.ElementTree as ET
                    resp_xml = resultado.get('xml_respuesta', '')
                    if resp_xml:
                        root = ET.fromstring(resp_xml)
                        track_node = root.find('.//TrackId')
                        if track_node is not None and track_node.text:
                            track_id = track_node.text
                except:
                    pass

                print(f"DTE enviado exitosamente via DTEBox API - Track ID: {track_id}")
                
                with transaction.atomic():
                    dte.estado_sii = 'enviado'
                    dte.track_id = track_id
                    dte.fecha_envio_sii = timezone.now()
                    dte.respuesta_sii = resultado.get('xml_respuesta', '')
                    # Actualizar el timbre si DTEBox devolvió uno nuevo/mejorado
                    if resultado.get('ted'):
                        dte.timbre_electronico = resultado.get('ted')
                        # Regenerar PDF417
                        from .firma_electronica import FirmadorDTE
                        firmador = self._obtener_firmador()
                        dte.datos_pdf417 = firmador.generar_datos_pdf417(dte.timbre_electronico)
                        from .pdf417_generator import PDF417Generator
                        PDF417Generator.guardar_pdf417_en_dte(dte)
                    
                    dte.save()
                
                return {
                    'success': True,
                    'track_id': track_id,
                    'xml_respuesta': resultado.get('xml_respuesta')
                }
            else:
                error_msg = resultado.get('error', 'Error desconocido en DTEBox API')
                # Fallback 1: Intentar envío con ClienteGDExpress (mismo comportamiento que KreaDTE-Cloud)
                try:
                    from dte_gdexpress import ClienteGDExpress
                    cliente = ClienteGDExpress(
                        api_key=self.empresa.dtebox_auth_key,
                        ambiente='CERTIFICACION' if (self.empresa.dtebox_ambiente or 'T') == 'T' else 'PRODUCCION',
                        url_servicio=self.empresa.dtebox_url
                    )
                    resultado2 = cliente.enviar_dte(
                        xml_firmado=xml_para_enviar,
                        resolucion_numero=self.empresa.resolucion_numero or 0,
                        resolucion_fecha=(self.empresa.resolucion_fecha.strftime('%Y-%m-%d') if self.empresa.resolucion_fecha else '2014-08-22')
                    )
                    if resultado2.get('success'):
                        track_id = resultado2.get('track_id', 'DTEBOX-' + str(dte.folio))
                        with transaction.atomic():
                            dte.estado_sii = 'enviado'
                            dte.track_id = track_id
                            dte.fecha_envio_sii = timezone.now()
                            dte.respuesta_sii = resultado2.get('xml_respuesta', '')
                            if resultado2.get('ted'):
                                dte.timbre_electronico = resultado2.get('ted')
                                from .firma_electronica import FirmadorDTE
                                firmador = self._obtener_firmador()
                                dte.datos_pdf417 = firmador.generar_datos_pdf417(dte.timbre_electronico)
                                from .pdf417_generator import PDF417Generator
                                PDF417Generator.guardar_pdf417_en_dte(dte)
                            dte.save()
                        return {
                            'success': True,
                            'track_id': track_id,
                            'xml_respuesta': resultado2.get('xml_respuesta')
                        }
                except Exception:
                    pass
                
                # Fallback 2: Envío directo al SII con SetDTE (certificación)
                try:
                    from .cliente_sii import ClienteSII
                    cliente_sii = ClienteSII(ambiente=self.empresa.ambiente_sii or 'certificacion')
                    firmador = self._obtener_firmador()
                    
                    # Obtener semilla y token
                    semilla = cliente_sii.obtener_semilla()
                    token = cliente_sii.obtener_token(semilla, firmador)
                    
                    # Construir carátula y SetDTE con un solo documento
                    caratula = {
                        'rut_emisor': self.empresa.rut,
                        'rut_envia': self.empresa.rut,
                        'rut_receptor': '60803000-K',
                        'fecha_resolucion': (self.empresa.resolucion_fecha.strftime('%Y-%m-%d') if self.empresa.resolucion_fecha else '2014-08-22'),
                        'numero_resolucion': int(self.empresa.resolucion_numero or 0),
                    }
                    set_xml = cliente_sii.crear_set_dte([xml_para_enviar], caratula)
                    
                    # Enviar al SII
                    respuesta_sii = cliente_sii.enviar_dte(
                        xml_envio=set_xml,
                        token=token,
                        rut_emisor=self.empresa.rut,
                        rut_envia=self.empresa.rut
                    )
                    
                    track_id = respuesta_sii.get('track_id')
                    if track_id:
                        with transaction.atomic():
                            dte.estado_sii = 'enviado'
                            dte.track_id = track_id
                            dte.fecha_envio_sii = timezone.now()
                            dte.respuesta_sii = respuesta_sii.get('respuesta_completa', '')
                            dte.save()
                        return {'success': True, 'track_id': track_id}
                except Exception as e_sii:
                    pass
                
                raise Exception(f"Error DTEBox: {error_msg}")
            
        except Exception as e:
            print(f"Error al enviar DTE a GDExpress: {str(e)}")

            # Actualizar estado del DTE (solo si NO está en modo prueba)
            modo_reutilizacion = getattr(self.empresa, 'modo_reutilizacion_folios', False)
            es_certificacion = self.empresa.ambiente_sii == 'certificacion'

            if not (modo_reutilizacion and es_certificacion):
                with transaction.atomic():
                    dte.estado_sii = 'error_envio'
                    dte.error_envio = str(e)
                    dte.save()
            
            raise
    
    def consultar_estado_dte(self, dte):
        """
        Consulta el estado de un DTE en el SII
        
        Args:
            dte: Instancia de DocumentoTributarioElectronico
            
        Returns:
            dict: Estado del DTE
        """
        try:
            if not dte.track_id:
                raise ValueError("El DTE no tiene Track ID. Debe ser enviado primero.")

            print(f"\nConsultando estado del DTE - Track ID: {dte.track_id}")

            # Inicializar cliente SII
            cliente_sii = ClienteSII(ambiente=self.empresa.ambiente_sii)

            # Obtener firmador y token
            firmador = self._obtener_firmador()
            semilla = cliente_sii.obtener_semilla()
            token = cliente_sii.obtener_token(semilla, firmador)

            # Consultar estado
            estado = cliente_sii.consultar_estado_dte(
                track_id=dte.track_id,
                token=token,
                rut_emisor=self.empresa.rut
            )

            # Actualizar estado del DTE (solo si NO está en modo prueba)
            modo_reutilizacion = self.empresa.modo_reutilizacion_folios
            es_certificacion = self.empresa.ambiente_sii == 'certificacion'

            if not (modo_reutilizacion and es_certificacion):
                with transaction.atomic():
                    if estado['estado'] == 'ACEPTADO':
                        dte.estado_sii = 'aceptado'
                    elif estado['estado'] == 'RECHAZADO':
                        dte.estado_sii = 'rechazado'

                    dte.glosa_sii = estado.get('glosa')
                    dte.fecha_consulta_estado = timezone.now()
                    dte.save()

            print(f"Estado consultado: {estado['estado']}")

            return estado
            
        except Exception as e:
            print(f"Error al consultar estado: {str(e)}")
            raise
    
    def _obtener_firmador(self):
        """Obtiene una instancia del firmador con el certificado de la empresa"""
        certificado_path = self.empresa.certificado_digital.path
        password = self.empresa.password_certificado
        
        return FirmadorDTE(certificado_path, password)
    
    def _generar_ted(self, venta, tipo_dte, folio, caf, firmador):
        """Genera el TED (Timbre Electrónico Digital)"""
        # Preparar datos del DTE
        dte_data = {
            'rut_emisor': self.empresa.rut,
            'tipo_dte': tipo_dte,
            'folio': folio,
            'fecha_emision': venta.fecha.strftime('%Y-%m-%d'),
            'rut_receptor': venta.cliente.rut if venta.cliente else '66666666-6',
            'razon_social_receptor': (venta.cliente.nombre if venta.cliente 
                                     else 'Cliente Genérico'),
            'monto_total': venta.total,
            'item_1': 'Documento Tributario Electrónico',
        }
        
        # Preparar datos del CAF
        datos_caf = self._parsear_datos_caf(caf)
        
        caf_data = {
            'rut_emisor': self.empresa.rut,
            'razon_social': self.empresa.razon_social_sii or self.empresa.razon_social,
            'tipo_documento': tipo_dte,
            'folio_desde': caf.folio_desde,
            'folio_hasta': caf.folio_hasta,
            'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
            'modulo': datos_caf['M'],
            'exponente': datos_caf['E'],
            'firma': caf.firma_electronica,
        }
        
        return firmador.generar_ted(dte_data, caf_data)

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
        """Genera el TED para una Nota de Crédito"""
        dte_data = {
            'rut_emisor': self.empresa.rut,
            'tipo_dte': tipo_dte,
            'folio': folio,
            'fecha_emision': nota.fecha.strftime('%Y-%m-%d'),
            'rut_receptor': nota.cliente.rut,
            'razon_social_receptor': nota.cliente.nombre,
            'monto_total': nota.total,
            'item_1': 'Nota de Crédito Electrónica',
        }
        
        # Preparar datos del CAF
        datos_caf = self._parsear_datos_caf(caf)

        caf_data = {
            'rut_emisor': self.empresa.rut,
            'razon_social': self.empresa.razon_social_sii or self.empresa.razon_social,
            'tipo_documento': tipo_dte,
            'folio_desde': caf.folio_desde,
            'folio_hasta': caf.folio_hasta,
            'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
            'modulo': datos_caf['M'],
            'exponente': datos_caf['E'],
            'firma': caf.firma_electronica,
        }
        
        return firmador.generar_ted(dte_data, caf_data)
    
    def _crear_registro_dte(self, venta, tipo_dte, folio, caf, xml_sin_firmar, 
                           xml_firmado, ted_xml, pdf417_data):
        """Crea el registro del DTE en la base de datos"""
        
        # Datos del receptor
        if venta.cliente:
            rut_receptor = venta.cliente.rut
            razon_social_receptor = venta.cliente.nombre
            direccion_receptor = venta.cliente.direccion or ''
            comuna_receptor = venta.cliente.comuna or ''
            giro_receptor = getattr(venta.cliente, 'giro', '') or ''
            ciudad_receptor = getattr(venta.cliente, 'ciudad', '') or ''
        else:
            rut_receptor = '66666666-6'
            razon_social_receptor = 'Cliente Genérico'
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
            print(f"   Reutilizando DTE existente")
            return dte_existente
        
        # Crear el DTE
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=self.empresa,
            venta=venta,
            caf_utilizado=caf,
            tipo_dte=tipo_dte,
            folio=folio,
            fecha_emision=venta.fecha,
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
            
            # Tipo de traslado (solo para guías tipo 52)
            # DEBUG
            # print(f"DEBUG: [DTE SERVICE] Creando DTE Tipo {tipo_dte}. Venta Tipo Despacho: {venta.tipo_despacho}")
            tipo_traslado=venta.tipo_despacho if tipo_dte == '52' else None,
            
            # Montos
            monto_neto=venta.subtotal,
            monto_iva=venta.iva,
            monto_total=venta.total,
            
            # XML y Timbre
            xml_dte=xml_sin_firmar,
            xml_firmado=xml_firmado,
            timbre_electronico=ted_xml,
            datos_pdf417=pdf417_data,
            
            # Estado
            estado_sii='generado',
        )
        
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
        """Genera el TED para una Nota de Débito"""
        dte_data = {
            'rut_emisor': self.empresa.rut,
            'tipo_dte': tipo_dte,
            'folio': folio,
            'fecha_emision': nota.fecha.strftime('%Y-%m-%d'),
            'rut_receptor': nota.cliente.rut,
            'razon_social_receptor': nota.cliente.nombre,
            'monto_total': nota.total,
            'item_1': 'Nota de Débito Electrónica',
        }
        
        # Preparar datos del CAF
        datos_caf = self._parsear_datos_caf(caf)

        caf_data = {
            'rut_emisor': self.empresa.rut,
            'razon_social': self.empresa.razon_social_sii or self.empresa.razon_social,
            'tipo_documento': tipo_dte,
            'folio_desde': caf.folio_desde,
            'folio_hasta': caf.folio_hasta,
            'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
            'modulo': datos_caf['M'],
            'exponente': datos_caf['E'],
            'firma': caf.firma_electronica,
        }
        
        return firmador.generar_ted(dte_data, caf_data)
    
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
        """Genera el TED para un DTE ya existente"""
        # Preparar datos del DTE
        dte_data = {
            'rut_emisor': dte.rut_emisor,
            'tipo_dte': dte.tipo_dte,
            'folio': dte.folio,
            'fecha_emision': dte.fecha_emision.strftime('%Y-%m-%d'),
            'rut_receptor': dte.rut_receptor,
            'razon_social_receptor': dte.razon_social_receptor,
            'monto_total': int(dte.monto_total),
            'item_1': 'Documento Tributario Electrónico',
        }
        
        # Preparar datos del CAF
        datos_caf = self._parsear_datos_caf(dte.caf_utilizado)
        
        caf_data = {
            'rut_emisor': dte.caf_utilizado.empresa.rut,
            'razon_social': dte.caf_utilizado.empresa.razon_social_sii or dte.caf_utilizado.empresa.razon_social,
            'tipo_documento': dte.caf_utilizado.tipo_documento,
            'folio_desde': dte.caf_utilizado.folio_desde,
            'folio_hasta': dte.caf_utilizado.folio_hasta,
            'fecha_autorizacion': dte.caf_utilizado.fecha_autorizacion.strftime('%Y-%m-%d'),
            'modulo': datos_caf['M'],
            'exponente': datos_caf['E'],
            'firma': dte.caf_utilizado.firma_electronica,
        }
        
        return firmador.generar_ted(dte_data, caf_data)
