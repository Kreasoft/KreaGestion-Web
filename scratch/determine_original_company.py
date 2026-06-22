import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from clientes.models import Cliente
from ventas.models import Venta
from empresas.models import Empresa
from usuarios.models import PerfilUsuario

print("=== EMPRESAS ===")
for emp in Empresa.objects.all():
    print(f"ID: {emp.id} | Nombre: {emp.nombre}")

# Obtener fecha de creación o ID de las empresas
emp1 = Empresa.objects.get(id=1)
emp2 = Empresa.objects.get(id=2)

print("\n=== PERFILES DE USUARIOS ===")
user_company_map = {}
for p in PerfilUsuario.objects.all():
    user_company_map[p.usuario_id] = p.empresa_id
    print(f"User ID: {p.usuario_id} | Username: {p.usuario.username} | Empresa: {p.empresa_id} ({p.empresa.nombre})")

print("\n=== ANALIZANDO CLIENTES ===")
clientes_emp1 = 0
clientes_emp2 = 0
indeterminados = 0

# Ver quién creó a los clientes
emp2_creados = []
for c in Cliente.objects.all():
    # 1. Por ventas asociadas
    ventas = Venta.objects.filter(cliente=c)
    venta_companies = set(ventas.values_list('empresa_id', flat=True))
    
    # 2. Por creador
    creador_empresa = user_company_map.get(c.creado_por_id) if c.creado_por_id else None
    
    # Decidir empresa original
    original_emp_id = None
    reason = ""
    
    if len(venta_companies) == 1:
        original_emp_id = list(venta_companies)[0]
        reason = "ventas"
    elif len(venta_companies) > 1:
        original_emp_id = 1 # fallback
        reason = "ventas multiples (usando fallback 1)"
    elif creador_empresa:
        original_emp_id = creador_empresa
        reason = "creado por usuario"
    else:
        # Si no hay ventas ni creador, como la empresa 2 es nueva, 
        # asumimos que los clientes antiguos (con IDs bajos) pertenecen a la empresa 1.
        # ¿Cuál es el ID máximo de cliente de la primera empresa? 
        # Vamos a ver cuántos clientes hay y dónde cae el corte
        if c.id < 7000: 
            original_emp_id = 1
            reason = "id bajo (< 7000)"
        else:
            original_emp_id = 2
            reason = "id alto (>= 7000)"

    if original_emp_id == 1:
        clientes_emp1 += 1
    elif original_emp_id == 2:
        clientes_emp2 += 1
        emp2_creados.append(c)
        print(f"Propuesto para Empresa 2: ID: {c.id} | Nombre: {c.nombre} | RUT: {c.rut} | Motivo: {reason}")
    else:
        indeterminados += 1

print(f"\nResumen de propuesta:")
print(f"Clientes propuestos para Empresa 1: {clientes_emp1}")
print(f"Clientes propuestos para Empresa 2: {clientes_emp2}")
print(f"Indeterminados: {indeterminados}")
