import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico

print("VERIFICANDO XML FOLIO 260")
print("="*60)

dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=260).first()

if dte and dte.xml_firmado:
    xml = dte.xml_firmado[:2000]
    
    checks = {
        'RznSocEmisor (correcto)': 'RznSocEmisor' in xml,
        'GiroEmisor (correcto)': 'GiroEmisor' in xml,
        'RznSoc (incorrecto)': 'RznSoc<' in xml and 'RznSocEmisor' not in xml,
        'GiroEmis (incorrecto)': 'GiroEmis' in xml and 'GiroEmisor' not in xml,
        'TasaIVA presente': 'TasaIVA' in xml,
        'TED presente': '<TED>' in xml,
    }
    
    print(f"XML firmado: {len(dte.xml_firmado)} caracteres")
    print(f"Timbre: {'Sí' if dte.timbre_electronico else 'No'}")
    print()
    
    for check, result in checks.items():
        status = '✓' if result else '✗'
        print(f"{status} {check}: {'SÍ' if result else 'NO'}")
    
    # Determinar generador
    if checks['RznSocEmisor (correcto)'] and not checks['TasaIVA presente']:
        print("\n✅ XML generado por DTEXMLGenerator (correcto)")
    elif checks['RznSoc (incorrecto)'] or checks['TasaIVA presente']:
        print("\n⚠️ XML generado por GeneradorBoleta (incorrecto)")
    else:
        print("\n? No se puede determinar el generador")
else:
    print("No tiene XML firmado")
