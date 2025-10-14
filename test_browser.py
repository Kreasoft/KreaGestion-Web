#!/usr/bin/env python
"""
Script para probar la vista con una sesión completa
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session

# Crear cliente con sesión
client = Client()

# Login
user = User.objects.filter(is_superuser=True).first()
print(f"Usuario: {user.username}")

# Force login crea la sesión automáticamente
client.force_login(user)

# Verificar sesión
session = client.session
print(f"Session key: {session.session_key}")
print(f"Session data: {dict(session)}")

# Hacer request
print("\n=== REQUEST ===")
try:
    response = client.get('/tesoreria/cuenta-corriente-clientes/', follow=True)
    print(f"Status: {response.status_code}")
    print(f"URL final: {response.request['PATH_INFO']}")
    
    if response.status_code == 200:
        print("\n✓✓✓ ÉXITO ✓✓✓")
        
        # Ver contexto
        if hasattr(response, 'context') and response.context:
            empresa = response.context.get('empresa')
            page_obj = response.context.get('page_obj')
            
            print(f"\nEmpresa: {empresa.nombre if empresa else 'None'} (ID: {empresa.id if empresa else 'N/A'})")
            print(f"Items en página: {len(page_obj) if page_obj else 0}")
            
            if page_obj and len(page_obj) > 0:
                print("\n=== PRIMEROS 3 ITEMS ===")
                for i, item in enumerate(list(page_obj)[:3], 1):
                    print(f"\n{i}. Movimiento ID: {item.id}")
                    print(f"   Cliente: {item.cuenta_corriente.cliente.nombre}")
                    print(f"   Monto: ${item.monto}")
            else:
                print("\n⚠ NO HAY ITEMS EN LA PÁGINA")
        else:
            print("\n⚠ No hay contexto en la respuesta")
    else:
        print(f"\n❌ Error: {response.status_code}")
        print(f"Content: {response.content[:500]}")
        
except Exception as e:
    print(f"\n❌ EXCEPCIÓN: {e}")
    import traceback
    traceback.print_exc()
