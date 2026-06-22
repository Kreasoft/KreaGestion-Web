import sys

def patch_impresion_utils():
    filepath = 'caja/impresion_utils.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content.replace("def generar_esc_pos_ticket(venta, detalles=None):", """def generar_esc_pos_ticket(venta, detalles=None):
    formato = '80mm'
    if venta.estacion_trabajo and venta.estacion_trabajo.formato_impresion:
        formato = venta.estacion_trabajo.formato_impresion

    width = 48
    logo_w = 300
    timbre_w = 512
    if formato == '58mm':
        width = 32
        logo_w = 200
        timbre_w = 384
""")
    
    # Replace fixed max_width in logo
    new_content = new_content.replace("logo_hex = img_to_escpos_hex(venta.empresa.logo.path, max_width=300)", 
                                      "logo_hex = img_to_escpos_hex(venta.empresa.logo.path, max_width=logo_w)")

    # Replace fixed width dashes and alignments
    new_content = new_content.replace('lineas.append("-" * 40)', 'lineas.append("-" * width)')
    new_content = new_content.replace('lineas.append(f"{empresa.upper()[:40]}")', 'lineas.append(f"{empresa.upper()[:width]}")')
    new_content = new_content.replace('lineas.append(venta.sucursal.direccion[:40])', 'lineas.append(venta.sucursal.direccion[:width])')
    new_content = new_content.replace('lineas.append(f"Cliente: {venta.cliente.nombre[:40]}")', 'lineas.append(f"Cliente: {venta.cliente.nombre[:width]}")')

    # Replace Items headers
    items_header_old = "lineas.append(f\"{'CANT':<4} {'DESCRIPCION':<24} {'TOTAL':>10}\")"
    items_header_new = """
    name_w = width - 4 - 10 - 1
    lineas.append(f"{'CANT':<4} {'DESCRIPCION':<{name_w}} {'TOTAL':>10}")
"""
    new_content = new_content.replace(items_header_old, items_header_new)

    # Replace Items loop
    items_loop_old = """
    for d_item in detalles:
        nombre = d_item.articulo.nombre[:24]
        cant = int(d_item.cantidad) if d_item.cantidad == int(d_item.cantidad) else round(d_item.cantidad, 2)
        total_item = int(d_item.precio_total)
        total_item_str = f"{total_item:,}".replace(',', '.')
        linea_item = f"{cant:<4} {nombre:<24} ${total_item_str:>9}"
        lineas.append(linea_item)
"""
    items_loop_new = """
    for d_item in detalles:
        name_w = width - 4 - 10 - 1
        nombre = d_item.articulo.nombre[:name_w]
        cant = int(d_item.cantidad) if d_item.cantidad == int(d_item.cantidad) else round(d_item.cantidad, 2)
        total_item = int(d_item.precio_total)
        total_item_str = f"{total_item:,}".replace(',', '.')
        linea_item = f"{cant:<4} {nombre:<{name_w}} ${total_item_str:>9}"
        lineas.append(linea_item)
"""
    new_content = new_content.replace(items_loop_old, items_loop_new)

    # Replace Timbre
    new_content = new_content.replace("timbre_hex = img_to_escpos_hex(dte.timbre_pdf417.path, max_width=512)",
                                      "timbre_hex = img_to_escpos_hex(dte.timbre_pdf417.path, max_width=timbre_w)")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Patched impresion_utils")

patch_impresion_utils()
