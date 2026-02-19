#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para corregir TODOS los errores de sintaxis del template Django"""

import re

file_path = r'c:\PROJECTOS-WEB\GestionCloud\facturacion_electronica\templates\facturacion_electronica\dte_list.html'

print("Leyendo archivo...")
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print("Aplicando correcciones...")

# 1. Corregir comparadores sin espacios
content = re.sub(r'tipo_dte==key', 'tipo_dte == key', content)
content = re.sub(r'estado==key', 'estado == key', content)
print("  OK - Corregidos comparadores ==")

# 2. Buscar y corregir tags {% if %} multilínea
# Patrón para encontrar {% if ... and\n ... %}
pattern = r'{%\s*if\s+([^%]+?)\s+and\s*\n\s*([^%]+?)\s*%}'
replacement = r'{% if \1 and \2 %}'
content = re.sub(pattern, replacement, content)
print("  OK - Corregidos tags multilínea")

# 3. Verificar balance de tags
if_count = len(re.findall(r'{%\s*if\s+', content))
endif_count = len(re.findall(r'{%\s*endif\s*%}', content))
for_count = len(re.findall(r'{%\s*for\s+', content))
endfor_count = len(re.findall(r'{%\s*endfor\s*%}', content))

print("\nBalance de tags:")
if_balance = "OK" if if_count == endif_count else "DESBALANCEADO"
for_balance = "OK" if for_count == endfor_count else "DESBALANCEADO"
print(f"  if/endif: {if_count}/{endif_count} - {if_balance}")
print(f"  for/endfor: {for_count}/{endfor_count} - {for_balance}")

# Escribir archivo corregido
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nArchivo corregido exitosamente")
