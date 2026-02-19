#!/usr/bin/env python
"""
Script de ayuda para activar y verificar Facturación Electrónica
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from django.utils import timezone

print("=" * 70)
print("DIAGNOSTICO DE FACTURACION ELECTRONICA")
print("=" * 70)

# Obtener todas las empresas
empresas = Empresa.objects.all()
print(f"\nTotal de empresas: {empresas.count()}")

for empresa in empresas:
    print(f"\n{'=' * 70}")
    print(f"EMPRESA: {empresa.nombre}")
    print(f"   RUT: {empresa.rut}")
    print(f"   {'=' * 66}")
    print(f"   FE Activada: {'SI' if empresa.facturacion_electronica else 'NO'}")
    print(f"   Ambiente SII: {empresa.get_ambiente_sii_display()}")
    print(f"   Certificado: {'Cargado' if empresa.certificado_digital else 'No cargado'}")
    print(f"   Razon Social SII: {empresa.razon_social_sii or 'Usara: ' + empresa.razon_social}")
    print(f"   Giro SII: {empresa.giro_sii or 'Usara: ' + empresa.giro}")
    print(f"   Direccion: {empresa.direccion}")
    print(f"   Comuna: {empresa.comuna}")
    print(f"   Ciudad: {empresa.ciudad}")
    print(f"   Codigo Act. Economica: {empresa.codigo_actividad_economica or 'NO CONFIGURADO'}")
    print(f"   Resolucion: {empresa.resolucion_numero or 'No registrada'}")
    
    # Contar CAFs
    cafs_count = empresa.archivos_caf.count()
    cafs_activos = empresa.archivos_caf.filter(estado='activo').count()
    print(f"   CAFs cargados: {cafs_count} (activos: {cafs_activos})")

print(f"\n{'=' * 70}")
print("OPCIONES:")
print("=" * 70)

# Activar FE en primera empresa
if empresas.exists():
    empresa = empresas.first()
    
    if not empresa.facturacion_electronica:
        print("\n¿Deseas activar FE en la primera empresa? (s/n): ", end='')
        respuesta = input().strip().lower()
        
        if respuesta == 's':
            empresa.facturacion_electronica = True
            empresa.ambiente_sii = 'certificacion'
            
            # Usar datos existentes
            if not empresa.codigo_actividad_economica:
                empresa.codigo_actividad_economica = '620200'  # Servicios informáticos por defecto
            
            if not empresa.resolucion_numero:
                empresa.resolucion_numero = 80
                empresa.resolucion_fecha = timezone.now().date()
            
            empresa.save()
            
            print(f"\nOK - Facturacion Electronica activada para: {empresa.nombre}")
            print(f"   - Ambiente: Certificacion (Pruebas)")
            print(f"   - Codigo Actividad: {empresa.codigo_actividad_economica}")
            print(f"   - Resolucion: No {empresa.resolucion_numero}")
            print(f"\nAhora puedes cargar archivos CAF en:")
            print(f"   http://127.0.0.1:8000/facturacion-electronica/caf/nuevo/")
        else:
            print("\nOperacion cancelada")
    else:
        print(f"\nLa empresa '{empresa.nombre}' ya tiene FE activada")
        print(f"\nURLs disponibles:")
        print(f"   - Configurar FE: http://127.0.0.1:8000/empresas/editar-empresa-activa/")
        print(f"   - Cargar CAF: http://127.0.0.1:8000/facturacion-electronica/caf/nuevo/")
        print(f"   - Lista CAF: http://127.0.0.1:8000/facturacion-electronica/caf/")

print(f"\n{'=' * 70}\n")

