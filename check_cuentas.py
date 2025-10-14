import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from tesoreria.models import CuentaCorrienteCliente, CuentaCorrienteProveedor, MovimientoCuentaCorrienteCliente
from clientes.models import Cliente
from proveedores.models import Proveedor

print("=" * 80)
print("VERIFICACIÓN DE CUENTAS CORRIENTES - KREASOFT")
print("=" * 80)

# Buscar empresa Kreasoft
try:
    empresa = Empresa.objects.filter(nombre__icontains='kreasoft').first()
    if not empresa:
        empresa = Empresa.objects.first()
    
    print(f"\n✓ Empresa: {empresa.nombre}")
    print(f"  RUT: {empresa.rut}")
    print(f"  ID: {empresa.id}")
except Exception as e:
    print(f"\n✗ Error al obtener empresa: {e}")
    exit()

# Verificar Clientes
print("\n" + "=" * 80)
print("CLIENTES")
print("=" * 80)
clientes = Cliente.objects.filter(empresa=empresa)
print(f"Total clientes: {clientes.count()}")
for cliente in clientes[:5]:
    print(f"  - {cliente.nombre} (RUT: {cliente.rut})")

# Verificar Cuentas Corrientes de Clientes
print("\n" + "=" * 80)
print("CUENTAS CORRIENTES DE CLIENTES")
print("=" * 80)
cuentas_clientes = CuentaCorrienteCliente.objects.filter(empresa=empresa)
print(f"Total cuentas corrientes clientes: {cuentas_clientes.count()}")
for cuenta in cuentas_clientes[:5]:
    print(f"  - Cliente: {cuenta.cliente.nombre}")
    print(f"    Saldo: ${cuenta.saldo:,.0f}")
    print(f"    Estado: {cuenta.estado}")

# Verificar Movimientos de Cuenta Corriente Cliente
print("\n" + "=" * 80)
print("MOVIMIENTOS DE CUENTA CORRIENTE CLIENTE")
print("=" * 80)
movimientos = MovimientoCuentaCorrienteCliente.objects.filter(empresa=empresa)
print(f"Total movimientos: {movimientos.count()}")
for mov in movimientos[:5]:
    print(f"  - Fecha: {mov.fecha}")
    print(f"    Cliente: {mov.cliente.nombre if mov.cliente else 'Sin cliente'}")
    print(f"    Tipo: {mov.tipo_movimiento}")
    print(f"    Monto: ${mov.monto:,.0f}")
    print(f"    Estado: {mov.estado_pago}")
    print()

# Verificar Proveedores
print("\n" + "=" * 80)
print("PROVEEDORES")
print("=" * 80)
proveedores = Proveedor.objects.filter(empresa=empresa)
print(f"Total proveedores: {proveedores.count()}")
for proveedor in proveedores[:5]:
    print(f"  - {proveedor.nombre} (RUT: {proveedor.rut})")

# Verificar Cuentas Corrientes de Proveedores
print("\n" + "=" * 80)
print("CUENTAS CORRIENTES DE PROVEEDORES")
print("=" * 80)
cuentas_proveedores = CuentaCorrienteProveedor.objects.filter(empresa=empresa)
print(f"Total cuentas corrientes proveedores: {cuentas_proveedores.count()}")
for cuenta in cuentas_proveedores[:5]:
    print(f"  - Proveedor: {cuenta.proveedor.nombre}")
    print(f"    Saldo: ${cuenta.saldo:,.0f}")
    print(f"    Estado: {cuenta.estado}")

print("\n" + "=" * 80)
print("FIN DEL REPORTE")
print("=" * 80)
