"""
Script para depurar tickets pendientes
Ejecutar con: python manage.py shell < debug_tickets.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta
from django.utils import timezone

print("\n" + "="*80)
print("DEBUG: TICKETS PENDIENTES EN LA BASE DE DATOS")
print("="*80)

# Obtener todos los tickets pendientes (sin filtro de fecha)
tickets_todos = Venta.objects.filter(
    tipo_documento='vale',
    estado='borrador'
).order_by('-fecha_creacion')

print(f"\nTotal de tickets pendientes (todos): {tickets_todos.count()}")
print("-"*80)

for ticket in tickets_todos:
    print(f"\nTicket #{ticket.numero_venta}")
    print(f"  ID: {ticket.id}")
    print(f"  Cliente: {ticket.cliente.nombre if ticket.cliente else 'Sin cliente'}")
    print(f"  Total: ${ticket.total:,.0f}")
    print(f"  Fecha (campo fecha): {ticket.fecha}")
    print(f"  Fecha creación: {ticket.fecha_creacion}")
    print(f"  Estado: {ticket.estado}")
    print(f"  Tipo documento: {ticket.tipo_documento}")

# Obtener tickets del día actual
hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
hoy_fin = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)

tickets_hoy = Venta.objects.filter(
    tipo_documento='vale',
    estado='borrador',
    fecha_creacion__gte=hoy_inicio,
    fecha_creacion__lte=hoy_fin
).order_by('-fecha_creacion')

print("\n" + "="*80)
print(f"TICKETS PENDIENTES DEL DÍA ACTUAL (usando fecha_creacion): {tickets_hoy.count()}")
print(f"Rango: {hoy_inicio} a {hoy_fin}")
print("="*80)

for ticket in tickets_hoy:
    print(f"\nTicket #{ticket.numero_venta}")
    print(f"  ID: {ticket.id}")
    print(f"  Cliente: {ticket.cliente.nombre if ticket.cliente else 'Sin cliente'}")
    print(f"  Total: ${ticket.total:,.0f}")
    print(f"  Fecha creación: {ticket.fecha_creacion}")

print("\n" + "="*80)
