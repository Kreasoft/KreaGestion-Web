import sys
import re

def patch_views_detalle():
    filepath = 'ventas/views.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        if "articulo=detalle.articulo," in line:
            # Check if descripcion is already added in the next line
            if i + 1 < len(lines) and "descripcion=detalle.descripcion," in lines[i+1]:
                continue
            
            indent = line.split("articulo=")[0]
            new_lines.append(indent + "descripcion=detalle.descripcion,")
            print(f"Added descripcion at line {i+1}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

patch_views_detalle()
