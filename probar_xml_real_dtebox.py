#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para probar DTEBox con un XML real de DTE
"""
import os
import sys
import django
import base64
import xml.etree.ElementTree as ET

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from facturacion_electronica.dtebox_service import DTEBoxService


def probar_xml_desde_archivo(archivo_xml):
    """
    Prueba DTEBox con un XML desde un archivo
    """
    print("=" * 80)
    print("PRUEBA DTEBox CON XML REAL DESDE ARCHIVO")
    print("=" * 80)
    print()
    
    try:
        # Leer XML del archivo
        with open(archivo_xml, 'r', encoding='ISO-8859-1') as f:
            xml_content = f.read()
        
        print(f"[OK] XML leído desde: {archivo_xml}")
        print(f"Tamaño: {len(xml_content)} caracteres")
        print()
        
        # Mostrar primeros caracteres
        print("Primeros 500 caracteres del XML:")
        print("-" * 80)
        print(xml_content[:500])
        if len(xml_content) > 500:
            print("...")
        print("-" * 80)
        print()
        
        # Probar con el servicio
        probar_xml_con_servicio(xml_content)
        
    except FileNotFoundError:
        print(f"[ERROR] No se encontró el archivo: {archivo_xml}")
    except Exception as e:
        print(f"[ERROR] Error al leer archivo: {str(e)}")
        import traceback
        traceback.print_exc()


def probar_xml_desde_string(xml_string):
    """
    Prueba DTEBox con un XML desde un string
    """
    print("=" * 80)
    print("PRUEBA DTEBox CON XML REAL DESDE STRING")
    print("=" * 80)
    print()
    
    print(f"Tamaño del XML: {len(xml_string)} caracteres")
    print()
    
    # Mostrar primeros caracteres
    print("Primeros 500 caracteres del XML:")
    print("-" * 80)
    print(xml_string[:500])
    if len(xml_string) > 500:
        print("...")
    print("-" * 80)
    print()
    
    # Probar con el servicio
    probar_xml_con_servicio(xml_string)


def probar_xml_con_servicio(xml_content):
    """
    Prueba el XML con el servicio DTEBoxService
    """
    try:
        # Buscar empresa con DTEBox habilitado o usar la primera
        empresa = Empresa.objects.filter(dtebox_habilitado=True).first()
        
        if not empresa:
            empresa = Empresa.objects.first()
            if not empresa:
                print("[ERROR] No se encontró ninguna empresa")
                return
            
            # Configurar DTEBox para prueba
            empresa.dtebox_habilitado = True
            empresa.dtebox_url = "http://200.6.118.43/api/Core.svc/Core"
            empresa.dtebox_auth_key = "0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0"
            empresa.dtebox_ambiente = "T"
            empresa.dtebox_pdf417_columns = 5
            empresa.dtebox_pdf417_level = 2
            empresa.dtebox_pdf417_type = 1
        
        print(f"Empresa: {empresa.nombre}")
        print(f"RUT: {empresa.rut}")
        print(f"URL DTEBox: {empresa.dtebox_url}")
        print(f"Ambiente: {empresa.dtebox_ambiente}")
        print()
        
        # Verificar datos de resolución
        if empresa.resolucion_numero and empresa.resolucion_fecha:
            print(f"Resolución: N° {empresa.resolucion_numero} del {empresa.resolucion_fecha.strftime('%d-%m-%Y')}")
        else:
            print("[ADVERTENCIA] Datos de resolución no configurados")
            print("Configurando datos de resolución...")
            from datetime import date
            empresa.resolucion_numero = 80
            empresa.resolucion_fecha = date(2014, 8, 22)
            empresa.save()
            print(f"Resolución configurada: N° {empresa.resolucion_numero} del {empresa.resolucion_fecha.strftime('%d-%m-%Y')}")
        print()
        
        # Inicializar servicio
        print("Inicializando servicio DTEBoxService...")
        dtebox_service = DTEBoxService(empresa)
        print()
        
        # Timbrar DTE
        print("Enviando XML real a DTEBox para obtener TED...")
        print("=" * 80)
        
        resultado = dtebox_service.timbrar_dte(xml_content)
        
        print()
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        
        if resultado['success']:
            print("[OK] DTE timbrado exitosamente!")
            print(f"TED recibido: {len(resultado['ted'])} caracteres")
            print()
            print("TED completo:")
            print("-" * 80)
            print(resultado['ted'])
            print("-" * 80)
        else:
            print("[ERROR] Error al timbrar DTE")
            print(f"Error: {resultado['error']}")
            print()
            print("Revisa los archivos de debug en:")
            print("  logs/dtebox_debug/dtebox_request_*.xml")
            print("  logs/dtebox_debug/dtebox_response_*.txt")
        
        print("=" * 80)
        
    except ValueError as e:
        print(f"[ERROR] Error de configuración: {str(e)}")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print()
    print("=" * 80)
    print("PRUEBA DTEBox CON XML REAL")
    print("=" * 80)
    print()
    
    # Opción 1: Desde archivo
    if len(sys.argv) > 1:
        archivo_xml = sys.argv[1]
        probar_xml_desde_archivo(archivo_xml)
    else:
        print("OPCIONES DE USO:")
        print()
        print("1. Desde archivo:")
        print("   python probar_xml_real_dtebox.py ruta/al/archivo.xml")
        print()
        print("2. Desde string (editar el script y pegar el XML):")
        print("   Editar la variable XML_REAL en el script")
        print()
        print("=" * 80)
        print()
        
        # Si quieres probar directamente, puedes pegar el XML aquí:
        XML_REAL = """
        <!-- Pega aquí el XML real del DTE -->
        """
        
        if XML_REAL.strip() and not XML_REAL.strip().startswith("<!--"):
            probar_xml_desde_string(XML_REAL.strip())
        else:
            print("Por favor, proporciona el XML real de una de estas formas:")
            print("1. Ejecuta: python probar_xml_real_dtebox.py ruta/al/archivo.xml")
            print("2. Edita este script y pega el XML en la variable XML_REAL")




