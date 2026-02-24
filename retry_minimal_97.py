
import os
import django
import sys
import base64

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.dtebox_service import DTEBoxService

def retry_97():
    print("--- REINTENTANDO FOLIO 97 CON SCHEMA MINIMAL ---")
    dte = DocumentoTributarioElectronico.objects.filter(folio=97, tipo_dte='52').first()
    if not dte:
        print("No se encontró el DTE 97")
        return
    
    generator = DTEXMLGenerator(dte.empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
    xml_sin_firmar = generator.generar_xml()
    
    # Guardar para debug
    with open("debug_folio_97_minimal.xml", "w") as f:
        f.write(xml_sin_firmar)
    print("XML generado en debug_folio_97_minimal.xml")
    
    service = DTEBoxService(dte.empresa)
    res = service.timbrar_dte(xml_sin_firmar, tipo_dte='52')
    
    if res['success']:
        print("[SUCCESS] DTE Enviado y Timbrado!")
        print(f"TED: {res['ted'][:100]}...")
    else:
        print(f"[FAIL] Error: {res['error']}")

if __name__ == "__main__":
    retry_97()
