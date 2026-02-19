#!/usr/bin/env python
"""Script temporal para verificar hojas de ruta y facturas"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionCloud.settings')
django.setup()

from pedidos.models_rutas import HojaRuta
from facturacion_electronica.models import DocumentoTributarioElectronico
from clientes.models import Cliente
from datetime import date

hoy = date.today()
print(f'\n=== HOJAS DE RUTA PARA HOY ({hoy}) ===')
hojas = HojaRuta.objects.filter(fecha=hoy).select_related('ruta', 'vehiculo', 'chofer')
print(f'Total hojas de ruta: {hojas.count()}')

for hr in hojas:
    print(f'\nHoja: {hr.numero_ruta}')
    print(f'  Ruta: {hr.ruta.codigo if hr.ruta else None}')
    print(f'  Vehículo: {hr.vehiculo.patente if hr.vehiculo else None}')
    print(f'  Chofer: {hr.chofer.nombre if hr.chofer else None}')
    print(f'  Fecha: {hr.fecha}')
    print(f'  Facturas asociadas: {hr.facturas.count()}')
    facturas_ids = list(hr.facturas.values_list('id', flat=True))
    print(f'  Facturas IDs: {facturas_ids}')
    
    # Verificar facturas esperadas
    if hr.ruta:
        clientes_ruta = hr.ruta.clientes.filter(estado='activo')
        print(f'  Clientes en ruta: {clientes_ruta.count()}')
        facturas_esperadas = DocumentoTributarioElectronico.objects.filter(
            fecha_emision=hoy,
            tipo_dte__in=['33', '34'],
            venta__cliente__in=clientes_ruta
        )
        print(f'  Facturas esperadas (clientes de ruta): {facturas_esperadas.count()}')
        facturas_esperadas_ids = list(facturas_esperadas.values_list('id', flat=True))
        print(f'  Facturas IDs esperadas: {facturas_esperadas_ids}')

print(f'\n=== FACTURAS PARA HOY ({hoy}) ===')
facturas = DocumentoTributarioElectronico.objects.filter(
    fecha_emision=hoy,
    tipo_dte__in=['33', '34']
).select_related('venta__cliente', 'venta__vehiculo', 'vehiculo')
print(f'Total facturas: {facturas.count()}')

for f in facturas[:10]:
    print(f'\nFactura Folio: {f.folio}')
    print(f'  Cliente: {f.venta.cliente.nombre if f.venta and f.venta.cliente else None}')
    print(f'  Cliente Ruta: {f.venta.cliente.ruta.codigo if f.venta and f.venta.cliente and f.venta.cliente.ruta else None}')
    print(f'  Vehículo DTE: {f.vehiculo.patente if f.vehiculo else None}')
    print(f'  Vehículo Venta: {f.venta.vehiculo.patente if f.venta and f.venta.vehiculo else None}')
    print(f'  En hojas de ruta: {f.hojas_ruta.count()}')

