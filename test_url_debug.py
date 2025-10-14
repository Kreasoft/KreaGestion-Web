#!/usr/bin/env python
import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth.models import User
from tesoreria.views import cuenta_corriente_cliente_list

# Crear request factory
rf = RequestFactory()
user = User.objects.filter(is_superuser=True).first()

print(f"✓ Usuario: {user.username}")

# Crear request
request = rf.get('/tesoreria/cuenta-corriente-clientes/')
request.user = user
request.session = {}

print("\n=== LLAMANDO A LA VISTA DIRECTAMENTE ===")
try:
    response = cuenta_corriente_cliente_list(request)
    print(f"✓ Status: {response.status_code}")
    print(f"✓ Vista ejecutada correctamente")
except Exception as e:
    print(f"\n❌ ERROR EN LA VISTA:")
    print(f"Tipo: {type(e).__name__}")
    print(f"Mensaje: {str(e)}")
    print(f"\nTraceback completo:")
    traceback.print_exc()
