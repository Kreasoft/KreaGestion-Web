def img_to_escpos_hex(image_path, max_width=384):
    """
    Convierte una imagen (por ejemplo el PDF417 o Logo) a comandos ESC/POS Raster (GS v 0).
    max_width=384 es para papel 58mm (aprox). Para 80mm suele ser 512.
    """
    try:
        from PIL import Image, ImageChops
        img = Image.open(image_path)
        
        # Crop whitespace margins
        if img.mode != 'RGB':
            img = img.convert('RGB')
        bg = Image.new(img.mode, img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox)
        
        # Resize to fit paper width if it's too large, or scale it nicely
        if img.width > max_width or img.width < max_width:
            ratio = max_width / img.width
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
        
        # Ensure width is multiple of 8
        width = img.width
        if width % 8 != 0:
            width = width + (8 - (width % 8))
            new_img = Image.new('RGB', (width, img.height), 'white')
            new_img.paste(img, (0, 0))
            img = new_img
            
        img = img.convert('1') # 1-bit black and white
        width, height = img.size
        bytes_per_row = width // 8
        
        # GS v 0 0 xL xH yL yH
        header = b"\x1d\x76\x30\x00" + bytes([bytes_per_row % 256, bytes_per_row // 256, height % 256, height // 256])
        
        # Pixels
        pixel_data = bytearray()
        pixels = img.load()
        
        for y in range(height):
            for x_byte in range(bytes_per_row):
                b = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if x < width:
                        if pixels[x, y] == 0:
                            b |= (1 << (7 - bit))
                pixel_data.append(b)
                
        final_bytes = header + pixel_data
        return "".join([f"\\x{b:02x}" for b in final_bytes])
    except Exception as e:
        print(f"Error convirtiendo imagen a ESC/POS: {e}")
        return ""

def _formatear_monto_ticket(monto):
    return f"{int(round(float(monto or 0))):,}".replace(",", ".")


def _agregar_linea_monto(lineas, nombre, monto, width):
    monto_texto = f"${_formatear_monto_ticket(monto)}"
    nombre = (nombre or "SIN FORMA").upper()
    espacio_nombre = max(8, width - len(monto_texto) - 1)
    lineas.append(f"{nombre[:espacio_nombre]:<{espacio_nombre}} {monto_texto}")


def obtener_formas_pago_ticket(venta):
    pagos = []
    try:
        from caja.models import MovimientoCaja

        movimientos = (
            MovimientoCaja.objects
            .filter(venta=venta, tipo__in=['venta', 'ingreso'])
            .select_related('forma_pago')
            .order_by('id')
        )

        acumulados = {}
        orden = []
        for mov in movimientos:
            if not mov.forma_pago:
                continue

            key = mov.forma_pago_id
            if key not in acumulados:
                acumulados[key] = {
                    'nombre': mov.forma_pago.nombre,
                    'monto': 0,
                }
                orden.append(key)

            acumulados[key]['monto'] += abs(mov.monto or 0)

        pagos = [acumulados[key] for key in orden]
    except Exception:
        pagos = []

    if not pagos and getattr(venta, 'forma_pago', None):
        pagos.append({
            'nombre': venta.forma_pago.nombre,
            'monto': venta.total,
        })

    return pagos


def generar_esc_pos_ticket(venta, detalles=None):
    # Obtener configuración de empresa
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

    width = 42        # Fuente A en 80mm: máximo seguro 42 caracteres
    logo_w = 300
    timbre_w = 512
    if formato_impresora == 'termica_58':
        width = 30    # Fuente A en 58mm: máximo seguro 30 caracteres
        logo_w = 200
        timbre_w = 384

    """
    Genera un string con comandos ESC/POS profesionales para imprimir directo a la ticketera.
    Ajustado para Fuente A (máx 40 caracteres) en 80mm e incluye Código de Barras / Timbre DTE.
    """
    if detalles is None:
        detalles = venta.ventadetalle_set.all()
    import datetime

    # Comandos ESC/POS (raw strings para no corromper la BD con null bytes)
    INIT = r"\x1B\x40"
    COMPACT_SPACING = r"\x1B\x33\x18" # ESC 3 24 (Espaciado de linea ajustado a 24 puntos)
    
    # Alineacion
    ALIGN_LEFT = r"\x1B\x61\x00"
    ALIGN_CENTER = r"\x1B\x61\x01"
    ALIGN_RIGHT = r"\x1B\x61\x02"
    
    # Texto
    BOLD_ON = r"\x1B\x45\x01"
    BOLD_OFF = r"\x1B\x45\x00"
    
    # Tamaños
    SIZE_NORMAL = r"\x1B\x21\x00"
    SIZE_DOUBLE_H = r"\x1B\x21\x10"
    SIZE_DOUBLE_W = r"\x1B\x21\x20"
    SIZE_DOUBLE_HW = r"\x1B\x21\x30"
    
    # Código de Barras CODE39
    BARCODE_SETUP = r"\x1D\x48\x02\x1D\x68\x40\x1D\x77\x03"
    CUT_PAPER = r"\x1D\x56\x00"

    empresa = venta.empresa.nombre if venta.empresa.nombre else venta.empresa.razon_social
    rut_empresa = venta.empresa.rut if venta.empresa.rut else ""
    fecha = venta.fecha.strftime('%d/%m/%Y %H:%M') if venta.fecha else datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    
    # Buscar DTE asociado
    dte = None
    if hasattr(venta, 'dte_asociado'):
        dte = venta.dte_asociado
    
    lineas = []
    lineas.append(INIT)
    lineas.append(COMPACT_SPACING)
    
    # LOGO (si existe)
    if venta.empresa.logo:
        logo_hex = img_to_escpos_hex(venta.empresa.logo.path, max_width=logo_w)
        if logo_hex:
            lineas.append(ALIGN_CENTER)
            lineas.append(logo_hex)
    
    # ENCABEZADO (Centrado)
    lineas.append(ALIGN_CENTER)
    lineas.append(BOLD_ON)
    if not venta.empresa.logo:
        lineas.append(SIZE_DOUBLE_HW)
        lineas.append(f"{empresa.upper()[:15]}")
        lineas.append(SIZE_NORMAL)
    else:
        lineas.append(f"{empresa.upper()[:width]}")
    lineas.append(BOLD_OFF)
    
    if rut_empresa:
        lineas.append(f"RUT: {rut_empresa}")
    if venta.sucursal and venta.sucursal.direccion:
        lineas.append(venta.sucursal.direccion[:width])
    
    # TIPO DE DOCUMENTO
    lineas.append(BOLD_ON)
    lineas.append(SIZE_DOUBLE_H)
    if dte:
        tipo_doc = dte.get_tipo_dte_display().upper() if hasattr(dte, 'get_tipo_dte_display') else "DOCUMENTO TRIBUTARIO"
        folio = dte.folio
    else:
        tipo_doc = venta.tipo_documento.upper() if venta.tipo_documento else "VALE"
        if tipo_doc == "TICKET":
            tipo_doc = "VALE INTERNO"
        folio = venta.numero_venta
        
    lineas.append(f"{tipo_doc} NRO: {folio}")
    lineas.append(SIZE_NORMAL)
    lineas.append(BOLD_OFF)
    
    # DATOS DE VENTA
    lineas.append(ALIGN_LEFT)
    lineas.append(f"Fecha: {fecha}")
    if venta.vendedor:
        lineas.append(f"Atendido por: {venta.vendedor.nombre[:20]}")
    if dte and venta.numero_venta:
        lineas.append(f"VALE REF: {venta.numero_venta}")
    
    if getattr(venta, 'cliente', None) and venta.cliente.nombre != "Cliente Genérico":
        lineas.append(f"Cliente: {venta.cliente.nombre[:width]}")
    
    lineas.append("-" * width)
    lineas.append(BOLD_ON)
    
    name_w = width - 4 - 10 - 2
    lineas.append(f"{'CANT':<4} {'DESCRIPCION':<{name_w}} {'TOTAL':>10}")

    lineas.append(BOLD_OFF)
    lineas.append("-" * width)
    
    # ITEMS
    for d_item in detalles:
        name_w = width - 4 - 10 - 2
        nombre = d_item.articulo.nombre[:name_w]
        cant = int(d_item.cantidad) if d_item.cantidad == int(d_item.cantidad) else round(d_item.cantidad, 2)
        total_item = int(d_item.precio_total)
        total_item_str = f"{total_item:,}".replace(',', '.')
        linea_item = f"{cant:<4} {nombre:<{name_w}} ${total_item_str:>9}"
        lineas.append(linea_item)
    
    lineas.append("-" * width)
    
    # FORMAS DE PAGO
    formas_pago_ticket = obtener_formas_pago_ticket(venta)
    if formas_pago_ticket:
        lineas.append(ALIGN_LEFT)
        if len(formas_pago_ticket) == 1:
            pago = formas_pago_ticket[0]
            lineas.append(f"MEDIO PAGO: {pago['nombre'].upper()}")
            _agregar_linea_monto(lineas, "MONTO PAGO", pago['monto'], width)
        else:
            lineas.append(BOLD_ON)
            lineas.append("PAGO COMBINADO")
            lineas.append(BOLD_OFF)
            for pago in formas_pago_ticket:
                _agregar_linea_monto(lineas, pago['nombre'], pago['monto'], width)

            total_pagado = sum(pago['monto'] for pago in formas_pago_ticket)
            _agregar_linea_monto(lineas, "TOTAL PAGADO", total_pagado, width)
        lineas.append("-" * width)
        
    # TOTALES
    lineas.append(ALIGN_RIGHT)
    lineas.append(BOLD_ON)
    neto = int(venta.neto or 0)
    iva = int(venta.iva or 0)
    total = int(venta.total)
    neto_str = f"{neto:,}".replace(',', '.')
    iva_str = f"{iva:,}".replace(',', '.')
    total_str = f"{total:,}".replace(',', '.')
    lineas.append(f"NETO:  ${neto_str}")
    lineas.append(f"IVA:   ${iva_str}")
    lineas.append(SIZE_DOUBLE_HW)
    lineas.append(f"TOTAL: ${total_str}")
    lineas.append(SIZE_NORMAL)
    lineas.append(BOLD_OFF)
    
    lineas.append(ALIGN_CENTER)
    
    # TIMBRE DTE o CÓDIGO DE BARRAS
    if dte and dte.timbre_pdf417:
        timbre_hex = img_to_escpos_hex(dte.timbre_pdf417.path, max_width=timbre_w)
        if timbre_hex:
            lineas.append(timbre_hex)
            lineas.append(BOLD_ON)
            lineas.append("TIMBRE ELECTRONICO SII")
            lineas.append(BOLD_OFF)
            lineas.append(f"Res. {dte.empresa.get_resolucion_sii()} de {dte.empresa.get_anio_resolucion_sii()}" if hasattr(dte.empresa, 'get_resolucion_sii') else "Res. 80 de 2014")
            lineas.append("Verifique documento en sii.cl")
    else:
        # Solo vale interno
        num_vale = str(venta.numero_venta).zfill(6)
        lineas.append("")
        lineas.append(ALIGN_CENTER)
        cmd_barcode = f"{BARCODE_SETUP}\\x1D\\x6B\\x04{num_vale}\\x00"
        lineas.append(cmd_barcode)
        lineas.append("")
    
    lineas.append("Gracias por su preferencia!")
    
    # 5 lineas de espacio final para avanzar el papel hasta el cortador
    lineas.append("")
    lineas.append("")
    lineas.append("")
    lineas.append("")
    lineas.append("")
    lineas.append(CUT_PAPER)
    
    contenido_unico = "\n".join(lineas) + "\n"
    
    # Determinar cantidad de copias
    copias = 1
    if venta.estacion_trabajo:
        tipo_busqueda = dte.get_tipo_dte_display() if dte and hasattr(dte, 'get_tipo_dte_display') else venta.tipo_documento
        tipo_busqueda = (tipo_busqueda or '').lower()
        if 'boleta' in tipo_busqueda:
            tipo_busqueda = 'boleta'
        elif 'factura' in tipo_busqueda:
            tipo_busqueda = 'factura'
        elif tipo_busqueda == 'ticket' and getattr(venta, 'tipo_documento_planeado', '') == 'vale':
            tipo_busqueda = 'vale'
        copias = venta.estacion_trabajo.get_copias_por_tipo(tipo_busqueda) or 1
        
    return contenido_unico * copias
