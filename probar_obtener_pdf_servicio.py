#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para probar el método obtener_pdf del servicio DTEBoxService
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from facturacion_electronica.dtebox_service import DTEBoxService

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def print_header(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

def probar_obtener_pdf():
    """
    Prueba el método obtener_pdf del servicio DTEBoxService
    """
    print_header("PROBAR MÉTODO obtener_pdf DEL SERVICIO DTEBoxService")
    
    # Datos de la factura
    tipo_dte = 33  # Factura
    folio = 3233
    ambiente = "P"  # Producción
    
    print(f"\nDatos del documento:")
    print(f"  Tipo DTE: {tipo_dte} (Factura)")
    print(f"  Folio: {folio}")
    print(f"  Ambiente: {ambiente} (Producción)")
    
    try:
        # Obtener empresa
        empresa = Empresa.objects.filter(dtebox_habilitado=True).first()
        
        if not empresa:
            empresa = Empresa.objects.first()
            if not empresa:
                print("\n[ERROR] No se encontró ninguna empresa")
                return
        
        # Configurar DTEBox si no está configurado
        if not empresa.dtebox_habilitado or not empresa.dtebox_url or not empresa.dtebox_auth_key:
            print("\n[INFO] Configurando DTEBox con datos de acceso...")
            empresa.dtebox_habilitado = True
            empresa.dtebox_url = "http://200.6.118.43/api/Core.svc/Core"
            empresa.dtebox_auth_key = "0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0"
            empresa.dtebox_ambiente = ambiente
            empresa.save()
        
        print(f"\nEmpresa: {empresa.nombre}")
        print(f"RUT: {empresa.rut}")
        print(f"URL DTEBox: {empresa.dtebox_url}")
        print(f"Auth Key: {empresa.dtebox_auth_key[:20]}...")
        print(f"Ambiente: {empresa.dtebox_ambiente}")
        
        # Inicializar servicio
        print("\nInicializando servicio DTEBoxService...")
        servicio = DTEBoxService(empresa)
        
        # Obtener PDF
        print("\nObteniendo PDF usando el método obtener_pdf...")
        print("=" * 80)
        
        resultado = servicio.obtener_pdf(tipo_dte, folio)
        
        print()
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        
        if resultado['success']:
            print("✅ PDF obtenido exitosamente!")
            print(f"Tamaño: {len(resultado['pdf'])} bytes ({len(resultado['pdf'])/1024:.2f} KB)")
            
            # Guardar PDF
            nombre_archivo = f"factura_{tipo_dte}_{folio}_servicio.pdf"
            with open(nombre_archivo, 'wb') as f:
                f.write(resultado['pdf'])
            
            print(f"📄 PDF guardado como: {nombre_archivo}")
            print("\nEl método obtener_pdf funciona correctamente y puede ser usado desde Django.")
        else:
            print("❌ Error al obtener PDF")
            print(f"Error: {resultado['error']}")
        
        print("=" * 80)
    
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    probar_obtener_pdf()




