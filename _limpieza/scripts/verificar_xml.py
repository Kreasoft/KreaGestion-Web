import os
import re

# Leer el XML generado
xml_file = r'C:\PROJECTOS-WEB\GestionCloud\logs\dtebox_debug\test_guia_xml.xml'

if os.path.exists(xml_file):
    with open(xml_file, 'r', encoding='ISO-8859-1') as f:
        xml_content = f.read()
    
    print("=" * 80)
    print("VERIFICACIÓN DEL XML GENERADO PARA GUÍA DE DESPACHO")
    print("=" * 80)
    
    # Extraer las primeras líneas
    lines = xml_content.split('\n')
    print("\n📄 PRIMERAS 30 LÍNEAS DEL XML:")
    print("-" * 80)
    for i, line in enumerate(lines[:30], 1):
        print(f"{i:3}: {line}")
    
    print("\n" + "=" * 80)
    print("VERIFICACIONES CRÍTICAS:")
    print("=" * 80)
    
    checks = [
        (r'<DTE.*version="1\.0"', '✓ DTE con version 1.0'),
        (r'<Documento ID="F\d+T52"', '✓ ID correcto (F{folio}T52)'),
        (r'<IndTraslado>(\d+)</IndTraslado>', '✓ IndTraslado en IdDoc'),
        (r'<RznSoc>', '✓ RznSoc (no RznSocEmisor)'),
        (r'<GiroEmis>', '✓ GiroEmis (no GiroEmisor)'),
        (r'<Transporte>', '✗ Transporte (NO debería estar)'),
    ]
    
    for pattern, message in checks:
        match = re.search(pattern, xml_content)
        if match:
            if 'Transporte' in pattern:
                print(f"  ✗ {message}")
            else:
                print(f"  {message}")
                if 'IndTraslado' in pattern:
                    print(f"      Valor: {match.group(1)}")
        else:
            if 'Transporte' in pattern:
                print(f"  ✓ Transporte AUSENTE (correcto)")
            else:
                print(f"  ✗ {message} - NO ENCONTRADO")
    
    print("\n" + "=" * 80)
    print("RESUMEN:")
    print("=" * 80)
    print(f"Tamaño del XML: {len(xml_content)} caracteres")
    print(f"Archivo: {xml_file}")
    
else:
    print(f"❌ No se encontró el archivo: {xml_file}")
