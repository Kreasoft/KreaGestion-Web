import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta

# Obtener último ticket
ticket = Venta.objects.filter(tipo_documento='vale').order_by('-id').first()

if ticket:
    print(f"Ticket: {ticket.numero_venta}")
    print(f"tipo_documento: {ticket.tipo_documento}")
    print(f"tipo_documento_planeado: '{ticket.tipo_documento_planeado}'")
else:
    print("No hay tickets")
