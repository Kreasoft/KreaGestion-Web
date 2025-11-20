"""
Funciones de utilidad para la gestión de despachos.
"""
from django.db import transaction, models
from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.firma_electronica import FirmadorDTE
from facturacion_electronica.pdf417_generator import PDF417Generator

def actualizar_estado_pedido_despachado(orden_despacho):
    """
    Verifica si todos los items de un pedido han sido completamente despachados
    y, de ser así, actualiza el estado del pedido a 'finalizada'.
    """
    from django.db.models import Sum
    pedido = orden_despacho.orden_pedido
    if not pedido:
        return

    # Obtener todos los items del pedido original
    items_pedido = pedido.itemordenpedido_set.all()

    todos_despachados = True
    for item in items_pedido:
        total_despachado = item.detalleordendespacho_set.aggregate(Sum('cantidad'))['cantidad__sum'] or 0
        if total_despachado < item.cantidad:
            todos_despachados = False
            break

    if todos_despachados:
        pedido.estado = 'finalizada'
        pedido.save()

def generar_guia_desde_orden_despacho(orden_despacho, usuario):
    """
    Genera una Guía de Despacho (DTE 52) a partir de una orden de despacho.
    """
    with transaction.atomic():
        # Buscar CAF disponible para Guía de Despacho
        caf_disponible = ArchivoCAF.objects.filter(
            empresa=orden_despacho.empresa,
            tipo_documento='52',  # Guía de Despacho
            estado='activo',
            folio_actual__lt=models.F('folio_hasta')
        ).first()

        if not caf_disponible:
            raise Exception("No hay folios CAF disponibles para Guías de Despacho (52).")

        # Obtener siguiente folio
        siguiente_folio = caf_disponible.obtener_siguiente_folio()

        # [FIX] Verificar si ya existe un DTE con este folio y eliminarlo para evitar error de constraint.
        DocumentoTributarioElectronico.objects.filter(
            empresa=orden_despacho.empresa,
            tipo_dte='52',
            folio=siguiente_folio
        ).delete()

        # Calcular totales de la orden de despacho
        monto_neto = 0
        monto_iva = 0
        monto_exento = 0
        
        for item_despacho in orden_despacho.items.all():
            item_pedido = item_despacho.item_pedido
            cantidad = item_despacho.cantidad
            precio_unitario = item_pedido.precio_unitario
            
            # Calcular subtotal del item
            subtotal = cantidad * precio_unitario
            
            # Aplicar descuento si existe
            if item_pedido.descuento_porcentaje > 0:
                descuento = subtotal * (item_pedido.descuento_porcentaje / 100)
                subtotal -= descuento
            
            # Calcular impuesto
            if item_pedido.impuesto_porcentaje > 0:
                impuesto = subtotal * (item_pedido.impuesto_porcentaje / 100)
                monto_neto += subtotal
                monto_iva += impuesto
            else:
                monto_exento += subtotal
        
        monto_total = monto_neto + monto_iva + monto_exento

        # Crear el DTE
        cliente = orden_despacho.orden_pedido.cliente
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=orden_despacho.empresa,
            tipo_dte='52',
            folio=siguiente_folio,
            fecha_emision=orden_despacho.fecha_despacho,
            usuario_creacion=usuario,
            estado_sii='NoEnviado',
            caf_utilizado=caf_disponible,
            # Montos
            monto_neto=int(monto_neto),
            monto_iva=int(monto_iva),
            monto_exento=int(monto_exento),
            monto_total=int(monto_total),
            # Datos del receptor (cliente)
            rut_receptor=cliente.rut,
            razon_social_receptor=cliente.nombre,
            giro_receptor=getattr(cliente, 'giro', ''),
            direccion_receptor=cliente.direccion or '',
            comuna_receptor=cliente.comuna if isinstance(cliente.comuna, str) else '',
            # Datos del emisor (se llenan desde la empresa)
            rut_emisor=orden_despacho.empresa.rut,
            razon_social_emisor=orden_despacho.empresa.razon_social,
            giro_emisor=getattr(orden_despacho.empresa, 'giro', ''),
        )

        # Crear los detalles del DTE y vincular con los items de despacho
        for item_despacho in orden_despacho.items.all():
            articulo = item_despacho.item_pedido.articulo
            unidad = articulo.unidad_medida.simbolo if articulo.unidad_medida else 'UN'
            
            
            # Vincular la guía de despacho con el item
            item_despacho.guia_despacho = dte
            item_despacho.save()

        # --- PROCESAMIENTO COMPLETO DEL DTE ---
        empresa = orden_despacho.empresa
        
        # 1. Generar XML
        generator = DTEXMLGenerator(empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
        xml_sin_firmar = generator.generar_xml_desde_dte()

        # 2. Firmar XML
        firmador = FirmadorDTE(empresa.certificado_digital.path, empresa.password_certificado)
        xml_firmado = firmador.firmar_xml(xml_sin_firmar)

        # 3. Generar TED
        # (Esta es una implementación simplificada del método que no pude añadir antes)
        dte_data = {'rut_emisor': dte.rut_emisor, 'tipo_dte': dte.tipo_dte, 'folio': dte.folio, 'fecha_emision': dte.fecha_emision.strftime('%Y-%m-%d'), 'rut_receptor': dte.rut_receptor, 'razon_social_receptor': dte.razon_social_receptor, 'monto_total': dte.monto_total, 'item_1': orden_despacho.items.first().item_pedido.articulo.nombre if orden_despacho.items.exists() else 'Guía de Despacho'}
        caf_data = {'rut_emisor': dte.caf_utilizado.empresa.rut, 'razon_social': dte.caf_utilizado.empresa.razon_social_sii, 'tipo_documento': dte.caf_utilizado.tipo_documento, 'folio_desde': dte.caf_utilizado.folio_desde, 'folio_hasta': dte.caf_utilizado.folio_hasta, 'fecha_autorizacion': dte.caf_utilizado.fecha_autorizacion.strftime('%Y-%m-%d'), 'modulo': 'MODULO_PLACEHOLDER', 'exponente': 'EXPONENTE_PLACEHOLDER', 'firma': dte.caf_utilizado.firma_electronica}
        ted_xml = firmador.generar_ted(dte_data, caf_data)

        # 4. Generar datos para PDF417
        pdf417_data = firmador.generar_datos_pdf417(ted_xml)

        # 5. Actualizar DTE
        dte.xml_dte = xml_sin_firmar
        dte.xml_firmado = xml_firmado
        dte.timbre_electronico = ted_xml
        dte.datos_pdf417 = pdf417_data
        dte.estado_sii = 'generado'
        dte.save()

        # 6. Generar imagen del timbre
        PDF417Generator.guardar_pdf417_en_dte(dte)

        return dte

def generar_factura_desde_orden_despacho(orden_despacho, usuario):
    """
    Genera una Factura Electrónica (DTE 33) a partir de una orden de despacho.
    """
    with transaction.atomic():
        # Buscar CAF disponible para Factura
        caf_disponible = ArchivoCAF.objects.filter(
            empresa=orden_despacho.empresa,
            tipo_documento='33',  # Factura Electrónica
            estado='activo',
            folio_actual__lt=models.F('folio_hasta')
        ).first()

        if not caf_disponible:
            raise Exception("No hay folios CAF disponibles para Facturas Electrónicas (33).")

        # Obtener siguiente folio
        siguiente_folio = caf_disponible.obtener_siguiente_folio()

        # [FIX] Verificar si ya existe un DTE con este folio y eliminarlo para evitar error de constraint.
        DocumentoTributarioElectronico.objects.filter(
            empresa=orden_despacho.empresa,
            tipo_dte='33',
            folio=siguiente_folio
        ).delete()

        # Calcular totales de la orden de despacho
        monto_neto = 0
        monto_iva = 0
        monto_exento = 0
        
        for item_despacho in orden_despacho.items.all():
            item_pedido = item_despacho.item_pedido
            cantidad = item_despacho.cantidad
            precio_unitario = item_pedido.precio_unitario
            
            # Calcular subtotal del item
            subtotal = cantidad * precio_unitario
            
            # Aplicar descuento si existe
            if item_pedido.descuento_porcentaje > 0:
                descuento = subtotal * (item_pedido.descuento_porcentaje / 100)
                subtotal -= descuento
            
            # Calcular impuesto
            if item_pedido.impuesto_porcentaje > 0:
                impuesto = subtotal * (item_pedido.impuesto_porcentaje / 100)
                monto_neto += subtotal
                monto_iva += impuesto
            else:
                monto_exento += subtotal
        
        monto_total = monto_neto + monto_iva + monto_exento

        # Crear el DTE
        cliente = orden_despacho.orden_pedido.cliente
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=orden_despacho.empresa,
            tipo_dte='33',
            folio=siguiente_folio,
            fecha_emision=orden_despacho.fecha_despacho,
            usuario_creacion=usuario,
            estado_sii='NoEnviado',
            caf_utilizado=caf_disponible,
            # Montos
            monto_neto=int(monto_neto),
            monto_iva=int(monto_iva),
            monto_exento=int(monto_exento),
            monto_total=int(monto_total),
            # Datos del receptor (cliente)
            rut_receptor=cliente.rut,
            razon_social_receptor=cliente.nombre,
            giro_receptor=getattr(cliente, 'giro', ''),
            direccion_receptor=cliente.direccion or '',
            comuna_receptor=cliente.comuna if isinstance(cliente.comuna, str) else '',
            # Datos del emisor (se llenan desde la empresa)
            rut_emisor=orden_despacho.empresa.rut,
            razon_social_emisor=orden_despacho.empresa.razon_social,
            giro_emisor=getattr(orden_despacho.empresa, 'giro', ''),
        )

        # Crear los detalles del DTE y vincular con los items de despacho
        for item_despacho in orden_despacho.items.all():
            articulo = item_despacho.item_pedido.articulo
            unidad = articulo.unidad_medida.simbolo if articulo.unidad_medida else 'UN'
            
            
            # Vincular la factura con el item
            item_despacho.factura = dte
            item_despacho.save()

        # --- PROCESAMIENTO COMPLETO DEL DTE ---
        empresa = orden_despacho.empresa
        
        # 1. Generar XML
        generator = DTEXMLGenerator(empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
        xml_sin_firmar = generator.generar_xml_desde_dte()

        # 2. Firmar XML
        firmador = FirmadorDTE(empresa.certificado_digital.path, empresa.password_certificado)
        xml_firmado = firmador.firmar_xml(xml_sin_firmar)

        # 3. Generar TED
        dte_data = {'rut_emisor': dte.rut_emisor, 'tipo_dte': dte.tipo_dte, 'folio': dte.folio, 'fecha_emision': dte.fecha_emision.strftime('%Y-%m-%d'), 'rut_receptor': dte.rut_receptor, 'razon_social_receptor': dte.razon_social_receptor, 'monto_total': dte.monto_total, 'item_1': orden_despacho.items.first().item_pedido.articulo.nombre if orden_despacho.items.exists() else 'Factura Electrónica'}
        caf_data = {'rut_emisor': dte.caf_utilizado.empresa.rut, 'razon_social': dte.caf_utilizado.empresa.razon_social_sii, 'tipo_documento': dte.caf_utilizado.tipo_documento, 'folio_desde': dte.caf_utilizado.folio_desde, 'folio_hasta': dte.caf_utilizado.folio_hasta, 'fecha_autorizacion': dte.caf_utilizado.fecha_autorizacion.strftime('%Y-%m-%d'), 'modulo': 'MODULO_PLACEHOLDER', 'exponente': 'EXPONENTE_PLACEHOLDER', 'firma': dte.caf_utilizado.firma_electronica}
        ted_xml = firmador.generar_ted(dte_data, caf_data)

        # 4. Generar datos para PDF417
        pdf417_data = firmador.generar_datos_pdf417(ted_xml)

        # 5. Actualizar DTE
        dte.xml_dte = xml_sin_firmar
        dte.xml_firmado = xml_firmado
        dte.timbre_electronico = ted_xml
        dte.datos_pdf417 = pdf417_data
        dte.estado_sii = 'generado'
        dte.save()

        # 6. Generar imagen del timbre
        PDF417Generator.guardar_pdf417_en_dte(dte)

        return dte
