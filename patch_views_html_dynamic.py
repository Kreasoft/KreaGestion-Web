import sys

def patch_views_html_dynamic():
    filepath = 'ventas/views.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    idx = content.find('<select name="modo_pos"')
    if idx == -1:
        print("Not found")
        return
        
    start_idx = content.rfind('<div class="row">', 0, idx)
    end_idx = content.find('</div>\n            </div>\n', idx) + len('</div>\n            </div>\n')
    
    old_segment = content[start_idx:end_idx]
    
    new_segment = """<div class="row">
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label" style="font-weight: 600;">Formato Impresión</label>
                        <select name="formato_impresion" class="form-select">
                            <option value="80mm" {'selected' if estacion.formato_impresion == '80mm' else ''}>Térmica 80mm</option>
                            <option value="58mm" {'selected' if estacion.formato_impresion == '58mm' else ''}>Térmica 58mm</option>
                            <option value="carta" {'selected' if estacion.formato_impresion == 'carta' else ''}>Carta (PDF)</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label" style="font-weight: 600;">Modo de Operación POS *</label>
                        <select name="modo_pos" class="form-select">
                            <option value="normal" {'selected' if estacion.modo_pos == 'normal' else ''}>Normal - Cliente al final</option>
                            <option value="con_cliente" {'selected' if estacion.modo_pos == 'con_cliente' else ''}>Con Cliente - Seleccionar al inicio</option>
                        </select>
                    </div>
                </div>
            </div>
"""
    
    content = content.replace(old_segment, new_segment)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Patched using dynamic finding!")

patch_views_html_dynamic()
