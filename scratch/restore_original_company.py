import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from clientes.models import Cliente
from ventas.models import Venta
from empresas.models import Empresa
from usuarios.models import PerfilUsuario

# 1. Analizar usuarios
user_company_map = {}
for p in PerfilUsuario.objects.all():
    user_company_map[p.usuario_id] = p.empresa_id

# 2. Encontrar clientes y restaurar
print("Restaurando clientes...")
moved_to_1 = 0
moved_to_2 = 0

for c in Cliente.objects.all():
    # 1. Por ventas asociadas
    ventas = Venta.objects.filter(cliente=c)
    venta_companies = set(ventas.values_list('empresa_id', flat=True))
    
    # 2. Por creador
    creador_empresa = user_company_map.get(c.creado_por_id) if c.creado_por_id else None
    
    # Decidir
    original_emp_id = None
    if len(venta_companies) == 1:
        original_emp_id = list(venta_companies)[0]
    elif len(venta_companies) > 1:
        # Si tiene ventas en múltiples empresas, usar la de la mayoría de ventas
        # o fallback a 1
        original_emp_id = 1
    elif creador_empresa:
        original_emp_id = creador_empresa
    else:
        # Fallback por ID
        if c.id < 7000:
            original_emp_id = 1
        else:
            original_emp_id = 2

    # Aplicar cambio si es diferente
    if c.empresa_id != original_emp_id:
        c.empresa_id = original_emp_id
        c.save()
        if original_emp_id == 1:
            moved_to_1 += 1
        else:
            moved_to_2 += 1

print(f"Restauración completa:")
print(f"  Clientes movidos a Empresa 1: {moved_to_1}")
print(f"  Clientes movidos a Empresa 2: {moved_to_2}")

# Validar que ahora existan clientes en la Empresa 1
count_1 = Cliente.objects.filter(empresa_id=1).count()
count_2 = Cliente.objects.filter(empresa_id=2).count()
print(f"Estado final:")
print(f"  Total clientes Empresa 1: {count_1}")
print(f"  Total clientes Empresa 2: {count_2}")
