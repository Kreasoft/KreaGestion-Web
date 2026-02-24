"""
Script para comparar XML de guía generado vs KreaDTE-Cloud
"""
import os
import django
import base64

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService
from empresas.models import Empresa

empresa = Empresa.objects.first()
guia = DocumentoTributarioElectronico.objects.filter(tipo_dte='52', folio=98).first()

if guia and guia.xml_dte:
    print("=" * 80)
    print("XML GENERADO (nuestro)")
    print("=" * 80)
    print(guia.xml_dte[:2000])
    print("\n... (truncado) ...\n")
    
    # Simular lo que enviamos a DTEBox
    dtebox = DTEBoxService(empresa)
    xml_preparado, error = dtebox._limpiar_y_preparar_xml(guia.xml_dte, '52')
    
    if xml_preparado:
        print("=" * 80)
        print("XML PREPARADO PARA DTEBox (después de limpiar)")
        print("=" * 80)
        print(xml_preparado[:2000])
        print("\n... (truncado) ...\n")
        
        # Base64 que enviamos
        xml_bytes = xml_preparado.encode('ISO-8859-1', errors='replace')
        xml_b64 = base64.b64encode(xml_bytes).decode('utf-8')
        print("=" * 80)
        print("BASE64 ENVIADO (primeros 500 chars)")
        print("=" * 80)
        print(xml_b64[:500])
    else:
        print(f"ERROR preparando XML: {error}")
else:
    print("No hay XML para guía 98")
