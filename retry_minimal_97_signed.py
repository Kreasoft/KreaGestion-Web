
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
from facturacion_electronica.dte_service import DTEService

def retry_97_signed():
    print("--- REINTENTANDO FOLIO 97 CON SCHEMA MINIMAL Y FIRMA ---")
    dte = DocumentoTributarioElectronico.objects.filter(folio=97, tipo_dte='52').first()
    if not dte:
        print("No se encontró el DTE 97")
        return
    
    service = DTEService(dte.empresa)
    generator = DTEXMLGenerator(dte.empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
    xml_sin_firmar = generator.generar_xml()
    
    # Firmar el XML
    print("Firmando XML...")
    firmador = service._obtener_firmador()
    xml_firmado = firmador.firmar_xml(xml_sin_firmar)
    
    # Guardar para debug
    with open("debug_folio_97_minimal_signed.xml", "w") as f:
        f.write(xml_firmado)
    print("XML firmado generado en debug_folio_97_minimal_signed.xml")
    
    box_service = DTEBoxService(dte.empresa)
    res = box_service.timbrar_dte(xml_firmado, tipo_dte='52')
    
    if res['success']:
        print("[SUCCESS] DTE Enviado y Timbrado!")
        print(f"TED: {res['ted'][:100]}...")
    else:
        print(f"[FAIL] Error: {res['error']}")

if __name__ == "__main__":
    retry_97_signed()
