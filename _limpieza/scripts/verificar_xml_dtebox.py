#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verificar formato del XML que se envía a DTEBox"""

import os
import django
import sys

sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService

# Obtener DTE
dte = DocumentoTributarioElectronico.objects.get(id=58)

print("=" * 80)
print("VERIFICACIÓN DEL XML PARA DTEBOX")
print("=" * 80)
print(f"\nDTE: Tipo {dte.tipo_dte}, Folio {dte.folio}")
print(f"Estado: {dte.estado_sii}")
print()

# Inicializar DTEBox service
dtebox = DTEBoxService(dte.empresa)

# Obtener el XML original
xml_original = dte.xml_firmado

print("1. XML ORIGINAL (primeros 500 chars):")
print("-" * 80)
print(xml_original[:500])
print()

# Procesar el XML como lo hace DTEBox
import re

# Extraer bloque DTE
start_dte = xml_original.find('<DTE')
end_dte = xml_original.find('</DTE>')

if start_dte != -1 and end_dte != -1:
    dte_xml = xml_original[start_dte:end_dte + 6]
    
    # Simplificar tag DTE
    dte_xml = re.sub(r'<DTE[^>]*>', '<DTE version="1.0">', dte_xml, count=1)
    
    # Agregar declaración XML
    xml_final = '<?xml version="1.0" encoding="ISO-8859-1"?>' + dte_xml
    
    print("2. XML PROCESADO (primeros 800 chars):")
    print("-" * 80)
    print(xml_final[:800])
    print()
    
    # Verificar si tiene firma
    tiene_signature = '<Signature' in xml_final or '<ds:Signature' in xml_final
    tiene_ted = '<TED' in xml_final
    
    print("3. VERIFICACIONES:")
    print("-" * 80)
    print(f"  • Tiene <Signature>: {'❌ SÍ (DEBE REMOVERSE)' if tiene_signature else '✅ NO'}")
    print(f"  • Tiene <TED>: {'❌ SÍ (DEBE REMOVERSE)' if tiene_ted else '✅ NO'}")
    print(f"  • Longitud: {len(xml_final)} caracteres")
    print()
    
    # Comparar con el ejemplo
    print("4. COMPARACIÓN CON EJEMPLO:")
    print("-" * 80)
    
    ejemplo_path = r'c:\PROJECTOS-WEB\GestionCloud\facturacion_electronica\XML_PARA_ENVIAR_Corregido (1).xml'
    with open(ejemplo_path, 'r', encoding='ISO-8859-1') as f:
        xml_ejemplo = f.read()
    
    print(f"  • Ejemplo (primeros 500 chars):")
    print(xml_ejemplo[:500])
    print()
    
    # Verificar estructura
    print("5. ESTRUCTURA:")
    print("-" * 80)
    print(f"  • Inicia con declaración XML: {'✅' if xml_final.startswith('<?xml') else '❌'}")
    print(f"  • Tag DTE limpio: {'✅' if '<DTE version="1.0">' in xml_final else '❌'}")
    print(f"  • Sin namespaces: {'✅' if 'xmlns' not in xml_final[:200] else '❌'}")
    
else:
    print("❌ No se encontró el bloque <DTE>...</DTE>")

print()
print("=" * 80)
