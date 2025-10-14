#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.contrib.auth.models import User
from tesoreria.models import MovimientoCuentaCorrienteCliente
from empresas.models import Empresa
from decimal import Decimal

# Simular usuario superusuario
user = User.objects.filter(is_superuser=True).first()
print(f"Usuario: {user.username if user else 'No hay superusuario'}")

# Simular sesión sin empresa_activa
empresa_id = None

# Lógica EXACTA de la vista corregida
if empresa_id:
    try:
        empresa = Empresa.objects.get(id=empresa_id)
        print(f"Empresa desde sesión: {empresa.nombre}")
    except Empresa.DoesNotExist:
        empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        if not empresa:
            empresa = Empresa.objects.exclude(nombre='').first()
        if not empresa:
            empresa = Empresa.objects.first()
        print(f"Empresa fallback: {empresa.nombre if empresa else 'None'}")
else:
    empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
    if not empresa:
        empresa = Empresa.objects.exclude(nombre='').first()
    if not empresa:
        empresa = Empresa.objects.first()
    print(f"Empresa sin sesión: {empresa.nombre if empresa else 'None'}")

print(f"\n=== EMPRESA SELECCIONADA ===")
print(f"ID: {empresa.id}")
print(f"Nombre: '{empresa.nombre}'")
print(f"RUT: {empresa.rut}")

# Obtener movimientos EXACTAMENTE como la vista
print(f"\n=== CONSULTANDO MOVIMIENTOS ===")
movimientos_query = MovimientoCuentaCorrienteCliente.objects.filter(
    cuenta_corriente__empresa=empresa,
    tipo_movimiento='debe'
).select_related('cuenta_corriente', 'cuenta_corriente__cliente', 'venta').order_by('-fecha_movimiento')

print(f"Query SQL: {movimientos_query.query}")
print(f"\nTotal movimientos encontrados: {movimientos_query.count()}")

if movimientos_query.count() > 0:
    print("\n=== PROCESANDO MOVIMIENTOS ===")
    movimientos_list = []
    for mov in movimientos_query[:3]:  # Solo primeros 3 para debug
        # Calcular total pagado
        from django.db.models import Sum
        total_pagado_result = MovimientoCuentaCorrienteCliente.objects.filter(
            cuenta_corriente=mov.cuenta_corriente,
            venta=mov.venta,
            tipo_movimiento='haber'
        ).aggregate(total=Sum('monto'))['total']
        
        total_pagado = Decimal(str(total_pagado_result)) if total_pagado_result else Decimal('0')
        monto_factura = Decimal(str(mov.monto))
        
        # Determinar estado
        if total_pagado >= monto_factura:
            estado_pago = 'pagado'
        elif total_pagado > 0:
            estado_pago = 'parcial'
        else:
            estado_pago = 'pendiente'
        
        print(f"\n  ✓ Movimiento ID: {mov.id}")
        print(f"    Cliente: {mov.cuenta_corriente.cliente.nombre}")
        print(f"    Factura: {mov.venta.numero_venta if mov.venta else 'N/A'}")
        print(f"    Monto: ${int(monto_factura):,}")
        print(f"    Pagado: ${int(total_pagado):,}")
        print(f"    Saldo: ${int(monto_factura - total_pagado):,}")
        print(f"    Estado: {estado_pago}")
else:
    print("\n⚠ NO SE ENCONTRARON MOVIMIENTOS")
    print("\nVerificando todas las empresas:")
    for emp in Empresa.objects.all():
        count = MovimientoCuentaCorrienteCliente.objects.filter(
            cuenta_corriente__empresa=emp,
            tipo_movimiento='debe'
        ).count()
        print(f"  - {emp.nombre} (ID: {emp.id}): {count} movimientos")
