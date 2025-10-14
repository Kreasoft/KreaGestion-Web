#!/usr/bin/env python
"""
Script de prueba para verificar que tipo_documento_planeado se guarda correctamente
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta

def test_tipo_documento_planeado():
    """Verificar que tipo_documento_planeado se está guardando correctamente"""

    # Buscar algunos tickets recientes
    tickets_recientes = Venta.objects.filter(
        tipo_documento='vale',
        estado='borrador'
    ).order_by('-fecha_creacion')[:5]

    print("=== TICKETS RECIENTES ===")
    for ticket in tickets_recientes:
        print(f"Ticket #{ticket.numero_venta}:")
        print(f"  Tipo documento actual: {ticket.tipo_documento}")
        print(f"  Tipo documento planeado: {ticket.tipo_documento_planeado}")
        print(f"  Cliente: {ticket.cliente.nombre if ticket.cliente else 'Sin cliente'}")
        print(f"  Fecha: {ticket.fecha_creacion}")
        print("---")

if __name__ == "__main__":
    test_tipo_documento_planeado()



