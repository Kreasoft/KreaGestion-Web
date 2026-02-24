
import os
import sys
import django
import re

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService

def verify():
    # Usar el mismo DTE que fallaba
    dte = DocumentoTributarioElectronico.objects.get(id=136)
    empresa = dte.empresa
    
    # El XML original del DTE (que ya esta firmado pero le faltara limpieza)
    xml_firmado = dte.xml_firmado
    
    service = DTEBoxService(empresa)
    
    print(f"Probando envio de Boleta {dte.folio} usando el nuevo DTEBoxService...")
    
    # El metodo timbrar_dte hara toda la limpieza y correccion de esquema
    resultado = service.timbrar_dte(xml_firmado, tipo_dte=dte.tipo_dte)
    
    if resultado['success']:
        print("¡EXITO TOTAL!")
        print(f"TED recibido: {resultado['ted'][:100]}...")
    else:
        print(f"FALLO: {resultado.get('error')}")
        # Si fallo, vamos a ver como quedo el XML preparado para depurar
        xml_debug = service._limpiar_y_preparar_xml(xml_firmado, dte.tipo_dte)
        with open('debug_service_xml.xml', 'w', encoding='ISO-8859-1') as f:
            f.write(xml_debug)
        print("XML preparado guardado en debug_service_xml.xml para inspeccion.")

if __name__ == "__main__":
    verify()
