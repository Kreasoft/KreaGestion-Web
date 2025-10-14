#!/usr/bin/env python
"""
Script de prueba para verificar que el formato correcto de factura se esté usando
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta

def test_formato_factura():
    """Verificar qué formato se está usando para las facturas"""

    # Buscar facturas recientes
    facturas_recientes = Venta.objects.filter(
        tipo_documento='factura'
    ).order_by('-fecha_creacion')[:3]

    print("=== FACTURAS RECIENTES ===")
    for factura in facturas_recientes:
        print(f"Factura #{factura.numero_venta}:")
        print(f"  Empresa: {factura.empresa.nombre}")
        print(f"  Tiene FE activa: {factura.empresa.facturacion_electronica}")
        print(f"  Fecha: {factura.fecha_creacion}")
        print("---")

if __name__ == "__main__":
    test_formato_factura()



