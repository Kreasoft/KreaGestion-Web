import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
dte = DocumentoTributarioElectronico.objects.get(id=156)
with open('dte_156_debug.xml', 'w', encoding='latin-1') as f:
    f.write(dte.xml_dte)
print("XML guardado en dte_156_debug.xml")
