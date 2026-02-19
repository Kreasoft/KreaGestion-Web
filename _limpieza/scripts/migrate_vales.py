import os
import django
import sys

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta

def migrate():
    print("Migrando ventas de 'vale' a 'ticket'...")
    # Solo migramos las que tienen facturado=False o estaban pensadas como tickets
    # En realidad, todas las que son 'vale' actualmente son tickets facturables
    count = Venta.objects.filter(tipo_documento='vale').update(tipo_documento='ticket')
    print(f"Se actualizaron {count} registros.")

if __name__ == "__main__":
    migrate()
