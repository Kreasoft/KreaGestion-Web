import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
dte = DocumentoTributarioElectronico.objects.get(id=156)
print(f"XML DTE (primera parte):\n{dte.xml_dte[:2000]}")
if dte.xml_firmado:
    print(f"\nXML Firmado (primera parte):\n{dte.xml_firmado[:2000]}")
