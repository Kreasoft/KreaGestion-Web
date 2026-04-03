import os
import django
import sys

# Setup Django
sys.path.append('c:/PROJECTOS-WEB/GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta, Vendedor
from clientes.models import Cliente

print("--- RECENT SALES DEBUG ---")
sales = Venta.objects.order_by('-id')[:20]
for s in sales:
    cliente_str = f"ID: {s.cliente_id} ({s.cliente.nombre if s.cliente else 'NULL'})"
    print(f"Venta ID: {s.id} | Numero: {s.numero_venta} | Cliente: {cliente_str} | Obs: {s.observaciones[:50]}...")

print("\n--- VENDORS DEBUG ---")
vendedores = Vendedor.objects.all()
for v in vendedores:
    print(f"Vendedor: {v.id} | Codigo: {v.codigo} | Nombre: {v.nombre}")

print("\n--- CLIENTS SUMMARY ---")
print(f"Total Clientes: {Cliente.objects.count()}")
print(f"Clientes sin vendedor: {Cliente.objects.filter(vendedor__isnull=True).count()}")
