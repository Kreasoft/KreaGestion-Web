"""
Utilidades para gestión de despachos de pedidos
"""
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from empresas.models import Empresa
from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF
from inventario.models import TransferenciaInventario, Inventario


# Alias para mantener compatibilidad
def crear_transferencia_inventario(despacho, items_data=None):
    """
    Alias para crear_transferencia_despacho - mantiene compatibilidad
    """
    return crear_transferencia_despacho(despacho, items_data)


def crear_transferencia_despacho(despacho, items_data=None):
    """
    Crea una transferencia de inventario para el despacho
    Solo para los items que se están despachando

    Args:
        despacho: El objeto despacho
        items_data: Diccionario opcional con datos de items del POST
    """
    try:
        # Extraer datos del despacho
        empresa_obj = despacho.empresa
        pedido_obj = despacho.pedido
        user_obj = despacho.creado_por

        print(f"🔄 Creando transferencia para pedido {pedido_obj.numero_pedido}")

        # Crear transferencia desde bodega del pedido (para despachos no hay bodega destino)
        transferencia_kwargs = {
            'empresa': empresa_obj,
            'bodega_origen': pedido_obj.bodega,
            'numero_folio': f"TRF-{pedido_obj.numero_pedido}",
            'fecha_transferencia': timezone.now(),
            'observaciones': f"Transferencia automática por despacho de pedido {pedido_obj.numero_pedido}",
            'estado': 'confirmado',
            'creado_por': user_obj
        }

        # Solo agregar bodega_destino si existe
        if hasattr(pedido_obj, 'bodega_destino') and pedido_obj.bodega_destino:
            transferencia_kwargs['bodega_destino'] = pedido_obj.bodega_destino

        transferencia = TransferenciaInventario.objects.create(**transferencia_kwargs)

        # Crear movimientos de inventario solo para items que se están despachando
        items_despachados = despacho.get_items_despachados()

        # Si no hay items guardados aún, usar datos del POST
        if items_despachados.count() == 0 and items_data:
            for item_pedido in pedido_obj.items.all():
                item_id = str(item_pedido.id)
                checkbox_name = f'despachar_{item_id}'
                cantidad_name = f'item_{item_id}'

                if checkbox_name in items_data and items_data[checkbox_name] == 'on':
                    cantidad = float(items_data.get(cantidad_name, 0))
                    if cantidad > 0:
                        # Crear movimiento de inventario directamente
                        Inventario.objects.create(
                            empresa=empresa_obj,
                            bodega_origen=pedido_obj.bodega,
                            articulo=item_pedido.articulo,
                            transferencia=transferencia,
                            tipo_movimiento='transferencia',
                            cantidad=cantidad,
                            precio_unitario=item_pedido.precio_unitario,
                            descripcion=f"Salida por despacho {pedido_obj.numero_pedido}",
                            estado='confirmado',
                            fecha_movimiento=timezone.now(),
                            creado_por=user_obj
                        )
        else:
            for item_despacho in items_despachados:
                # Movimiento de salida de la bodega origen
                Inventario.objects.create(
                    empresa=despacho.empresa,
                    bodega_origen=despacho.pedido.bodega,
                    articulo=item_despacho.item_pedido.articulo,
                    transferencia=transferencia,
                    tipo_movimiento='transferencia',
                    cantidad=item_despacho.cantidad_despachar,
                    precio_unitario=item_despacho.item_pedido.precio_unitario,
                    descripcion=f"Salida por despacho {despacho.pedido.numero_pedido}",
                    estado='confirmado',
                    fecha_movimiento=timezone.now(),
                    creado_por=despacho.creado_por
                )

        # Actualizar stock de la bodega origen
        from inventario.utils import actualizar_stock_bodega
        actualizar_stock_bodega(pedido_obj.bodega, empresa_obj)

        return transferencia

    except Exception as e:
        raise Exception(f"Error al crear transferencia de inventario: {str(e)}")


# TODO: Implementar generación de DTE correctamente
# def generar_documento_despacho(despacho):
#     """
#     Genera el documento DTE correspondiente al tipo de despacho
#     """
#     # Esta función está comentada temporalmente hasta implementar
#     # la generación correcta de DTE
#     pass


