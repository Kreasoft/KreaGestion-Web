#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from tesoreria.models import MovimientoCuentaCorrienteCliente
from empresas.models import Empresa

empresa = Empresa.objects.first()
print(f'Empresa: {empresa.nombre if empresa else "No hay empresa"}')
print(f'Empresa ID: {empresa.id if empresa else None}')

if empresa:
    movs = MovimientoCuentaCorrienteCliente.objects.filter(
        cuenta_corriente__empresa=empresa,
        tipo_movimiento='debe'
    ).select_related('cuenta_corriente', 'cuenta_corriente__cliente', 'venta')
    
    print(f'\nTotal movimientos DEBE: {movs.count()}')
    
    for m in movs[:5]:
        print(f'\n  Movimiento ID: {m.id}')
        print(f'  Cliente: {m.cuenta_corriente.cliente.nombre}')
        print(f'  Venta: {m.venta.numero_venta if m.venta else "Sin venta"}')
        print(f'  Monto: ${m.monto}')
        print(f'  Fecha: {m.fecha_movimiento}')
