import sys

def patch_impresion_utils():
    filepath = 'caja/impresion_utils.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old_logic = """    formato = '80mm'
    if venta.estacion_trabajo and venta.estacion_trabajo.formato_impresion:
        formato = venta.estacion_trabajo.formato_impresion

    width = 48
    logo_w = 300
    timbre_w = 512
    if formato == '58mm':
        width = 32
        logo_w = 200
        timbre_w = 384"""
        
    new_logic = """    # Obtener configuración de empresa
    formato_impresora = 'termica_80'
    
    if venta.tipo_documento == 'factura' and hasattr(venta.empresa, 'impresora_factura'):
        formato_impresora = venta.empresa.impresora_factura
    elif venta.tipo_documento == 'boleta' and hasattr(venta.empresa, 'impresora_boleta'):
        formato_impresora = venta.empresa.impresora_boleta
    elif venta.tipo_documento == 'guia' and hasattr(venta.empresa, 'impresora_guia'):
        formato_impresora = venta.empresa.impresora_guia
    elif venta.tipo_documento == 'nota_credito' and hasattr(venta.empresa, 'impresora_nota_credito'):
        formato_impresora = venta.empresa.impresora_nota_credito
    elif venta.tipo_documento == 'nota_debito' and hasattr(venta.empresa, 'impresora_nota_debito'):
        formato_impresora = venta.empresa.impresora_nota_debito
    elif venta.tipo_documento == 'cotizacion' and hasattr(venta.empresa, 'impresora_cotizacion'):
        formato_impresora = venta.empresa.impresora_cotizacion
    elif hasattr(venta.empresa, 'impresora_vale'):
        formato_impresora = venta.empresa.impresora_vale

    width = 48
    logo_w = 300
    timbre_w = 512
    if formato_impresora == 'termica_58':
        width = 32
        logo_w = 200
        timbre_w = 384"""

    if old_logic in content:
        content = content.replace(old_logic, new_logic)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched impresion_utils")
    else:
        print("Could not find logic to replace")

patch_impresion_utils()
