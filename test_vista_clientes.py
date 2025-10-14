#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from tesoreria.models import MovimientoCuentaCorrienteCliente
from empresas.models import Empresa
from decimal import Decimal

# Simular la lógica de la vista
empresa_id = None  # Sin empresa en sesión

if empresa_id:
    try:
        empresa = Empresa.objects.get(id=empresa_id)
    except Empresa.DoesNotExist:
        empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        if not empresa:
            empresa = Empresa.objects.exclude(nombre='').first()
        if not empresa:
            empresa = Empresa.objects.first()
else:
    empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
    if not empresa:
        empresa = Empresa.objects.exclude(nombre='').first()
    if not empresa:
        empresa = Empresa.objects.first()

print(f"Empresa seleccionada: {empresa.nombre} (ID: {empresa.id})")

# Obtener movimientos
movimientos_query = MovimientoCuentaCorrienteCliente.objects.filter(
    cuenta_corriente__empresa=empresa,
    tipo_movimiento='debe'
).select_related('cuenta_corriente', 'cuenta_corriente__cliente', 'venta').order_by('-fecha_movimiento')

print(f"\nTotal movimientos DEBE: {movimientos_query.count()}")

# Procesar movimientos como en la vista
movimientos_list = []
for mov in movimientos_query:
    # Calcular total pagado para esta factura
    total_pagado_result = MovimientoCuentaCorrienteCliente.objects.filter(
        cuenta_corriente=mov.cuenta_corriente,
        venta=mov.venta,
        tipo_movimiento='haber'
    ).aggregate(total=django.db.models.Sum('monto'))['total']
    
    total_pagado = Decimal(str(total_pagado_result)) if total_pagado_result else Decimal('0')
    monto_factura = Decimal(str(mov.monto))
    
    # Determinar estado
    if total_pagado >= monto_factura:
        mov.estado_pago = 'pagado'
    elif total_pagado > 0:
        mov.estado_pago = 'parcial'
    else:
        mov.estado_pago = 'pendiente'
    
    mov.monto_display = int(monto_factura)
    mov.total_pagado = int(total_pagado)
    mov.saldo_pendiente_factura = int(monto_factura - total_pagado)
    movimientos_list.append(mov)
    
    print(f"\n  Movimiento ID: {mov.id}")
    print(f"  Cliente: {mov.cuenta_corriente.cliente.nombre}")
    print(f"  Factura: {mov.venta.numero_venta if mov.venta else 'N/A'}")
    print(f"  Monto: ${mov.monto_display:,}")
    print(f"  Pagado: ${mov.total_pagado:,}")
    print(f"  Saldo: ${mov.saldo_pendiente_factura:,}")
    print(f"  Estado: {mov.estado_pago}")

print(f"\n✓ Total registros procesados: {len(movimientos_list)}")
