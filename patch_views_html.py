import sys

def patch_views_html():
    filepath = 'ventas/views.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # The HTML block to patch
    old_html_segment = """            <div class="row">
                <div class="col-md-12">
                    <div class="mb-3">
                        <label class="form-label" style="font-weight: 600;">Modo de Operación POS *</label>
                        <select name="modo_pos" class="form-select">
                            <option value="normal" {'selected' if estacion.modo_pos == 'normal' else ''}>Normal - Cliente al final</option>
                            <option value="con_cliente" {'selected' if estacion.modo_pos == 'con_cliente' else ''}>Con Cliente - Seleccionar al inicio</option>
                        </select>
                        <small class="text-muted d-block mt-1">
                            <i class="fas fa-info-circle me-1"></i>
                            <strong>Normal:</strong> Cliente opcional al final de la venta (modo tradicional).<br>
                            <i class="fas fa-info-circle me-1"></i>
                            <strong>Con Cliente:</strong> Selección obligatoria de cliente al inicio para aplicar precios especiales y descuentos personalizados.
                        </small>
                    </div>
                </div>
            </div>"""

    new_html_segment = """            <div class="row">
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
                <div class="col-md-12 mb-3">
                    <small class="text-muted d-block mt-1">
                        <i class="fas fa-info-circle me-1"></i>
                        <strong>Normal:</strong> Cliente opcional al final de la venta.<br>
                        <i class="fas fa-info-circle me-1"></i>
                        <strong>Con Cliente:</strong> Selección obligatoria de cliente al inicio.
                    </small>
                </div>
            </div>"""

    if old_html_segment in content:
        content = content.replace(old_html_segment, new_html_segment)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched successfully")
    else:
        print("Could not find the HTML segment")

patch_views_html()
