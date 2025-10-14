#!/usr/bin/env python
"""
Test final para verificar que la vista funciona correctamente
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

print("="*70)
print("TEST FINAL - CUENTA CORRIENTE CLIENTES")
print("="*70)

# 1. Verificar empresas
from empresas.models import Empresa
print("\n1. EMPRESAS DISPONIBLES:")
empresas = Empresa.objects.all().order_by('id')
for emp in empresas:
    print(f"   ID {emp.id}: '{emp.nombre}' - RUT: {emp.rut}")

# 2. Verificar cuál se seleccionaría
print("\n2. EMPRESA QUE SE SELECCIONARÍA:")
empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
if empresa:
    print(f"   ✓ Kreasoft encontrado: {empresa.nombre} (ID: {empresa.id})")
else:
    empresa = Empresa.objects.exclude(nombre='').first()
    if empresa:
        print(f"   ✓ Primera empresa con nombre: {empresa.nombre} (ID: {empresa.id})")
    else:
        empresa = Empresa.objects.first()
        print(f"   ⚠ Primera empresa: '{empresa.nombre}' (ID: {empresa.id})")

# 3. Verificar movimientos
from tesoreria.models import MovimientoCuentaCorrienteCliente
print(f"\n3. MOVIMIENTOS DE LA EMPRESA {empresa.nombre} (ID: {empresa.id}):")
movs = MovimientoCuentaCorrienteCliente.objects.filter(
    cuenta_corriente__empresa=empresa,
    tipo_movimiento='debe'
).select_related('cuenta_corriente__cliente', 'venta')

print(f"   Total movimientos DEBE: {movs.count()}")

if movs.count() > 0:
    print("\n   Primeros 3 movimientos:")
    for i, m in enumerate(movs[:3], 1):
        print(f"   {i}. ID: {m.id}")
        print(f"      Cliente: {m.cuenta_corriente.cliente.nombre}")
        print(f"      Factura: {m.venta.numero_venta if m.venta else 'N/A'}")
        print(f"      Monto: ${m.monto:,.0f}")
        print()

# 4. Simular la vista
print("4. SIMULANDO VISTA:")
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore

rf = RequestFactory()
user = User.objects.filter(is_superuser=True).first()

if not user:
    print("   ❌ No hay usuario superusuario")
else:
    print(f"   Usuario: {user.username}")
    
    # Crear request con sesión
    request = rf.get('/tesoreria/cuenta-corriente-clientes/')
    request.user = user
    request.session = SessionStore()
    
    # Simular decorador
    from tesoreria.decorators import requiere_empresa
    from tesoreria.views import cuenta_corriente_cliente_list
    
    print("\n   Ejecutando decorador...")
    try:
        # El decorador debería asignar request.empresa
        if user.is_superuser:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
                if not empresa:
                    empresa = Empresa.objects.exclude(nombre='').first()
                if not empresa:
                    empresa = Empresa.objects.first()
                request.empresa = empresa
                request.session['empresa_activa'] = empresa.id
        
        print(f"   ✓ Empresa asignada: {request.empresa.nombre} (ID: {request.empresa.id})")
        
        # Ejecutar vista
        print("\n   Ejecutando vista...")
        response = cuenta_corriente_cliente_list(request)
        print(f"   ✓ Vista ejecutada - Status: {response.status_code}")
        
        if response.status_code == 200:
            print("\n   ✓✓✓ TODO FUNCIONA CORRECTAMENTE ✓✓✓")
        else:
            print(f"\n   ⚠ Status code inesperado: {response.status_code}")
            
    except Exception as e:
        print(f"\n   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*70)
print("FIN DEL TEST")
print("="*70)
