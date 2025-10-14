#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from tesoreria.models import MovimientoCuentaCorrienteCliente, CuentaCorrienteCliente
from empresas.models import Empresa

print("=== EMPRESAS DISPONIBLES ===")
empresas = Empresa.objects.all()
for emp in empresas:
    print(f"\nEmpresa ID: {emp.id}")
    print(f"  Nombre: '{emp.nombre}'")
    print(f"  RUT: {emp.rut}")
    
    # Contar cuentas corrientes
    cuentas = CuentaCorrienteCliente.objects.filter(empresa=emp).count()
    print(f"  Cuentas corrientes: {cuentas}")
    
    # Contar movimientos
    movs_debe = MovimientoCuentaCorrienteCliente.objects.filter(
        cuenta_corriente__empresa=emp,
        tipo_movimiento='debe'
    ).count()
    movs_haber = MovimientoCuentaCorrienteCliente.objects.filter(
        cuenta_corriente__empresa=emp,
        tipo_movimiento='haber'
    ).count()
    print(f"  Movimientos DEBE: {movs_debe}")
    print(f"  Movimientos HABER: {movs_haber}")

print("\n=== MOVIMIENTOS TOTALES ===")
total_movs = MovimientoCuentaCorrienteCliente.objects.all().count()
print(f"Total movimientos en sistema: {total_movs}")

# Ver algunos movimientos
print("\n=== PRIMEROS 5 MOVIMIENTOS ===")
movs = MovimientoCuentaCorrienteCliente.objects.all().select_related(
    'cuenta_corriente', 'cuenta_corriente__empresa', 'cuenta_corriente__cliente'
)[:5]
for m in movs:
    print(f"\nMovimiento ID: {m.id}")
    print(f"  Empresa: {m.cuenta_corriente.empresa.nombre} (ID: {m.cuenta_corriente.empresa.id})")
    print(f"  Cliente: {m.cuenta_corriente.cliente.nombre}")
    print(f"  Tipo: {m.tipo_movimiento}")
    print(f"  Monto: ${m.monto}")