def preparar_datos_documento(despacho, tipo_dte):
    """
    Prepara los datos necesarios para generar el documento DTE
    """
    pedido = despacho.pedido
    cliente = pedido.cliente
    empresa = despacho.empresa

    # Datos comunes
    datos = {
        'fecha_emision': datetime.now().date(),
        'rut_receptor': cliente.rut,
        'razon_social_receptor': cliente.nombre,
        'giro_receptor': getattr(cliente, 'giro', ''),
        'direccion_receptor': despacho.direccion_entrega or cliente.direccion,
        'comuna_receptor': getattr(cliente, 'comuna', ''),
        'ciudad_receptor': getattr(cliente, 'ciudad', ''),
    }

    # Items del documento
    items = []
    for item_pedido in pedido.items.all():
        item = {
            'codigo': item_pedido.articulo.codigo,
            'nombre': item_pedido.articulo.nombre,
            'cantidad': float(item_pedido.cantidad),
            'precio_unitario': int(item_pedido.precio_unitario),
            'descuento_porcentaje': float(item_pedido.descuento_porcentaje),
            'unidad_medida': 'UN'  # Unidad por defecto
        }

        # Calcular montos
        subtotal = item['cantidad'] * item['precio_unitario']
        descuento_monto = subtotal * (item['descuento_porcentaje'] / 100)
        base_imponible = subtotal - descuento_monto
        iva_monto = base_imponible * 0.19  # IVA 19%

        item.update({
            'subtotal': int(subtotal),
            'descuento_monto': int(descuento_monto),
            'base_imponible': int(base_imponible),
            'iva_monto': int(iva_monto),
            'total': int(base_imponible + iva_monto)
        })

        items.append(item)

    datos['items'] = items

    # Calcular totales
    subtotal_total = sum(item['subtotal'] for item in items)
    descuento_total = sum(item['descuento_monto'] for item in items)
    iva_total = sum(item['iva_monto'] for item in items)
    total_documento = subtotal_total - descuento_total + iva_total

    datos.update({
        'monto_neto': int(subtotal_total - descuento_total),
        'monto_exento': 0,
        'monto_iva': int(iva_total),
        'monto_total': int(total_documento)
    })

    # Datos específicos para guías de despacho
    if tipo_dte == '52':
        datos.update({
            'tipo_traslado': '1',  # Venta
            'glosa_sii': f"Despacho de pedido {pedido.numero_pedido}"
        })

    # Observaciones
    observaciones = []
    if despacho.observaciones:
        observaciones.append(despacho.observaciones)
    if despacho.transportista:
        observaciones.append(f"Transportista: {despacho.transportista}")
    if despacho.patente_vehiculo:
        observaciones.append(f"Patente: {despacho.patente_vehiculo}")

    if observaciones:
        datos['observaciones'] = ' | '.join(observaciones)

    return datos


def actualizar_stock_despacho(despacho):
    """
    Actualiza el stock después de un despacho
    """
    try:
        # La transferencia ya se creó y actualizó el stock
        # Solo necesitamos verificar que esté correcto
        from inventario.utils import actualizar_stock_bodega

        # Actualizar stock de la bodega origen
        actualizar_stock_bodega(despacho.pedido.bodega, despacho.empresa)

        # Si es una transferencia a otra bodega, actualizar también el destino
        if hasattr(despacho.transferencia_inventario, 'bodega_destino'):
            actualizar_stock_bodega(despacho.transferencia_inventario.bodega_destino, despacho.empresa)

        return True

    except Exception as e:
        raise Exception(f"Error al actualizar stock del despacho: {str(e)}")


def puede_despachar_pedido(pedido):
    """
    Verifica si un pedido puede ser despachado
    """
    # Verificar estado del pedido
    if not pedido.puede_despachar():
        return False, f"Estado del pedido no permite despacho: {pedido.get_estado_display()}"

    # Verificar stock disponible
    for item in pedido.items.all():
        # Aquí se debería verificar el stock real de la bodega
        # Por simplicidad, asumimos que hay stock suficiente
        pass

    # Verificar que no tenga despachos activos
    if pedido.tiene_despachos_pendientes():
        return False, "El pedido ya tiene despachos en proceso"

    return True, "Pedido listo para despachar"







