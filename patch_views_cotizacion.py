import sys

def patch_views():
    filepath = 'ventas/views.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add 'vale' to the array
    content = content.replace("tipo_venta in ['factura', 'boleta', 'guia']:", "tipo_venta in ['factura', 'boleta', 'guia', 'vale']:")
    
    # Fix the COT- parsing
    old_parsing = """            if ultima_venta and ultima_venta.numero_venta and ultima_venta.numero_venta != 'TEMP':
                try:
                    ultimo_numero = int(ultima_venta.numero_venta)
                    numero_nueva_venta = f"{ultimo_numero + 1:06d}"
                except ValueError:
                    # Si no se puede convertir, usar un número basado en la cotización
                    numero_nueva_venta = f"V{cotizacion.numero_venta}" """
                    
    new_parsing = """            if ultima_venta and ultima_venta.numero_venta and ultima_venta.numero_venta != 'TEMP':
                num_str = ultima_venta.numero_venta.replace('COT-', '')
                try:
                    ultimo_numero = int(num_str)
                    numero_nueva_venta = f"{ultimo_numero + 1:06d}"
                except ValueError:
                    # Si no se puede convertir, usar un número basado en la cotización
                    numero_nueva_venta = f"V{cotizacion.numero_venta}" """
    content = content.replace(old_parsing, new_parsing)
    
    # Add to context
    old_context = """        'tipos_venta': [
            ('factura', 'Factura'),
            ('boleta', 'Boleta'),
            ('guia', 'Guía de Despacho'),
        ]"""
    new_context = """        'tipos_venta': [
            ('factura', 'Factura'),
            ('boleta', 'Boleta'),
            ('guia', 'Guía de Despacho'),
            ('vale', 'Vale / Ticket Facturable'),
        ]"""
    content = content.replace(old_context, new_context)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
patch_views()
