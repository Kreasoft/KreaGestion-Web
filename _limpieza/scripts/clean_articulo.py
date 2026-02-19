
path = r"c:\PROJECTOS-WEB\GestionCloud\articulos\templates\articulos\articulo_form.html"
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Eliminamos líneas basura identificadas en el view_file anterior
# 401: </label> extra
if "</label>" in lines[400] and len(lines[400].strip()) == 8:
    del lines[400]

# 393 y 394: Espacio y </label> extra
if "</label>" in lines[393] and len(lines[393].strip()) == 8:
    del lines[393]
if lines[392].strip() == "":
    del lines[392]

# Insertar el form-text si no está
found_text = False
for line in lines:
    if "Este es el precio final" in line:
        found_text = True
        break

if not found_text:
    # Insertar después del input-group (alrededor de la línea 397-400)
    for i in range(len(lines)):
        if "precio_final" in lines[i] and "</div>" in lines[i+1] and i > 390:
            lines.insert(i+2, '                                                <div class="form-text" style="font-size: 0.7rem;">Este es el precio final de venta al público.</div>\n')
            break

# Corregir clases de error
for i in range(len(lines)):
    if 'class="text-danger">{{ form.precio_final.errors.0 }}</div>' in lines[i]:
        lines[i] = lines[i].replace('class="text-danger"', 'class="invalid-feedback-premium d-block"')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
