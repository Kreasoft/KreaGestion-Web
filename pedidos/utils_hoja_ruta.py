"""
Utilidades para generar hojas de ruta automáticamente
"""
from django.db import transaction
from django.utils import timezone
from facturacion_electronica.models import DocumentoTributarioElectronico
from .models_rutas import HojaRuta, Ruta


@transaction.atomic
def generar_hoja_ruta_automatica(dte, venta, empresa):
    """
    Genera o actualiza una hoja de ruta automáticamente al emitir una factura.
    
    Args:
        dte: DocumentoTributarioElectronico - La factura generada
        venta: Venta - La venta asociada
        empresa: Empresa - La empresa
    
    Returns:
        HojaRuta: La hoja de ruta creada o actualizada
    """
    # Verificar que la venta tenga cliente y ruta asignada
    if not venta.cliente:
        print(f"[HOJA RUTA] Venta {venta.numero_venta} no tiene cliente asignado, no se genera hoja de ruta")
        return None
    
    cliente = venta.cliente
    
    # Verificar que el cliente tenga ruta asignada
    if not cliente.ruta:
        print(f"[HOJA RUTA] Cliente {cliente.nombre} no tiene ruta asignada, no se genera hoja de ruta")
        return None
    
    ruta = cliente.ruta
    vehiculo = ruta.vehiculo
    if not vehiculo:
        print(f"[HOJA RUTA] Ruta {ruta.codigo} no tiene vehículo, no se genera hoja de ruta")
        return None

    # Chofer y acompañante van en el vehículo / se pueden cambiar; no agrupan la hoja.
    chofer = getattr(vehiculo, 'chofer', None) or ruta.chofer
    acompanante = ruta.acompanante
    fecha = venta.fecha

    hoja_ruta = HojaRuta.objects.filter(
        empresa=empresa,
        ruta=ruta,
        vehiculo=vehiculo,
        fecha=fecha,
        estado__in=['pendiente', 'en_ruta']
    ).first()

    if hoja_ruta:
        campos = []
        if chofer and hoja_ruta.chofer_id != chofer.id:
            hoja_ruta.chofer = chofer
            campos.append('chofer')
        if hoja_ruta.acompanante_id != getattr(acompanante, 'id', None):
            hoja_ruta.acompanante = acompanante
            campos.append('acompanante')
        if campos:
            hoja_ruta.save(update_fields=campos)
        hoja_ruta.facturas.add(dte)
        print(f"[HOJA RUTA] Factura {dte.folio} agregada a hoja de ruta existente: {hoja_ruta.numero_ruta}")
    else:
        hoja_ruta = HojaRuta.objects.create(
            empresa=empresa,
            ruta=ruta,
            vehiculo=vehiculo,
            chofer=chofer,
            acompanante=acompanante,
            fecha=fecha,
            estado='pendiente',
            creado_por=venta.usuario_creacion
        )
        hoja_ruta.facturas.add(dte)
        print(
            f"[HOJA RUTA] Nueva hoja de ruta creada: {hoja_ruta.numero_ruta} "
            f"para factura {dte.folio} (Ruta: {ruta.codigo}, Vehículo: {vehiculo.patente})"
        )
    
    return hoja_ruta

