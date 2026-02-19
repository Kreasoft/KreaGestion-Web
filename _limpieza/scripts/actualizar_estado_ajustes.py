"""
Script para actualizar el estado de los ajustes existentes a 'confirmado'
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from inventario.models import Inventario

# Actualizar ajustes sin estado o con estado pendiente
ajustes = Inventario.objects.filter(tipo_movimiento='AJUSTE')
total = ajustes.count()
actualizados = ajustes.update(estado='confirmado')

print(f"Total de ajustes encontrados: {total}")
print(f"Ajustes actualizados a 'confirmado': {actualizados}")
print("✅ Proceso completado")
