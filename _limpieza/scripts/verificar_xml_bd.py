import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
import re

dte = DocumentoTributarioElectronico.objects.get(id=74)

print("DTE 74 - VERIFICACION DE XML EN BD")
print("=" * 70)

# Verificar xml_dte
if dte.xml_dte:
    ciudad_dte = re.search(r'<CiudadRecep>([^<]+)</CiudadRecep>', dte.xml_dte)
    ind_dte = re.search(r'<IndTraslado>(\d+)</IndTraslado>', dte.xml_dte)
    
    print(f"\nxml_dte ({len(dte.xml_dte)} chars):")
    print(f"  CiudadRecep: {ciudad_dte.group(1) if ciudad_dte else 'NO ENCONTRADO'}")
    print(f"  IndTraslado: {ind_dte.group(1) if ind_dte else 'NO ENCONTRADO'}")

# Verificar xml_firmado
if dte.xml_firmado:
    ciudad_firm = re.search(r'<CiudadRecep>([^<]+)</CiudadRecep>', dte.xml_firmado)
    ind_firm = re.search(r'<IndTraslado>(\d+)</IndTraslado>', dte.xml_firmado)
    
    print(f"\nxml_firmado ({len(dte.xml_firmado)} chars):")
    print(f"  CiudadRecep: {ciudad_firm.group(1) if ciudad_firm else 'NO ENCONTRADO'}")
    print(f"  IndTraslado: {ind_firm.group(1) if ind_firm else 'NO ENCONTRADO'}")

print(f"\nTED: {len(dte.timbre_electronico) if dte.timbre_electronico else 0} chars")
print(f"PDF417: {len(dte.datos_pdf417) if dte.datos_pdf417 else 0} chars")

print("\n" + "=" * 70)
print("CONCLUSION:")
if ciudad_dte and ciudad_firm:
    print("OK: Ambos XMLs tienen CiudadRecep")
elif ciudad_dte and not ciudad_firm:
    print("PROBLEMA: xml_dte tiene CiudadRecep pero xml_firmado NO")
    print("SOLUCION: Regenerar la firma")
elif not ciudad_dte and ciudad_firm:
    print("PROBLEMA: xml_firmado tiene CiudadRecep pero xml_dte NO")
else:
    print("PROBLEMA GRAVE: Ningun XML tiene CiudadRecep")
    print("El script de regeneracion NO actualizo la BD")
