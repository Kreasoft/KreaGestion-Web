#!/usr/bin/env python
"""Script para verificar datos de hoja de ruta"""
import os
import sys
import django

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionCloud.settings')
django.setup()

from pedidos.models_rutas import HojaRuta
from facturacion_electronica.models import DocumentoTributarioElectronico
from clientes.models import Cliente
from django.utils import timezone
from django.db.models import Q

# Obtener la primera hoja de ruta
hr = HojaRuta.objects.first()

if not hr:
    print("No hay hojas de ruta en la base de datos")
    exit()

print("=" * 60)
print("INFORMACIÓN DE LA HOJA DE RUTA")
print("=" * 60)
print(f"ID: {hr.id}")
print(f"Número: {hr.numero_ruta}")
print(f"Fecha: {hr.fecha}")
print(f"Ruta: {hr.ruta.codigo if hr.ruta else None} - {hr.ruta.nombre if hr.ruta else None}")
print(f"Vehículo: {hr.vehiculo.patente if hr.vehiculo else None}")
print(f"Chofer: {hr.chofer.nombre if hr.chofer else None}")
print(f"Facturas asociadas: {hr.facturas.count()}")
print()

print("=" * 60)
print("CLIENTES DE LA RUTA")
print("=" * 60)
if hr.ruta:
    clientes = hr.ruta.clientes.filter(estado='activo')
    print(f"Total clientes activos: {clientes.count()}")
    for c in clientes[:10]:
        print(f"  - {c.nombre} (RUT: {c.rut})")
else:
    print("No hay ruta asignada")
print()

print("=" * 60)
print("FACTURAS DEL DÍA")
print("=" * 60)
facturas_dia = DocumentoTributarioElectronico.objects.filter(
    fecha_emision=hr.fecha,
    tipo_dte__in=['33', '34']
)
print(f"Total facturas del día {hr.fecha}: {facturas_dia.count()}")
for f in facturas_dia[:10]:
    cliente_nombre = f.venta.cliente.nombre if f.venta and f.venta.cliente else 'Sin cliente'
    print(f"  - Folio {f.folio}: {cliente_nombre} (Fecha: {f.fecha_emision})")
print()

print("=" * 60)
print("FACTURAS DE CLIENTES DE LA RUTA DEL DÍA")
print("=" * 60)
if hr.ruta:
    facturas_ruta = DocumentoTributarioElectronico.objects.filter(
        fecha_emision=hr.fecha,
        tipo_dte__in=['33', '34'],
        venta__cliente__ruta=hr.ruta
    )
    print(f"Facturas de clientes de la ruta: {facturas_ruta.count()}")
    for f in facturas_ruta[:20]:
        cliente_nombre = f.venta.cliente.nombre if f.venta and f.venta.cliente else 'Sin cliente'
        vehiculo_dte = f.vehiculo.patente if f.vehiculo else None
        vehiculo_venta = f.venta.vehiculo.patente if f.venta and f.venta.vehiculo else None
        print(f"  - Folio {f.folio}: {cliente_nombre}")
        print(f"    Vehículo DTE: {vehiculo_dte}, Vehículo Venta: {vehiculo_venta}")
else:
    print("No hay ruta asignada")
print()

print("=" * 60)
print("FACTURAS YA EN OTRAS HOJAS DE RUTA")
print("=" * 60)
facturas_en_otras = HojaRuta.objects.exclude(pk=hr.pk).values_list('facturas__id', flat=True)
facturas_en_otras_list = list(facturas_en_otras)
print(f"Facturas en otras hojas: {len(facturas_en_otras_list)}")
if facturas_en_otras_list:
    print(f"IDs: {facturas_en_otras_list[:10]}")
print()

print("=" * 60)
print("FACTURAS DISPONIBLES PARA ASOCIAR")
print("=" * 60)
if hr.ruta:
    facturas_disponibles = DocumentoTributarioElectronico.objects.filter(
        fecha_emision=hr.fecha,
        tipo_dte__in=['33', '34'],
        venta__cliente__ruta=hr.ruta
    ).exclude(id__in=facturas_en_otras_list)
    print(f"Facturas disponibles: {facturas_disponibles.count()}")
    for f in facturas_disponibles[:20]:
        cliente_nombre = f.venta.cliente.nombre if f.venta and f.venta.cliente else 'Sin cliente'
        print(f"  - Folio {f.folio}: {cliente_nombre} (ID: {f.id})")
else:
    print("No hay ruta asignada")
print()

print("=" * 60)
print("VERIFICACIÓN POR VEHÍCULO")
print("=" * 60)
if hr.vehiculo:
    facturas_vehiculo = DocumentoTributarioElectronico.objects.filter(
        fecha_emision=hr.fecha,
        tipo_dte__in=['33', '34']
    ).filter(
        Q(vehiculo=hr.vehiculo) | Q(venta__vehiculo=hr.vehiculo)
    )
    print(f"Facturas con vehículo {hr.vehiculo.patente}: {facturas_vehiculo.count()}")
    for f in facturas_vehiculo[:10]:
        cliente_nombre = f.venta.cliente.nombre if f.venta and f.venta.cliente else 'Sin cliente'
        print(f"  - Folio {f.folio}: {cliente_nombre}")
else:
    print("No hay vehículo asignado")

