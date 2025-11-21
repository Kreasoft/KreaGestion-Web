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
    
    # Verificar que la venta tenga vehículo y chofer
    if not venta.vehiculo or not venta.chofer:
        print(f"[HOJA RUTA] Venta {venta.numero_venta} no tiene vehículo o chofer asignado, no se genera hoja de ruta")
        return None
    
    vehiculo = venta.vehiculo
    chofer = venta.chofer
    fecha = venta.fecha
    
    # Buscar si ya existe una hoja de ruta para esta combinación
    hoja_ruta = HojaRuta.objects.filter(
        empresa=empresa,
        ruta=ruta,
        vehiculo=vehiculo,
        chofer=chofer,
        fecha=fecha,
        estado__in=['pendiente', 'en_ruta']
    ).first()
    
    if hoja_ruta:
        # Agregar la factura a la hoja de ruta existente
        hoja_ruta.facturas.add(dte)
        print(f"[HOJA RUTA] Factura {dte.folio} agregada a hoja de ruta existente: {hoja_ruta.numero_ruta}")
    else:
        # Crear nueva hoja de ruta
        hoja_ruta = HojaRuta.objects.create(
            empresa=empresa,
            ruta=ruta,
            vehiculo=vehiculo,
            chofer=chofer,
            fecha=fecha,
            estado='pendiente',
            creado_por=venta.usuario_creacion
        )
        
        # Agregar la factura
        hoja_ruta.facturas.add(dte)
        
        print(f"[HOJA RUTA] Nueva hoja de ruta creada: {hoja_ruta.numero_ruta} para factura {dte.folio}")
    
    return hoja_ruta

