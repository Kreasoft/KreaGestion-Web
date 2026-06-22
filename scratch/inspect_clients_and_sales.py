import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from clientes.models import Cliente
from ventas.models import Venta
from empresas.models import Empresa

print("=== EMPRESAS ===")
for emp in Empresa.objects.all():
    print(f"ID: {emp.id} | Nombre: {emp.nombre}")

print("\n=== CLIENTES Y SUS ASOCIACIONES A VENTAS ===")
all_clientes = Cliente.objects.all()
print(f"Total clientes: {all_clientes.count()}")

clients_with_sales = 0
clients_without_sales = 0

for c in all_clientes:
    # Buscar ventas asociadas a este cliente
    ventas = Venta.objects.filter(cliente=c)
    venta_companies = set(ventas.values_list('empresa_id', flat=True))
    
    print(f"Cliente ID: {c.id} | Nombre: {c.nombre} | RUT: {c.rut} | Empresa Actual: {c.empresa_id} ({c.empresa.nombre})")
    if venta_companies:
        clients_with_sales += 1
        print(f"  -> Ventas encontradas en empresas: {list(venta_companies)}")
    else:
        clients_without_sales += 1
        print(f"  -> Sin ventas asociadas")

print(f"\nResumen: Con ventas: {clients_with_sales} | Sin ventas: {clients_without_sales}")
