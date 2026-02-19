
import os

path = r"c:\PROJECTOS-WEB\GestionCloud\articulos\templates\articulos\articulo_form.html"
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # Restituir </label> accidentalmente borrados
    if line.strip() == "" and "   " in line:
         # Esto es muy impreciso, mejor usar el contenido original si lo tengo
         pass
    new_lines.append(line)

# Mejor técnica: usar los bloques corregidos que quería aplicar
full_content = "".join(lines)

# 1. Corregir los cierres de </label> de 48 spaces (392-ish)
# Buscamos labels que quedaron abiertos
import re
# Reemplazar "   " (3 spaces) que quedaron donde iba el </label>
full_content = full_content.replace("   \n", "                                                </label>\n")
full_content = full_content.replace("       \n", "                                                    </label>\n")

# 2. Corregir la sección de Precio Final (líneas 388-407 aprox)
# Buscamos el bloque por su contenido único
old_block_regex = r'<div class="col-md-4">\s+<div class="mb-3">\s+<label for="{{ form\.precio_final\.id_for_label }}" class="form-label-premium">PRECIO FINAL \(CON IVA\+IMP\)</label>\s+<i class="fas fa-calculator me-1"></i>Precio Final\s+<div class="input-group-premium d-flex align-items-center"'
# Espera, mi reemplazo anterior fue parcial. 

# Escribimos el contenido restaurado primero
with open(path, 'w', encoding='utf-8') as f:
    f.write(full_content)
