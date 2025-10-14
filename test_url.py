#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Crear cliente de prueba
client = Client()

# Obtener usuario admin
user = User.objects.filter(is_superuser=True).first()
if not user:
    print("❌ No hay usuario superusuario")
    exit(1)

print(f"✓ Usuario: {user.username}")

# Login
client.force_login(user)
print("✓ Login exitoso")

# Hacer request a la URL
print("\n=== HACIENDO REQUEST A /tesoreria/cuenta-corriente-clientes/ ===")
response = client.get('/tesoreria/cuenta-corriente-clientes/')

print(f"\nStatus Code: {response.status_code}")
print(f"Template usado: {response.templates[0].name if response.templates else 'N/A'}")

if response.status_code == 200:
    # Verificar contexto
    context = response.context
    print(f"\n=== CONTEXTO ===")
    print(f"Empresa: {context.get('empresa')}")
    print(f"Page obj: {context.get('page_obj')}")
    
    page_obj = context.get('page_obj')
    if page_obj:
        print(f"\nTotal items en page_obj: {len(page_obj)}")
        print(f"Tiene items: {page_obj.object_list if hasattr(page_obj, 'object_list') else 'N/A'}")
        
        if len(page_obj) > 0:
            print("\n✓✓✓ HAY DATOS EN LA PÁGINA ✓✓✓")
            for i, item in enumerate(page_obj[:3], 1):
                print(f"\n  Item {i}:")
                print(f"    ID: {item.id}")
                print(f"    Cliente: {item.cuenta_corriente.cliente.nombre}")
                if hasattr(item, 'venta') and item.venta:
                    print(f"    Factura: {item.venta.numero_venta}")
                print(f"    Monto: ${item.monto}")
        else:
            print("\n❌ NO HAY DATOS EN LA PÁGINA")
    
    stats = context.get('stats')
    if stats:
        print(f"\n=== ESTADÍSTICAS ===")
        print(f"Total documentos: {stats.get('total_documentos')}")
        print(f"Total pendiente: ${stats.get('total_pendiente'):,}")
        print(f"Total pagado: ${stats.get('total_pagado'):,}")
        print(f"Total parcial: ${stats.get('total_parcial'):,}")
else:
    print(f"\n❌ ERROR: Status code {response.status_code}")
    if response.status_code == 302:
        print(f"Redirigiendo a: {response.url}")
