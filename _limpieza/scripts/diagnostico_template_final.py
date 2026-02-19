#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script FINAL para diagnosticar y corregir template"""

import re
import os

file_path = r'C:\PROJECTOS-WEB\GestionCloud\facturacion_electronica\templates\facturacion_electronica\dte_list.html'

print("=" * 70)
print("DIAGNÓSTICO Y CORRECCIÓN FINAL DEL TEMPLATE")
print("=" * 70)

# Leer archivo
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"\nArchivo: {file_path}")
print(f"Total de líneas: {len(lines)}")

# DIAGNÓSTICO
print("\n" + "=" * 70)
print("DIAGNÓSTICO DE PROBLEMAS")
print("=" * 70)

problemas = []

# 1. Buscar comparadores sin espacios
for i, line in enumerate(lines, 1):
    if 'tipo_dte==key' in line or 'estado==key' in line:
        problemas.append(f"Línea {i}: Comparador sin espacios: {line.strip()}")

# 2. Buscar variables Django partidas
for i, line in enumerate(lines, 1):
    if '{{' in line and '}}' not in line:
        # Verificar si el cierre está en la siguiente línea
        if i < len(lines) and '}}' in lines[i]:
            problemas.append(f"Línea {i}: Variable Django partida en múltiples líneas")

# 3. Buscar comentarios Django multilínea
for i, line in enumerate(lines, 1):
    if '{#' in line and '#}' not in line:
        if i < len(lines) and '#}' in lines[i]:
            problemas.append(f"Línea {i}: Comentario Django multilínea")

if problemas:
    print("\n⚠️  PROBLEMAS ENCONTRADOS:")
    for p in problemas:
        print(f"  • {p}")
else:
    print("\n✅ No se encontraron problemas obvios")

# CORRECCIÓN
print("\n" + "=" * 70)
print("APLICANDO CORRECCIONES")
print("=" * 70)

content = ''.join(lines)
original = content

# 1. Corregir comparadores
content = content.replace('tipo_dte==key', 'tipo_dte == key')
content = content.replace('estado==key', 'estado == key')
print("✓ Comparadores corregidos")

# 2. Corregir variables Django partidas
# Patrón: ${{ seguido de salto de línea y espacios, luego variable }}
content = re.sub(r'\$\{\{\s*\r?\n\s*([^}]+?)\s*\}\}', r'${{ \1 }}', content)
print("✓ Variables Django unidas")

# 3. Corregir comentarios multilínea
content = re.sub(r'\{#([^#]*?)\r?\n([^#]*?)#\}', r'{# \1 \2 #}', content)
print("✓ Comentarios multilínea corregidos")

# 4. Corregir tags {% if %} multilínea
content = re.sub(r'{%\s*if\s+([^%]+?)\s+and\s*\r?\n\s*([^%]+?)\s*%}', r'{% if \1 and \2 %}', content)
print("✓ Tags {% if %} multilínea corregidos")

# Guardar
if content != original:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("\n✅ Archivo corregido y guardado")
else:
    print("\n✅ No se necesitaron correcciones")

# VERIFICACIÓN FINAL
print("\n" + "=" * 70)
print("VERIFICACIÓN FINAL")
print("=" * 70)

with open(file_path, 'r', encoding='utf-8') as f:
    final_content = f.read()

errores_finales = []
if 'tipo_dte==key' in final_content:
    errores_finales.append("Todavía existe 'tipo_dte==key'")
if 'estado==key' in final_content:
    errores_finales.append("Todavía existe 'estado==key'")
if re.search(r'\$\{\{\s*\n', final_content):
    errores_finales.append("Todavía hay variables Django partidas")

if errores_finales:
    print("\n❌ ERRORES PERSISTENTES:")
    for e in errores_finales:
        print(f"  • {e}")
else:
    print("\n✅ VERIFICACIÓN EXITOSA - No se encontraron errores")

print("\n" + "=" * 70)
print("INSTRUCCIONES FINALES")
print("=" * 70)
print("\n1. REINICIA el servidor Django (Ctrl+C y python manage.py runserver)")
print("2. LIMPIA la caché del navegador (Ctrl+Shift+R)")
print("3. Recarga la página")
print("\n" + "=" * 70)
