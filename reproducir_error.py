
import os
import sys
import django
from django.utils import timezone

# Configurar Django
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.append(base_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService
from facturacion_electronica.dte_generator import DTEXMLGenerator

def test_regenerar_y_enviar(folio, tipo='52'):
    try:
        dte = DocumentoTributarioElectronico.objects.filter(folio=folio, tipo_dte=tipo).latest('id')
        empresa = dte.empresa
        
        print(f"--- Regenerando y Probando Folio {folio} (Tipo {tipo}) ---")
        
        # Sincronizar fecha para evitar "Fecha futura"
        dte.fecha_emision = timezone.localtime(timezone.now()).date()
        dte.save()
        
        # Regenerar XML
        generator = DTEXMLGenerator(empresa, dte, tipo, folio, dte.caf_utilizado)
        nuevo_xml = generator.generar_xml()
        
        print(f"Nuevo XML generado (fragmento IdDoc):")
        if '<IdDoc>' in nuevo_xml:
            idx = nuevo_xml.find('<IdDoc>')
            idx2 = nuevo_xml.find('</IdDoc>') + 8
            print(nuevo_xml[idx:idx2])
        
        # Usar el servicio de TEST/BACKUP
        from facturacion_electronica.dtebox_service_test import DTEBoxService
        service = DTEBoxService(empresa)
        res = service.timbrar_dte(nuevo_xml)
        
        print(f"RESULTADO: {res.get('success')}")
        if not res.get('success'):
            print(f"ERROR: {res.get('error')}")
            if res.get('detail'):
                print(f"DETALLE: {res.get('detail')}")
        else:
            print(f"EXITO! Folio {folio} timbrado.")
            
        return res
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_regenerar_y_enviar(192)
