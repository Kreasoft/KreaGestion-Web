import os
import django
import sys

# Configurar Django
sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from lxml import etree
import re

# Redirigir stdout a archivo
sys.stdout = open('comparacion_xml_resultado.txt', 'w', encoding='utf-8')

# Cargar XML de ejemplo
with open(r'facturacion_electronica\XML_PARA_ENVIAR_Corregido (1).xml', 'rb') as f:
    xml_ejemplo_bytes = f.read()

# Obtener XML del DTE 58
dte = DocumentoTributarioElectronico.objects.get(id=58)
xml_generado = dte.xml_firmado

# Limpiar XML generado
start = xml_generado.find('<DTE')
end = xml_generado.find('</DTE>')
if start != -1 and end != -1:
    dte_block = xml_generado[start:end+6]
    dte_block = re.sub(r'<DTE[^>]*>', '<DTE version="1.0">', dte_block, count=1)
    dte_block = re.sub(r'<[^:>]*:?Signature[^>]*>.*?</[^:>]*:?Signature>', '', dte_block, flags=re.DOTALL)
    dte_block = re.sub(r'<TED[^>]*>.*?</TED>', '', dte_block, flags=re.DOTALL)
    xml_generado_limpio = '<?xml version="1.0" encoding="ISO-8859-1"?>' + dte_block
else:
    xml_generado_limpio = xml_generado

# Parsear
root_ejemplo = etree.fromstring(xml_ejemplo_bytes)
root_generado = etree.fromstring(xml_generado_limpio.encode('ISO-8859-1'))

print("=" * 80)
print("COMPARACIÓN XML EJEMPLO VS GENERADO")
print("=" * 80)

# Extraer campos
def extraer_campos(root):
    campos = {}
    for elem in root.iter():
        if elem.text and elem.text.strip():
            path = root.getroottree().getpath(elem)
            path_simple = re.sub(r'\[\d+\]', '', path)
            campos[path_simple] = elem.text.strip()
    return campos

campos_ejemplo = extraer_campos(root_ejemplo)
campos_generado = extraer_campos(root_generado)

print(f"\nTotal campos en ejemplo: {len(campos_ejemplo)}")
print(f"Total campos en generado: {len(campos_generado)}")

# Faltantes
faltantes = set(campos_ejemplo.keys()) - set(campos_generado.keys())
if faltantes:
    print(f"\n❌ CAMPOS FALTANTES ({len(faltantes)}):")
    for campo in sorted(faltantes):
        print(f"  {campo}: '{campos_ejemplo[campo]}'")
else:
    print("\n✅ No hay campos faltantes")

# Extras
extras = set(campos_generado.keys()) - set(campos_ejemplo.keys())
if extras:
    print(f"\n⚠️  CAMPOS EXTRA ({len(extras)}):")
    for campo in sorted(extras):
        print(f"  {campo}: '{campos_generado[campo]}'")

# Diferentes
diferentes = []
for campo in set(campos_ejemplo.keys()) & set(campos_generado.keys()):
    if campos_ejemplo[campo] != campos_generado[campo]:
        diferentes.append(campo)

if diferentes:
    print(f"\n🔄 VALORES DIFERENTES ({len(diferentes)}):")
    for campo in sorted(diferentes):
        print(f"  {campo}:")
        print(f"    Ejemplo:  '{campos_ejemplo[campo]}'")
        print(f"    Generado: '{campos_generado[campo]}'")

print("\n" + "=" * 80)
print("XML GENERADO LIMPIO:")
print("=" * 80)
print(xml_generado_limpio)

sys.stdout.close()
sys.stdout = sys.__stdout__
print("✅ Comparación guardada en: comparacion_xml_resultado.txt")
