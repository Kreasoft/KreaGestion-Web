import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
import re

dte = DocumentoTributarioElectronico.objects.get(id=74)

print("=" * 80)
print("VERIFICACIÓN DTE 74 REGENERADO")
print("=" * 80)

# Buscar elementos en el XML
ciudad = re.search(r'<CiudadRecep>([^<]+)</CiudadRecep>', dte.xml_dte)
ind_tras = re.search(r'<IndTraslado>(\d+)</IndTraslado>', dte.xml_dte)
rzn_soc = re.search(r'<RznSoc>([^<]+)</RznSoc>', dte.xml_dte)
giro_emis = re.search(r'<GiroEmis>([^<]+)</GiroEmis>', dte.xml_dte)
transporte = '<Transporte>' in dte.xml_dte

print(f"\n✓ Elementos del XML:")
print(f"  CiudadRecep: {ciudad.group(1) if ciudad else '❌ NO ENCONTRADO'}")
print(f"  IndTraslado: {ind_tras.group(1) if ind_tras else '❌ NO ENCONTRADO'}")
print(f"  RznSoc: {rzn_soc.group(1)[:50] if rzn_soc else '❌ NO ENCONTRADO'}...")
print(f"  GiroEmis: {giro_emis.group(1)[:50] if giro_emis else '❌ NO ENCONTRADO'}...")
print(f"  Transporte: {'❌ PRESENTE (ERROR)' if transporte else '✓ AUSENTE (correcto)'}")

print(f"\n✓ Tamaños:")
print(f"  XML: {len(dte.xml_dte)} caracteres")
print(f"  XML Firmado: {len(dte.xml_firmado)} caracteres")
print(f"  TED: {len(dte.timbre_electronico)} caracteres")
print(f"  PDF417: {len(dte.datos_pdf417)} caracteres")

print(f"\n✓ Datos del DTE:")
print(f"  Tipo: {dte.get_tipo_dte_display()}")
print(f"  Folio: {dte.folio}")
print(f"  Receptor: {dte.razon_social_receptor}")
print(f"  Total: ${dte.monto_total}")

# Mostrar primeras líneas del XML
print(f"\n✓ Primeras 30 líneas del XML regenerado:")
print("-" * 80)
lines = dte.xml_dte.split('\n')
for i, line in enumerate(lines[:30], 1):
    print(f"{i:3}: {line}")

print("\n" + "=" * 80)
print("LISTO PARA ENVIAR A DTEBOX")
print("=" * 80)
