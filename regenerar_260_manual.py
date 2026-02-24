import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.firma_electronica import FirmadorDTE
from empresas.models import Empresa

print("REGENERANDO XML FOLIO 260 MANUALMENTE")
print("="*60)

empresa = Empresa.objects.filter(activa=True).first()
dte = DocumentoTributarioElectronico.objects.get(tipo_dte='39', folio=260, empresa=empresa)

print(f"DTE ID: {dte.id}")
print(f"Venta ID: {dte.venta_id}")
print(f"CAF ID: {dte.caf_utilizado.id}")
print()

# Generar nuevo XML con DTEXMLGenerator
generator = DTEXMLGenerator(empresa, dte, '39', 260, dte.caf_utilizado)
xml_sin_firmar = generator.generar_xml_desde_dte()

print(f"XML generado: {len(xml_sin_firmar)} caracteres")

# Verificar esquema
checks = {
    'RznSocEmisor': 'RznSocEmisor' in xml_sin_firmar,
    'GiroEmisor': 'GiroEmisor' in xml_sin_firmar,
    'TasaIVA (prohibido)': 'TasaIVA' in xml_sin_firmar,
    'TED': '<TED>' in xml_sin_firmar,
    'TmstFirma': 'TmstFirma' in xml_sin_firmar,
}

print("\nVerificación esquema:")
for check, result in checks.items():
    status = '✓' if result else '✗'
    if 'prohibido' in check:
        status = '✓' if not result else '✗'
    print(f"  {status} {check}: {'SÍ' if result else 'NO'}")

# Firmar XML
print("\nFirmando XML...")
firmador = FirmadorDTE(empresa.certificado_digital.path, empresa.password_certificado)
xml_firmado = firmador.firmar_xml(xml_sin_firmar)

print(f"XML firmado: {len(xml_firmado)} caracteres")

# Guardar
dte.xml_dte = xml_sin_firmar
dte.xml_firmado = xml_firmado
dte.estado_sii = 'generado'
dte.error_envio = ''
dte.save()

print("\n✅ XML del folio 260 regenerado y guardado")
print("Listo para enviar a GDExpress")
