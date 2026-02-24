import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_service import DTEService
from empresas.models import Empresa

print("REGENERANDO XML FOLIO 261")
print("="*60)

empresa = Empresa.objects.filter(activa=True).first()
dte = DocumentoTributarioElectronico.objects.get(tipo_dte='39', folio=261, empresa=empresa)

print(f"DTE ID: {dte.id}")
print(f"Venta ID: {dte.venta_id}")
print(f"XML actual: {len(dte.xml_firmado) if dte.xml_firmado else 0} chars")
print()

# Regenerar con DTEXMLGenerator
service = DTEService(empresa)
service.procesar_dte_existente(dte)

# Verificar nuevo XML
dte.refresh_from_db()
xml = dte.xml_firmado[:3000]

checks = {
    'RznSocEmisor (correcto)': 'RznSocEmisor' in xml,
    'GiroEmisor (correcto)': 'GiroEmisor' in xml,
    'TasaIVA (prohibido)': 'TasaIVA' in xml,
}

print("\nVERIFICACION NUEVO XML:")
for check, result in checks.items():
    status = '✓' if (result and 'correcto' in check) or (not result and 'prohibido' in check) else '✗'
    print(f"{status} {check}: {'SÍ' if result else 'NO'}")

if checks['RznSocEmisor (correcto)'] and not checks['TasaIVA (prohibido)']:
    print("\n✅ XML regenerado correctamente con DTEXMLGenerator")
else:
    print("\n❌ XML sigue con errores")
