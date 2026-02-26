import os
import sys
import django

sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico as DTE
from facturacion_electronica.dtebox_service import DTEBoxService
from empresas.models import Empresa

def main(dte_id):
    dte = DTE.objects.filter(id=dte_id).first()
    if not dte:
        print("NOT_FOUND")
        return
    emp = Empresa.objects.first()
    svc = DTEBoxService(emp)
    xml_base = dte.xml_firmado or dte.xml_dte
    xml_preparado, error = svc._limpiar_y_preparar_xml(xml_base, dte.tipo_dte)
    if error:
        print("ERROR", error)
        return
    print("=== XML LIMPIO QUE SE ENVÍA EN Content (primeros 1000 chars) ===")
    print(xml_preparado[:1000])
    print("=== FIN ===")

if __name__ == "__main__":
    dte_id = int(sys.argv[1]) if len(sys.argv) > 1 else 156
    main(dte_id)
