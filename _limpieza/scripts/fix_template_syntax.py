#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para corregir sintaxis de template Django"""

import re

# Leer el archivo
file_path = r'c:\PROJECTOS-WEB\GestionCloud\facturacion_electronica\templates\facturacion_electronica\dte_list.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar todas las ocurrencias de ==key sin espacios
content = re.sub(r'tipo_dte==key', 'tipo_dte == key', content)
content = re.sub(r'estado==key', 'estado == key', content)

# Escribir el archivo corregido
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Archivo corregido exitosamente")
print("Cambios aplicados:")
print("  - tipo_dte==key → tipo_dte == key")
print("  - estado==key → estado == key")
