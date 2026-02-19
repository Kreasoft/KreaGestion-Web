"""
Comparar XML generado vs XML de ejemplo que funciona
"""
from facturacion_electronica.models import DocumentoTributarioElectronico
import re

# Leer XML de ejemplo que funciona
with open(r'facturacion_electronica\XML_PARA_ENVIAR_Corregido (1).xml', 'r', encoding='ISO-8859-1') as f:
    xml_ejemplo = f.read()

# Obtener XML del DTE 58
dte = DocumentoTributarioElectronico.objects.get(id=58)
xml_generado = dte.xml_firmado

# Extraer bloque DTE del generado
start = xml_generado.find('<DTE')
end = xml_generado.find('</DTE>')
if start != -1 and end != -1:
    dte_block = xml_generado[start:end+6]
    # Limpiar tag DTE
    dte_block = re.sub(r'<DTE[^>]*>', '<DTE version="1.0">', dte_block, count=1)
    # Remover firma
    dte_block = re.sub(r'<[^:>]*:?Signature[^>]*>.*?</[^:>]*:?Signature>', '', dte_block, flags=re.DOTALL)
    # Remover TED
    dte_block = re.sub(r'<TED[^>]*>.*?</TED>', '', dte_block, flags=re.DOTALL)
    xml_generado_limpio = '<?xml version="1.0" encoding="ISO-8859-1"?>' + dte_block
else:
    xml_generado_limpio = xml_generado

print("=" * 80)
print("COMPARACIÓN XML EJEMPLO vs GENERADO")
print("=" * 80)

print("\n1. LONGITUD:")
print(f"   Ejemplo: {len(xml_ejemplo)} caracteres")
print(f"   Generado: {len(xml_generado_limpio)} caracteres")

print("\n2. ESTRUCTURA:")
print(f"   Ejemplo tiene Signature: {'<Signature' in xml_ejemplo}")
print(f"   Generado tiene Signature: {'<Signature' in xml_generado_limpio}")
print(f"   Ejemplo tiene TED: {'<TED' in xml_ejemplo}")
print(f"   Generado tiene TED: {'<TED' in xml_generado_limpio}")

print("\n3. CAMPOS IMPORTANTES:")
campos = ['TipoDTE', 'Folio', 'FchEmis', 'FmaPago', 'RUTEmisor', 'RznSoc', 'GiroEmis', 
          'RUTRecep', 'RznSocRecep', 'MntNeto', 'IVA', 'MntTotal', 'NmbItem']

for campo in campos:
    en_ejemplo = f'<{campo}>' in xml_ejemplo
    en_generado = f'<{campo}>' in xml_generado_limpio
    simbolo = '✓' if en_ejemplo == en_generado else '✗'
    print(f"   {simbolo} {campo}: Ejemplo={en_ejemplo}, Generado={en_generado}")

print("\n4. PRIMEROS 500 CARACTERES:")
print("\n   EJEMPLO:")
print(xml_ejemplo[:500])
print("\n   GENERADO:")
print(xml_generado_limpio[:500])

# Guardar ambos para comparación manual
with open('comparacion_ejemplo.xml', 'w', encoding='ISO-8859-1') as f:
    f.write(xml_ejemplo)
with open('comparacion_generado.xml', 'w', encoding='ISO-8859-1') as f:
    f.write(xml_generado_limpio)

print("\n" + "=" * 80)
print("Archivos guardados:")
print("  - comparacion_ejemplo.xml")
print("  - comparacion_generado.xml")
print("=" * 80)
