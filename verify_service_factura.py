
import os
import sys
import django

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService

def verify_factura():
    # Usar una factura (id 141)
    dte = DocumentoTributarioElectronico.objects.get(id=141)
    empresa = dte.empresa
    xml_firmado = dte.xml_firmado
    
    service = DTEBoxService(empresa)
    print(f"Probando envio de Factura {dte.folio}...")
    resultado = service.timbrar_dte(xml_firmado, tipo_dte=dte.tipo_dte)
    
    if resultado['success']:
        print("¡EXITO FACTURA!")
        print(f"TED: {resultado['ted'][:50]}...")
    else:
        print(f"FALLO FACTURA: {resultado.get('error')}")
        xml_debug = service._limpiar_y_preparar_xml(xml_firmado, dte.tipo_dte)
        with open('debug_service_factura.xml', 'w', encoding='ISO-8859-1') as f:
            f.write(xml_debug)

if __name__ == "__main__":
    verify_factura()
