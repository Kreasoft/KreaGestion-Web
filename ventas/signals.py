from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal
from .models import Venta, VentaDetalle
from inventario.models import Stock, Inventario


def print(*args, **kwargs):
    """Evita que mensajes de depuracion rompan signals si stdout falla."""
    return None


def _debe_rebajar_stock(venta):
    """La rebaja de stock solo aplica al facturar el documento, no al crear el ticket."""
    if venta.tipo_documento == 'cotizacion':
        return False
    if venta.estado != 'confirmada':
        return False
    if venta.tipo_documento == 'ticket':
        return bool(venta.facturado)
    return True


@receiver(post_save, sender=Venta)
def actualizar_stock_venta(sender, instance, created, **kwargs):
    """
    Actualiza el stock cuando se factura o anula un documento.
    Los tickets pendientes (facturado=False) no rebajan inventario.
    """
    from inventario.models import Inventario
    movimientos_existentes = Inventario.objects.filter(
        empresa=instance.empresa,
        numero_documento=instance.numero_venta,
        tipo_movimiento='salida',
        estado='confirmado'
    ).exists()

    if _debe_rebajar_stock(instance) and not movimientos_existentes:
        descontar_stock_venta(instance)
    elif instance.estado == 'anulada':
        reponer_stock_venta(instance)


def descontar_stock_venta(venta):
    """
    Descuenta el stock de los artículos de una venta confirmada.
    Crea movimientos de inventario tipo 'salida'.
    """
    # Verificar que la venta tenga detalles
    detalles = venta.ventadetalle_set.all()
    
    if not detalles:
        return
    
    from bodegas.models import Bodega
    bodega = None
    if getattr(venta, 'sucursal_id', None):
        bodega = Bodega.objects.filter(empresa=venta.empresa, sucursal=venta.sucursal, activa=True).first()
    if not bodega:
        bodega = Bodega.objects.filter(empresa=venta.empresa, activa=True).first()

    if not bodega:
        print(f"WARNING: No se encontró bodega activa para la empresa {venta.empresa}")
        return
    
    with transaction.atomic():
        for detalle in detalles:
            articulo = detalle.articulo
            
            # Solo descontar si el artículo tiene control de stock
            if not articulo.control_stock:
                continue
            
            # Verificar si ya existe un movimiento de inventario para esta venta y artículo
            # Esto evita duplicados cuando el signal se ejecuta múltiples veces
            movimiento_existente = Inventario.objects.filter(
                empresa=venta.empresa,
                bodega_origen=bodega,
                articulo=articulo,
                tipo_movimiento='salida',
                numero_documento=venta.numero_venta,
                estado='confirmado'
            ).first()
            
            if movimiento_existente:
                # Si ya existe un movimiento, solo actualizar el stock si es necesario
                # pero no crear otro movimiento
                print(f"[INFO] Movimiento de inventario ya existe para venta {venta.numero_venta}, artículo {articulo.nombre}. Saltando creación duplicada.")
                continue
            
            # Obtener o crear el registro de stock
            stock, created = Stock.objects.get_or_create(
                empresa=venta.empresa,
                bodega=bodega,
                articulo=articulo,
                defaults={
                    'cantidad': Decimal('0'),
                    'stock_minimo': Decimal(str(articulo.stock_minimo)) if articulo.stock_minimo else Decimal('0'),
                    'stock_maximo': Decimal(str(articulo.stock_maximo)) if articulo.stock_maximo else Decimal('0'),
                    'precio_promedio': Decimal(str(articulo.precio_costo)) if articulo.precio_costo else Decimal('0'),
                }
            )
            
            # Descontar la cantidad
            stock.cantidad -= detalle.cantidad
            
            # No permitir stock negativo
            if stock.cantidad < 0:
                stock.cantidad = Decimal('0')
            
            stock.save()
            
            # Crear movimiento de inventario
            Inventario.objects.create(
                empresa=venta.empresa,
                bodega_origen=bodega,
                articulo=articulo,
                tipo_movimiento='salida',
                cantidad=detalle.cantidad,
                precio_unitario=detalle.precio_unitario,
                descripcion=f'Venta {venta.numero_venta} - {venta.get_tipo_documento_display()}',
                numero_documento=venta.numero_venta,
                estado='confirmado',
                creado_por=venta.usuario_creacion
            )


def reponer_stock_venta(venta):
    """
    Repone el stock de los artículos de una venta anulada.
    Crea movimientos de inventario tipo 'entrada' con motivo de anulación.
    """
    # Verificar que la venta tenga detalles
    detalles = venta.ventadetalle_set.all()
    
    if not detalles:
        return
    
    # Obtener la bodega principal de la empresa
    from bodegas.models import Bodega
    bodega = Bodega.objects.filter(empresa=venta.empresa, activa=True).first()
    
    if not bodega:
        print(f"WARNING: No se encontró bodega activa para la empresa {venta.empresa}")
        return
    
    with transaction.atomic():
        for detalle in detalles:
            articulo = detalle.articulo
            
            # Solo reponer si el artículo tiene control de stock
            if not articulo.control_stock:
                continue
            
            # Obtener o crear el registro de stock
            stock, created = Stock.objects.get_or_create(
                empresa=venta.empresa,
                bodega=bodega,
                articulo=articulo,
                defaults={
                    'cantidad': Decimal('0'),
                    'stock_minimo': Decimal(str(articulo.stock_minimo)) if articulo.stock_minimo else Decimal('0'),
                    'stock_maximo': Decimal(str(articulo.stock_maximo)) if articulo.stock_maximo else Decimal('0'),
                    'precio_promedio': Decimal(str(articulo.precio_costo)) if articulo.precio_costo else Decimal('0'),
                }
            )
            
            # Reponer la cantidad
            stock.cantidad += detalle.cantidad
            stock.save()
            
            # Crear movimiento de inventario
            Inventario.objects.create(
                empresa=venta.empresa,
                bodega_destino=bodega,
                articulo=articulo,
                tipo_movimiento='entrada',
                cantidad=detalle.cantidad,
                precio_unitario=detalle.precio_unitario,
                descripcion=f'Anulación de Venta {venta.numero_venta} - {venta.get_tipo_documento_display()}',
                motivo='Anulación de venta',
                numero_documento=venta.numero_venta,
                estado='confirmado',
                creado_por=venta.usuario_creacion
            )
