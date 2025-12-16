#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para reenviar un documento a DTEBox
Factura tipo 33, folio 3233 - Ambiente Producción
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
from facturacion_electronica.models import DocumentoTributarioElectronico

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def print_header(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

def reenviar_documento():
    """
    Reenvía un documento a DTEBox
    """
    print_header("REENVIAR DOCUMENTO A DTEBox")
    
    # Datos del documento
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
        
        # Buscar el DTE en la base de datos
        print(f"\nBuscando DTE en la base de datos...")
        try:
            dte = DocumentoTributarioElectronico.objects.filter(
                tipo_dte=tipo_dte,
                folio=folio,
                empresa=empresa
            ).first()
            
            if not dte:
                print(f"⚠️ No se encontró el DTE en la base de datos")
                print(f"   Tipo: {tipo_dte}, Folio: {folio}")
                print(f"\nOpciones:")
                print(f"1. Proporcionar el XML completo del documento manualmente")
                print(f"2. Crear el DTE primero y luego reenviarlo")
                return
            
            print(f"✅ DTE encontrado:")
            print(f"   ID: {dte.id}")
            print(f"   Fecha emisión: {dte.fecha_emision}")
            print(f"   Receptor: {dte.razon_social_receptor}")
            print(f"   Monto total: ${dte.monto_total:,.0f}")
            
            # Obtener XML completo del DTE
            if not dte.xml_firmado:
                print(f"❌ El DTE no tiene XML firmado")
                return
            
            xml_completo = dte.xml_firmado
            print(f"✅ XML encontrado ({len(xml_completo)} caracteres)")
            
            # Verificar que tenga TED timbrado
            if '<TED' in xml_completo and '<DD>' in xml_completo:
                # Verificar que el DD tenga contenido (está timbrado)
                import re
                dd_match = re.search(r'<DD>(.*?)</DD>', xml_completo, re.DOTALL)
                if dd_match and dd_match.group(1).strip():
                    print(f"✅ Documento tiene TED timbrado")
                else:
                    print(f"⚠️ El documento no parece tener TED timbrado")
                    print(f"   Se intentará reenviar de todas formas")
            else:
                print(f"⚠️ No se encontró elemento TED en el XML")
                print(f"   Se intentará reenviar de todas formas")
        
        except Exception as e:
            print(f"❌ Error al buscar DTE: {str(e)}")
            return
        
        # Inicializar servicio
        print("\nInicializando servicio DTEBoxService...")
        servicio = DTEBoxService(empresa)
        
        # Reenviar documento
        print("\nReenviando documento usando el método reenviar_documento...")
        print("=" * 80)
        
        resultado = servicio.reenviar_documento(xml_completo)
        
        print()
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        
        if resultado['success']:
            print("✅ Documento reenviado exitosamente!")
            if resultado['message']:
                print(f"Mensaje: {resultado['message']}")
            print("\nEl documento ha sido reenviado a DTEBox correctamente.")
        else:
            print("❌ Error al reenviar documento")
            print(f"Error: {resultado['error']}")
        
        print("=" * 80)
    
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reenviar_documento()

