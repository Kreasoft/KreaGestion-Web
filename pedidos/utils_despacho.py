"""
Funciones de utilidad para la gestión de despachos.
"""
from django.db import transaction, models
from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.firma_electronica import FirmadorDTE
from facturacion_electronica.pdf417_generator import PDF417Generator
from facturacion_electronica.ted_sii import construir_ted
from facturacion_electronica.dte_service import DTEService


def _finalizar_xml_dte_despacho(dte, xml_sin_firmar, item_glosa='Documento Tributario'):
    """Alinea montos del XML, inserta TED con el mismo total y firma."""
    empresa = dte.empresa
    totales = DTEXMLGenerator.extraer_totales_xml(xml_sin_firmar)
    if totales.get('total') or totales.get('neto'):
        dte.monto_neto = totales['neto']
        dte.monto_iva = totales['iva']
        dte.monto_exento = totales.get('exento') or 0
        dte.monto_total = totales['total']

    service = DTEService(empresa)
    ted_xml = construir_ted(
        dte.rut_emisor,
        dte.tipo_dte,
        dte.folio,
        dte.fecha_emision.strftime('%Y-%m-%d'),
        dte.rut_receptor,
        dte.razon_social_receptor,
        int(dte.monto_total or 0),
        (item_glosa or 'Documento Tributario')[:40],
        dte.caf_utilizado,
    )
    xml_con_ted = service._insertar_ted_y_tmstfirma(xml_sin_firmar, ted_xml)
    firmador = FirmadorDTE(empresa.certificado_digital.path, empresa.password_certificado)
    xml_firmado = firmador.firmar_xml(xml_con_ted)
    pdf417_data = firmador.generar_datos_pdf417(ted_xml)

    dte.xml_dte = xml_sin_firmar
    dte.xml_firmado = xml_firmado
    dte.timbre_electronico = ted_xml
    dte.datos_pdf417 = pdf417_data
    dte.estado_sii = 'generado'
    dte.save()
    PDF417Generator.guardar_pdf417_en_dte(dte)
    return dte


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
        # Obtener sucursal (casa matriz por defecto)
        from empresas.models import Sucursal
        from facturacion_electronica.services import FolioService
        
        sucursal = Sucursal.objects.filter(empresa=orden_despacho.empresa, es_principal=True).first()
        if not sucursal:
            sucursal = Sucursal.objects.filter(empresa=orden_despacho.empresa).first()
        
        if not sucursal:
            raise Exception("No se encontró sucursal para la empresa.")
        
        # USAR FolioService CENTRALIZADO para asignación de folios
        # NOTA: obtener_siguiente_folio retorna (folio, caf) - 2 valores
        siguiente_folio, caf_disponible = FolioService.obtener_siguiente_folio(
            empresa=orden_despacho.empresa,
            tipo_documento='52',  # Guía de Despacho
            sucursal=sucursal
        )

        if not caf_disponible or not siguiente_folio:
            raise Exception(f"No hay CAF activo disponible para Guías de Despacho (52) en sucursal {sucursal.nombre}.")

        # Calcular totales de la orden de despacho
        monto_neto = 0
        monto_iva = 0
        monto_exento = 0
        
        items_emitibles = orden_despacho.items.filter(cantidad__gt=0)
        if not items_emitibles.exists():
            raise ValueError("No hay productos con cantidad mayor a 0 para emitir la guía.")

        for item_despacho in items_emitibles:
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
        service = DTEService(orden_despacho.empresa)
        tipo_traslado = service._resolver_tipo_traslado_guia(orden_despacho=orden_despacho)
        chofer = getattr(orden_despacho, 'chofer', None)
        vehiculo = getattr(orden_despacho, 'vehiculo', None)
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=orden_despacho.empresa,
            tipo_dte='52',
            folio=siguiente_folio,
            fecha_emision=orden_despacho.fecha_despacho,
            usuario_creacion=usuario,
            estado_sii='NoEnviado',
            caf_utilizado=caf_disponible,
            tipo_traslado=tipo_traslado,
            chofer=chofer,
            vehiculo=vehiculo,
            nombre_chofer=(chofer.nombre if chofer else '') or '',
            patente_transporte=(vehiculo.patente if vehiculo else '') or '',
            # Montos
            monto_neto=int(monto_neto),
            monto_iva=int(monto_iva),
            monto_exento=int(monto_exento),
            monto_total=int(monto_total),
            # Datos del receptor (cliente)
            rut_receptor=cliente.rut,
            razon_social_receptor=cliente.nombre,
            giro_receptor=getattr(cliente, 'giro', ''),
            direccion_receptor=(orden_despacho.direccion_entrega or cliente.direccion or '')[:200],
            comuna_receptor=(orden_despacho.comuna_entrega or (cliente.comuna if isinstance(cliente.comuna, str) else '') or '')[:100],
            ciudad_receptor=(orden_despacho.ciudad_entrega or getattr(cliente, 'ciudad', '') or '')[:100],
            # Datos del emisor (se llenan desde la empresa)
            rut_emisor=orden_despacho.empresa.rut,
            razon_social_emisor=orden_despacho.empresa.razon_social,
            giro_emisor=getattr(orden_despacho.empresa, 'giro', ''),
        )

        for item_despacho in items_emitibles:
            item_despacho.guia_despacho = dte
            item_despacho.save(update_fields=['guia_despacho'])

        # --- PROCESAMIENTO COMPLETO DEL DTE ---
        empresa = orden_despacho.empresa
        
        # Generar XML desde el DTE para usar solo las líneas de esta guía
        generator = DTEXMLGenerator(empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
        xml_sin_firmar = generator.generar_xml()
        primer_item = items_emitibles.select_related('item_pedido__articulo').first()
        item_glosa = primer_item.item_pedido.articulo.nombre if primer_item and primer_item.item_pedido else 'Guía de Despacho'
        return _finalizar_xml_dte_despacho(dte, xml_sin_firmar, item_glosa)

def generar_factura_desde_orden_despacho(orden_despacho, usuario):
    """
    Genera una Factura Electrónica (DTE 33) a partir de una orden de despacho.
    """
    with transaction.atomic():
        # Obtener sucursal (casa matriz por defecto)
        from empresas.models import Sucursal
        from facturacion_electronica.services import FolioService
        
        sucursal = Sucursal.objects.filter(empresa=orden_despacho.empresa, es_principal=True).first()
        if not sucursal:
            sucursal = Sucursal.objects.filter(empresa=orden_despacho.empresa).first()
        
        if not sucursal:
            raise Exception("No se encontró sucursal para la empresa.")
        
        # USAR FolioService CENTRALIZADO para asignación de folios
        # NOTA: obtener_siguiente_folio retorna (folio, caf) - 2 valores
        siguiente_folio, caf_disponible = FolioService.obtener_siguiente_folio(
            empresa=orden_despacho.empresa,
            tipo_documento='33',  # Factura Electrónica
            sucursal=sucursal
        )

        if not caf_disponible or not siguiente_folio:
            raise Exception(f"No hay CAF activo disponible para Facturas Electrónicas (33) en sucursal {sucursal.nombre}.")

        # Calcular totales de la orden de despacho
        monto_neto = 0
        monto_iva = 0
        monto_exento = 0
        
        items_emitibles = orden_despacho.items.filter(cantidad__gt=0)
        if not items_emitibles.exists():
            raise ValueError("No hay productos con cantidad mayor a 0 para emitir la factura.")

        for item_despacho in items_emitibles:
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

        # Datos de cobranza, vendedor y bodega
        from ventas.models import Vendedor, FormaPago, Venta, VentaDetalle
        from datetime import timedelta
        from decimal import Decimal

        vendedor = orden_despacho.vendedor
        if not vendedor:
            vendedor = Vendedor.objects.filter(empresa=orden_despacho.empresa, activo=True).first()

        cliente = orden_despacho.orden_pedido.cliente
        forma_pago = orden_despacho.forma_pago or getattr(cliente, 'forma_pago_defecto', None)
        if not forma_pago:
            forma_pago = FormaPago.objects.filter(empresa=orden_despacho.empresa, activo=True).first()

        bodega = orden_despacho.bodega or orden_despacho.orden_pedido.bodega

        from core.fechas import calcular_fecha_vencimiento
        fecha_vencimiento = orden_despacho.fecha_vencimiento
        if not fecha_vencimiento:
            plazo = getattr(cliente, 'plazo_pago', 0) or getattr(cliente, 'dias_credito', 0) or 0
            fecha_vencimiento = calcular_fecha_vencimiento(orden_despacho.fecha_despacho, plazo)


        # Determinar si el pago es a crédito o al contado
        es_credito = bool(getattr(forma_pago, 'es_cuenta_corriente', False))
        if not es_credito and forma_pago:
            nombre_fp = forma_pago.nombre.lower()
            if 'credito' in nombre_fp or 'crédito' in nombre_fp or 'cuenta corriente' in nombre_fp:
                es_credito = True

        if es_credito:
            monto_pagado = Decimal('0.00')
            saldo_pendiente = Decimal(str(monto_total))
        else:
            monto_pagado = Decimal(str(monto_total))
            saldo_pendiente = Decimal('0.00')

        # Crear el registro de Venta para cuentas corrientes, comisiones e informes
        temp_numero = f"FACT-{siguiente_folio}"
        venta = Venta.objects.create(
            empresa=orden_despacho.empresa,
            sucursal=sucursal,
            numero_venta=temp_numero,
            fecha=orden_despacho.fecha_despacho,
            fecha_vencimiento=fecha_vencimiento,
            cliente=cliente,
            vendedor=vendedor,
            forma_pago=forma_pago,
            tipo_documento='factura',
            tipo_documento_planeado='factura',
            vehiculo=orden_despacho.vehiculo,
            chofer=orden_despacho.chofer,
            subtotal=Decimal(str(monto_neto + monto_exento)),
            neto=Decimal(str(monto_neto)),
            iva=Decimal(str(monto_iva)),
            total=Decimal(str(monto_total)),
            estado='confirmada',
            facturado=True,
            monto_pagado=monto_pagado,
            saldo_pendiente=saldo_pendiente,
            observaciones=f"Factura generada desde Despacho {orden_despacho.numero_despacho}",
            usuario_creacion=usuario,
        )

        for item_despacho in items_emitibles:
            item_pedido = item_despacho.item_pedido
            VentaDetalle.objects.create(
                venta=venta,
                articulo=item_pedido.articulo,
                comentario=f"Despacho {orden_despacho.numero_despacho}",
                cantidad=item_despacho.cantidad,
                precio_unitario=item_pedido.precio_unitario,
                precio_total=Decimal(str(item_despacho.cantidad * item_pedido.precio_unitario)),
            )

        # Rebajar stock de bodega si existe
        if bodega:
            try:
                from caja.views import descontar_stock_venta_completo
                descontar_stock_venta_completo(venta, bodega)
            except Exception as e_stock:
                print(f"[WARN] No se pudo descontar stock automáticamente: {e_stock}")

        # Crear el DTE
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=orden_despacho.empresa,
            tipo_dte='33',
            folio=siguiente_folio,
            fecha_emision=orden_despacho.fecha_despacho,
            usuario_creacion=usuario,
            estado_sii='NoEnviado',
            caf_utilizado=caf_disponible,
            venta=venta,
            vendedor=vendedor,
            chofer=orden_despacho.chofer,
            vehiculo=orden_despacho.vehiculo,
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

        for item_despacho in items_emitibles:
            item_despacho.factura = dte
            item_despacho.save(update_fields=['factura'])

        empresa = orden_despacho.empresa
        generator = DTEXMLGenerator(empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
        xml_sin_firmar = generator.generar_xml()
        primer_item = items_emitibles.select_related('item_pedido__articulo').first()
        item_glosa = primer_item.item_pedido.articulo.nombre if primer_item and primer_item.item_pedido else 'Factura Electrónica'
        dte_final = _finalizar_xml_dte_despacho(dte, xml_sin_firmar, item_glosa)

        # Sincronizar con Tesorería / Cuentas Corrientes de Clientes
        if es_credito and saldo_pendiente > 0:
            try:
                from tesoreria.services import sincronizar_venta_credito_en_tesoreria
                sincronizar_venta_credito_en_tesoreria(
                    venta=venta,
                    dte=dte_final,
                    usuario=usuario,
                    descripcion=f"Factura N° {dte_final.folio} (Despacho {orden_despacho.numero_despacho})"
                )
            except Exception as e_cc:
                print(f"[WARN] No se pudo sincronizar venta a crédito en tesorería: {e_cc}")

        return dte_final


