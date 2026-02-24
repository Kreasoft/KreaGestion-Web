
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

def test():
    dte = DocumentoTributarioElectronico.objects.get(id=136)
    empresa = dte.empresa
    service = DTEBoxService(empresa)
    
    print(f"Probando timbrado de DTE {dte.id} (Folio {dte.folio}, Tipo {dte.tipo_dte})")
    print(f"XML Firmado (primeros 100): {dte.xml_dte[:100]}")
    
    res = service.timbrar_dte(dte.xml_dte)
    print(f"Resultado: {res}")

if __name__ == "__main__":
    test()
