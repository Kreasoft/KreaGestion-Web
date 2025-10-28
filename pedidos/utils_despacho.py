"""
Funciones de utilidad para la gestión de despachos.
"""
from django.db import transaction, models
from facturacion_electronica.models import DocumentoTributarioElectronico, DetalleDocumentoTributarioElectronico, ArchivoCAF

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
            
            DetalleDocumentoTributarioElectronico.objects.create(
                dte=dte,
                articulo=articulo,
                nombre=articulo.nombre,
                cantidad=item_despacho.cantidad,
                precio_unitario=item_despacho.item_pedido.precio_unitario,
                impuesto_especifico=0,
                unidad_medida=unidad,
            )
            
            # Vincular la guía de despacho con el item
            item_despacho.guia_despacho = dte
            item_despacho.save()

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
            
            DetalleDocumentoTributarioElectronico.objects.create(
                dte=dte,
                articulo=articulo,
                nombre=articulo.nombre,
                cantidad=item_despacho.cantidad,
                precio_unitario=item_despacho.item_pedido.precio_unitario,
                impuesto_especifico=0,
                unidad_medida=unidad,
            )
            
            # Vincular la factura con el item
            item_despacho.factura = dte
            item_despacho.save()

        return dte
