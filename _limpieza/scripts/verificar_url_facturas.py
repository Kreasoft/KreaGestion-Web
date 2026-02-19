import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.urls import reverse

try:
    url = reverse('compras:facturas_recibidas_sii')
    print(f"✓ URL configurada correctamente: {url}")
except Exception as e:
    print(f"✗ Error al obtener URL: {e}")
