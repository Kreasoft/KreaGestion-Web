from facturacion_electronica.models import DocumentoTributarioElectronico
from lxml import etree
import re

# Cargar XML de ejemplo
with open(r'facturacion_electronica\XML_PARA_ENVIAR_Corregido (1).xml', 'rb') as f:
    xml_ejemplo_bytes = f.read()

# Obtener XML del DTE 58
dte = DocumentoTributarioElectronico.objects.get(id=58)
xml_generado = dte.xml_firmado

# Limpiar XML generado (como lo hace dtebox_service)
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

# Parsear ambos
root_ejemplo = etree.fromstring(xml_ejemplo_bytes)
root_generado = etree.fromstring(xml_generado_limpio.encode('ISO-8859-1'))

print("=" * 80)
print("COMPARACIÓN DETALLADA DE CAMPOS")
print("=" * 80)

# Extraer todos los campos de ambos
def extraer_campos(root):
    campos = {}
    for elem in root.iter():
        if elem.text and elem.text.strip():
            # Obtener path completo
            path = root.getroottree().getpath(elem)
            # Simplificar path (remover indices)
            path_simple = re.sub(r'\[\d+\]', '', path)
            campos[path_simple] = elem.text.strip()
    return campos

campos_ejemplo = extraer_campos(root_ejemplo)
campos_generado = extraer_campos(root_generado)

print(f"\nTotal campos en ejemplo: {len(campos_ejemplo)}")
print(f"Total campos en generado: {len(campos_generado)}")

# Campos que están en ejemplo pero NO en generado
faltantes = set(campos_ejemplo.keys()) - set(campos_generado.keys())
if faltantes:
    print(f"\n❌ CAMPOS FALTANTES EN GENERADO ({len(faltantes)}):")
    for campo in sorted(faltantes):
        print(f"  • {campo}: '{campos_ejemplo[campo]}'")

# Campos que están en generado pero NO en ejemplo
extras = set(campos_generado.keys()) - set(campos_ejemplo.keys())
if extras:
    print(f"\n⚠️  CAMPOS EXTRA EN GENERADO ({len(extras)}):")
    for campo in sorted(extras):
        print(f"  • {campo}: '{campos_generado[campo]}'")

# Campos con valores diferentes
diferentes = []
for campo in set(campos_ejemplo.keys()) & set(campos_generado.keys()):
    if campos_ejemplo[campo] != campos_generado[campo]:
        diferentes.append(campo)

if diferentes:
    print(f"\n🔄 CAMPOS CON VALORES DIFERENTES ({len(diferentes)}):")
    for campo in sorted(diferentes):
        print(f"  • {campo}:")
        print(f"      Ejemplo:  '{campos_ejemplo[campo]}'")
        print(f"      Generado: '{campos_generado[campo]}'")

print("\n" + "=" * 80)
print("ESTRUCTURA DEL XML GENERADO:")
print("=" * 80)
print(xml_generado_limpio[:1000])
print("\n" + "=" * 80)

# Guardar en archivo
with open('comparacion_xml_resultado.txt', 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write("COMPARACIÓN DETALLADA DE CAMPOS\n")
    f.write("=" * 80 + "\n\n")
    f.write(f"Total campos en ejemplo: {len(campos_ejemplo)}\n")
    f.write(f"Total campos en generado: {len(campos_generado)}\n\n")
    
    if faltantes:
        f.write(f"❌ CAMPOS FALTANTES EN GENERADO ({len(faltantes)}):\n")
        for campo in sorted(faltantes):
            f.write(f"  • {campo}: '{campos_ejemplo[campo]}'\n")
        f.write("\n")
    
    if extras:
        f.write(f"⚠️  CAMPOS EXTRA EN GENERADO ({len(extras)}):\n")
        for campo in sorted(extras):
            f.write(f"  • {campo}: '{campos_generado[campo]}'\n")
        f.write("\n")
    
    if diferentes:
        f.write(f"🔄 CAMPOS CON VALORES DIFERENTES ({len(diferentes)}):\n")
        for campo in sorted(diferentes):
            f.write(f"  • {campo}:\n")
            f.write(f"      Ejemplo:  '{campos_ejemplo[campo]}'\n")
            f.write(f"      Generado: '{campos_generado[campo]}'\n")
        f.write("\n")
    
    f.write("=" * 80 + "\n")
    f.write("XML GENERADO LIMPIO:\n")
    f.write("=" * 80 + "\n")
    f.write(xml_generado_limpio)

print("\n✅ Comparación guardada en: comparacion_xml_resultado.txt")
