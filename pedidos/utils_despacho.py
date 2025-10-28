"""
Funciones de utilidad para la gestión de despachos.
"""
from django.db import transaction, models
from facturacion_electronica.models import DocumentoTributarioElectronico, DetalleDocumentoTributarioElectronico, Folio

def generar_guia_desde_orden_despacho(orden_despacho, usuario):
    """
    Genera una Guía de Despacho (DTE 52) a partir de una orden de despacho.
    """
    with transaction.atomic():
        if DocumentoTributarioElectronico.objects.filter(orden_despacho=orden_despacho, tipo_dte='52').exists():
            raise Exception("Ya existe una Guía de Despacho para esta orden.")

        folio_disponible = Folio.objects.filter(
            empresa=orden_despacho.empresa,
            tipo_dte='52',
            activo=True,
            folio_actual__lt=models.F('folio_final')
        ).first()

        if not folio_disponible:
            raise Exception("No hay folios disponibles para Guías de Despacho (52).")

        dte = DocumentoTributarioElectronico.objects.create(
            empresa=orden_despacho.empresa,
            tipo_dte='52',
            folio=folio_disponible.folio_actual + 1,
            orden_despacho=orden_despacho,
            cliente=orden_despacho.orden_pedido.cliente,
            fecha_emision=orden_despacho.fecha_despacho,
            creado_por=usuario,
            estado_sii='NoEnviado'
        )

        for item_despacho in orden_despacho.items.all():
            DetalleDocumentoTributarioElectronico.objects.create(
                dte=dte,
                articulo=item_despacho.item_pedido.articulo,
                nombre=item_despacho.item_pedido.articulo.nombre,
                cantidad=item_despacho.cantidad,
                precio_unitario=item_despacho.item_pedido.precio_unitario,
                impuesto_especifico=0,
                unidad_medida=item_despacho.item_pedido.articulo.get_unidad_medida_display(),
            )
        
        folio_disponible.folio_actual += 1
        folio_disponible.save()

        return dte

def generar_factura_desde_orden_despacho(orden_despacho, usuario):
    """
    Genera una Factura Electrónica (DTE 33) a partir de una orden de despacho.
    """
    with transaction.atomic():
        if DocumentoTributarioElectronico.objects.filter(orden_despacho=orden_despacho).exists():
            raise Exception("Ya existe un documento tributario para esta orden de despacho.")

        folio_disponible = Folio.objects.filter(
            empresa=orden_despacho.empresa,
            tipo_dte='33',
            activo=True,
            folio_actual__lt=models.F('folio_final')
        ).first()

        if not folio_disponible:
            raise Exception("No hay folios disponibles para Facturas Electrónicas (33).")

        dte = DocumentoTributarioElectronico.objects.create(
            empresa=orden_despacho.empresa,
            tipo_dte='33',
            folio=folio_disponible.folio_actual + 1,
            orden_despacho=orden_despacho,
            cliente=orden_despacho.orden_pedido.cliente,
            fecha_emision=orden_despacho.fecha_despacho,
            creado_por=usuario,
            estado_sii='NoEnviado'
        )

        for item_despacho in orden_despacho.items.all():
            DetalleDocumentoTributarioElectronico.objects.create(
                dte=dte,
                articulo=item_despacho.item_pedido.articulo,
                nombre=item_despacho.item_pedido.articulo.nombre,
                cantidad=item_despacho.cantidad,
                precio_unitario=item_despacho.item_pedido.precio_unitario,
                impuesto_especifico=0,
                unidad_medida=item_despacho.item_pedido.articulo.get_unidad_medida_display(),
            )
        
        folio_disponible.folio_actual += 1
        folio_disponible.save()

        return dte
