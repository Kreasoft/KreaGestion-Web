import os
import django
import sys

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico

def read_xml():
    d = DocumentoTributarioElectronico.objects.get(folio=94, tipo_dte='52')
    print(d.xml_firmado)

if __name__ == "__main__":
    read_xml()
