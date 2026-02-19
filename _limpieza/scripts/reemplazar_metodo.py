"""
Script para reemplazar el método timbrar_dte en dtebox_service.py
"""

# Leer archivo original
with open('facturacion_electronica/dtebox_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar inicio y fin del método timbrar_dte
start_line = None
end_line = None

for i, line in enumerate(lines):
    if 'def timbrar_dte(self, xml_firmado):' in line:
        start_line = i
    elif start_line is not None and line.strip().startswith('def ') and i > start_line:
        end_line = i
        break

print(f"Método timbrar_dte encontrado: líneas {start_line} a {end_line}")

# Leer el nuevo método
with open('TIMBRAR_DTE_CORRECTO.py', 'r', encoding='utf-8') as f:
    nuevo_metodo = f.readlines()

# Remover las primeras líneas de comentario del nuevo método
nuevo_metodo = [line for line in nuevo_metodo if not line.strip().startswith('"""') or 'def timbrar_dte' in line]
# Encontrar donde empieza realmente el método
inicio_real = None
for i, line in enumerate(nuevo_metodo):
    if 'def timbrar_dte' in line:
        inicio_real = i
        break

if inicio_real:
    nuevo_metodo = nuevo_metodo[inicio_real:]

# Ajustar indentación (el nuevo método no tiene indentación de clase)
nuevo_metodo_indentado = []
for line in nuevo_metodo:
    if line.strip():  # Si no está vacía
        nuevo_metodo_indentado.append('    ' + line)  # Agregar 4 espacios
    else:
        nuevo_metodo_indentado.append(line)

# Construir nuevo archivo
nuevo_archivo = lines[:start_line] + nuevo_metodo_indentado + ['\n'] + lines[end_line:]

# Guardar
with open('facturacion_electronica/dtebox_service.py', 'w', encoding='utf-8') as f:
    f.writelines(nuevo_archivo)

print(f"✅ Método timbrar_dte reemplazado exitosamente")
print(f"   Líneas originales: {end_line - start_line}")
print(f"   Líneas nuevas: {len(nuevo_metodo_indentado)}")
print(f"   Total líneas archivo: {len(nuevo_archivo)}")
