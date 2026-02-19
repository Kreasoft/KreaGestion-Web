import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
sys.path.append(os.getcwd())
django.setup()

from ventas.models import Venta

try:
    t = Venta.objects.get(id=204)
    print(f"Ticket 44 (ID 204) estado actual: {t.tipo_documento_planeado}")
    t.tipo_documento_planeado = 'vale'
    # Forzar update_fields para evitar overrides raros si los hubiera
    t.save(update_fields=['tipo_documento_planeado'])
    print("✅ Ticket 44 (ID 204) corregido a planeado='vale'.")
    print("Ahora puede ser procesado en caja como Vale.")
except Venta.DoesNotExist:
    print("Ticket 44 (ID 204) no encontrado.")
except Exception as e:
    print(f"Error: {e}")
