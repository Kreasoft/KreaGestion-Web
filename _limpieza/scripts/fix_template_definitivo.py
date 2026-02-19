#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script DEFINITIVO para corregir template y limpiar cache"""

import os
import re
import shutil
import sys

print("=" * 60)
print("SCRIPT DEFINITIVO DE CORRECCIÓN DE TEMPLATE")
print("=" * 60)

# 1. LIMPIAR CACHE DE DJANGO
print("\n[1/4] Limpiando cache de Django...")
cache_dirs = [
    r'C:\PROJECTOS-WEB\GestionCloud\__pycache__',
    r'C:\PROJECTOS-WEB\GestionCloud\facturacion_electronica\__pycache__',
]

for cache_dir in cache_dirs:
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print(f"  ✓ Eliminado: {cache_dir}")
        except Exception as e:
            print(f"  ⚠ No se pudo eliminar {cache_dir}: {e}")

# 2. ELIMINAR ARCHIVOS .PYC
print("\n[2/4] Eliminando archivos .pyc...")
pyc_count = 0
for root, dirs, files in os.walk(r'C:\PROJECTOS-WEB\GestionCloud'):
    for file in files:
        if file.endswith('.pyc'):
            try:
                os.remove(os.path.join(root, file))
                pyc_count += 1
            except:
                pass
print(f"  ✓ Eliminados {pyc_count} archivos .pyc")

# 3. CORREGIR TEMPLATE
print("\n[3/4] Corrigiendo template...")
file_path = r'C:\PROJECTOS-WEB\GestionCloud\facturacion_electronica\templates\facturacion_electronica\dte_list.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Aplicar TODAS las correcciones
original_content = content

# Corregir comparadores
content = content.replace('tipo_dte==key', 'tipo_dte == key')
content = content.replace('estado==key', 'estado == key')

# Corregir tags multilínea
content = re.sub(r'{%\s*if\s+([^%]+?)\s+and\s*\r?\n\s*([^%]+?)\s*%}', r'{% if \1 and \2 %}', content)

# Escribir archivo
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

if content != original_content:
    print("  ✓ Template corregido")
else:
    print("  ℹ Template ya estaba correcto")

# 4. VERIFICAR
print("\n[4/4] Verificando correcciones...")
with open(file_path, 'r', encoding='utf-8') as f:
    final_content = f.read()

errors = []
if 'tipo_dte==key' in final_content:
    errors.append("  ✗ Todavía existe 'tipo_dte==key'")
if 'estado==key' in final_content:
    errors.append("  ✗ Todavía existe 'estado==key'")

if errors:
    print("ERRORES ENCONTRADOS:")
    for error in errors:
        print(error)
    sys.exit(1)
else:
    print("  ✓ No se encontraron errores de sintaxis")

print("\n" + "=" * 60)
print("✅ PROCESO COMPLETADO EXITOSAMENTE")
print("=" * 60)
print("\nPor favor:")
print("1. Detén el servidor Django (Ctrl+C)")
print("2. Reinicia el servidor: python manage.py runserver")
print("3. Recarga la página en el navegador")
