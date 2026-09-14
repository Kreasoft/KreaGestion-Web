import logging
import textwrap

from django.db import transaction

logger = logging.getLogger("django")

def img_to_escpos_hex(image_path, max_width=384, max_height=None, keep_modules=False):
    """
    Convierte una imagen (PDF417 o logo) a raster ESC/POS (GS v 0).
    keep_modules=True evita aplastar el timbre (si no, se ve como recuadros).
    """
    try:
        from PIL import Image, ImageChops
        img = Image.open(image_path)

        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            mask = img.split()[-1] if img.mode in ('RGBA', 'LA') else img.convert('RGBA').split()[-1]
            bg.paste(img, mask=mask)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        bg = Image.new('RGB', img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox)

        resample = Image.Resampling.NEAREST if keep_modules else Image.Resampling.LANCZOS
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, max(1, int(img.height * ratio))), resample)
        elif keep_modules and img.width < max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, max(1, int(img.height * ratio))), Image.Resampling.NEAREST)
        if max_height and img.height > max_height:
            ratio = max_height / img.height
            img = img.resize((max(1, int(img.width * ratio)), max_height), resample)

        return _bitmap_a_escpos_hex(img)
    except Exception as e:
        print(f"Error convirtiendo imagen a ESC/POS: {e}")
        return ""


def _bitmap_a_escpos_hex(img):
    """Convierte una imagen PIL a raster ESC/POS (GS v 0) en escapes \\xHH."""
    from PIL import Image

    if img.mode != "1":
        if img.mode != "RGB":
            img = img.convert("RGB")
        width = img.width
        if width % 8 != 0:
            width = width + (8 - (width % 8))
            padded = Image.new("RGB", (width, img.height), "white")
            padded.paste(img, (0, 0))
            img = padded
        img = img.convert("1")

    width, height = img.size
    if width % 8 != 0:
        padded = Image.new("1", (width + (8 - width % 8), height), 1)
        padded.paste(img, (0, 0))
        img = padded
        width, height = img.size

    bytes_per_row = width // 8
    header = b"\x1d\x76\x30\x00" + bytes([
        bytes_per_row % 256, bytes_per_row // 256,
        height % 256, height // 256,
    ])
    pixel_data = bytearray()
    pixels = img.load()
    for y in range(height):
        for x_byte in range(bytes_per_row):
            b = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if x < width and pixels[x, y] == 0:
                    b |= (1 << (7 - bit))
            pixel_data.append(b)
    return "".join(f"\\x{byte:02x}" for byte in (header + pixel_data))


# CODE128: 0-106 (Stop = 106, patrón de 7 anchos)
_CODE128_PATRONES = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
]


def _barcode_code128_escpos(texto, target_width=384, bar_height=92):
    """
    CODE128 a ancho de papel, como raster GS v 0.
    Sin texto HRI: el folio ya va en el encabezado.
    """
    from PIL import Image, ImageDraw

    data = "".join(ch for ch in str(texto or "") if 32 <= ord(ch) <= 126)[:22]
    if not data:
        return ""

    valores = [104]  # Start B
    valores.extend(ord(ch) - 32 for ch in data)
    checksum = valores[0]
    for i, valor in enumerate(valores[1:], start=1):
        checksum += i * valor
    valores.append(checksum % 103)
    valores.append(106)  # Stop

    module = 2
    quiet = module * 10
    ancho = quiet * 2
    for valor in valores:
        for w in _CODE128_PATRONES[valor]:
            ancho += int(w) * module

    alto = max(64, int(bar_height))
    img = Image.new("RGB", (ancho, alto), "white")
    draw = ImageDraw.Draw(img)
    x = quiet
    for valor in valores:
        for idx, w in enumerate(_CODE128_PATRONES[valor]):
            px = int(w) * module
            if idx % 2 == 0:
                draw.rectangle([x, 0, x + px - 1, alto - 1], fill="black")
            x += px

    destino = max(200, int(target_width))
    if img.width != destino:
        img = img.resize((destino, alto), Image.Resampling.NEAREST)

    return _bitmap_a_escpos_hex(img)

def _formatear_monto_ticket(monto):
    return f"{int(round(float(monto or 0))):,}".replace(",", ".")


def _escpos_texto(texto):
    """
    Convierte texto a escapes ESC/POS de un byte (CP850).
    El agente interpreta \\xHH y latin-1; si se manda UTF-8, las letras con
    acento (ó, ñ, é…) ocupan 2 bytes y la ticketera las omite.
    """
    if not texto:
        return ""
    partes = []
    for ch in str(texto):
        if ch == "\\":
            partes.append("\\\\")
            continue
        try:
            encoded = ch.encode("cp850")
        except UnicodeEncodeError:
            encoded = ch.encode("cp850", errors="replace")
        for byte in encoded:
            if 32 <= byte <= 126:
                partes.append(chr(byte))
            else:
                partes.append("\\x%02x" % byte)
    return "".join(partes)


def _preparar_linea_escpos(linea):
    if not linea or linea.startswith("\\x"):
        return linea
    return _escpos_texto(linea)


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


def _escpos_campo(lineas, etiqueta, valor, width):
    texto = (valor or '').strip() or '-'
    prefijo = f"{etiqueta}: "
    espacio = max(8, width - len(prefijo))
    if len(texto) <= espacio:
        lineas.append(prefijo + texto)
        return
    lineas.append(prefijo + texto[:espacio])
    for tramo in textwrap.wrap(texto[espacio:], width=width) or []:
        lineas.append(tramo)


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
    barcode_w = 384
    timbre_w = 512
    if formato_impresora == 'termica_58':
        width = 30    # Fuente A en 58mm: máximo seguro 30 caracteres
        logo_w = 200
        barcode_w = 256
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
    CODEPAGE_PC850 = r"\x1B\x74\x02"
    CHARSET_SPAIN = r"\x1B\x52\x0C"
    COMPACT_SPACING = r"\x1B\x33\x1C" # ESC 3 28 (un poco más de aire entre líneas)
    
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
    
    # Avance corto hasta el cortador (menos papel que ESC d 8)
    FEED_CUT = r"\x1B\x64\x04"
    CUT_PAPER = r"\x1D\x56\x00"

    empresa = (venta.empresa.nombre or venta.empresa.razon_social or "")
    rut_empresa = venta.empresa.rut if venta.empresa.rut else ""
    if venta.fecha:
        try:
            fecha = venta.fecha.strftime('%d-%m-%Y %H:%M')
        except (TypeError, ValueError):
            fecha = venta.fecha.strftime('%d-%m-%Y')
    else:
        fecha = datetime.datetime.now().strftime('%d-%m-%Y %H:%M')
    
    # Buscar DTE asociado (no asignar venta.dte_asociado: es property de solo lectura)
    dte = getattr(venta, '_dte_para_ticket', None)
    if not dte:
        try:
            dte = venta.dte_asociado
        except Exception:
            dte = None
    if not dte:
        try:
            dte = venta.dte
        except Exception:
            dte = None
    if not dte:
        try:
            from caja.models import VentaProcesada
            venta_proc = (
                VentaProcesada.objects
                .filter(venta_final=venta, dte_generado__isnull=False)
                .select_related('dte_generado')
                .order_by('-id')
                .first()
            )
            if venta_proc:
                dte = venta_proc.dte_generado
        except Exception:
            dte = None
    if not dte:
        try:
            from facturacion_electronica.models import DocumentoTributarioElectronico
            dte = (
                DocumentoTributarioElectronico.objects
                .filter(orden_despacho=venta)
                .order_by('-id')
                .first()
            )
        except Exception:
            dte = None
    if dte and getattr(dte, 'fecha_emision', None):
        fecha = dte.fecha_emision.strftime('%d-%m-%Y')
    
    lineas = []
    lineas.append(INIT)
    lineas.append(CODEPAGE_PC850)
    lineas.append(CHARSET_SPAIN)
    lineas.append(COMPACT_SPACING)

    # Logo solo en DTE: en vale/ticket el raster se come el texto y no sale papel.
    usar_logo = bool(dte) and bool(getattr(venta.empresa, "logo", None))
    if usar_logo:
        try:
            logo_hex = img_to_escpos_hex(venta.empresa.logo.path, max_width=logo_w, max_height=100)
            if logo_hex:
                lineas.append(ALIGN_CENTER + logo_hex)
            else:
                usar_logo = False
        except Exception:
            usar_logo = False

    # ENCABEZADO (Centrado - pegar inmediatamente tras el logo con mínimo espacio)
    if not usar_logo:
        lineas.append(ALIGN_CENTER + BOLD_ON + SIZE_DOUBLE_HW + _escpos_texto(empresa.upper()[:15]) + SIZE_NORMAL + BOLD_OFF)
    else:
        # Pegar el nombre de la empresa directamente tras el logo sin INIT ni saltos de línea intermedios
        lineas.append(ALIGN_CENTER + COMPACT_SPACING + BOLD_ON + _escpos_texto(empresa.upper()[:width]) + BOLD_OFF)

    if rut_empresa:
        lineas.append(f"RUT: {rut_empresa}")
    dir_empresa = (venta.sucursal.direccion if venta.sucursal and venta.sucursal.direccion else getattr(venta.empresa, 'direccion', '')) or ''
    if dir_empresa:
        lineas.append(dir_empresa[:width])
    comuna_emp = getattr(venta.sucursal, 'comuna', '') if venta.sucursal else getattr(venta.empresa, 'comuna', '')
    ciudad_emp = getattr(venta.sucursal, 'ciudad', '') if venta.sucursal else getattr(venta.empresa, 'ciudad', '')
    ubica = f"{comuna_emp}, {ciudad_emp}".strip(', ') if (comuna_emp or ciudad_emp) else ''
    if ubica:
        lineas.append(ubica[:width])
    fono_emp = getattr(venta.empresa, 'telefono', '') or ''
    if fono_emp:
        lineas.append(f"Fono: {fono_emp}"[:width])
    email_emp = getattr(venta.empresa, 'email', '') or ''
    if email_emp:
        lineas.append(f"Email: {email_emp}"[:width])
    web_emp = getattr(venta.empresa, 'sitio_web', '') or ''
    if web_emp:
        lineas.append(f"Web: {web_emp}"[:width])
    
    # TIPO DE DOCUMENTO
    lineas.append(BOLD_ON)
    lineas.append(SIZE_DOUBLE_H)
    if dte:
        tipo_doc = dte.get_tipo_dte_display().upper() if hasattr(dte, 'get_tipo_dte_display') else "DOCUMENTO TRIBUTARIO"
        folio = dte.folio
    else:
        planeado = (getattr(venta, 'tipo_documento_planeado', '') or '').lower()
        tipo_real = (venta.tipo_documento or 'vale').lower()
        if tipo_real == 'ticket':
            tipo_doc = "TICKET FACTURABLE"
        elif tipo_real == 'vale' or planeado == 'vale':
            tipo_doc = "VALE INTERNO"
        else:
            tipo_doc = tipo_real.upper()
        folio = venta.numero_venta
        
    lineas.append(f"{tipo_doc} NRO: {folio}")
    lineas.append(SIZE_NORMAL)
    lineas.append(BOLD_OFF)
    if not dte and (getattr(venta, 'tipo_documento', '') or '').lower() == 'ticket':
        destino = (getattr(venta, 'tipo_documento_planeado', '') or '').lower()
        destino_txt = {
            'boleta': 'BOLETA',
            'factura': 'FACTURA',
            'guia': 'GUIA DE DESPACHO',
            'vale': 'VALE INTERNO',
            'cotizacion': 'COTIZACION',
        }.get(destino, (destino or '').upper())
        if destino_txt:
            lineas.append(f"Se facturara como: {destino_txt}")
    
    # DATOS DE VENTA
    lineas.append(ALIGN_LEFT)
    lineas.append(f"Fecha: {fecha}")
    fecha_venc = getattr(venta, 'fecha_vencimiento', None)
    if fecha_venc:
        try:
            venc_txt = fecha_venc.strftime('%d-%m-%Y')
        except Exception:
            venc_txt = str(fecha_venc)
        lineas.append(f"Vence: {venc_txt}")
    if venta.vendedor:
        lineas.append(f"Atendido por: {(venta.vendedor.nombre or '')[:20]}")
    estacion_imp = getattr(venta, 'estacion_trabajo', None)
    if estacion_imp:
        est_txt = ' · '.join(
            part for part in (str(estacion_imp.numero or '').strip(), str(estacion_imp.nombre or '').strip()) if part
        )
        if est_txt:
            lineas.append(f"Estacion: {est_txt[:width - 10]}")
    if dte and venta.numero_venta:
        lineas.append(f"VALE REF: {venta.numero_venta}")
    if dte and getattr(dte, 'tipo_dte', '') == '52':
        tipo_traslado = (getattr(dte, 'tipo_traslado', None) or getattr(venta, 'tipo_despacho', None) or '').strip()
        traslado_display = ''
        if tipo_traslado and hasattr(dte, 'get_tipo_traslado_display'):
            traslado_display = dte.get_tipo_traslado_display()
        elif getattr(venta, 'tipo_despacho', None) and hasattr(venta, 'get_tipo_despacho_display'):
            traslado_display = venta.get_tipo_despacho_display()

        if traslado_display:
            traslado_linea = f"Traslado: {tipo_traslado} - {traslado_display}" if tipo_traslado else f"Traslado: {traslado_display}"
            for tramo in textwrap.wrap(traslado_linea, width=width) or [traslado_linea[:width]]:
                lineas.append(tramo)
        patente = (getattr(dte, 'patente_transporte', None) or getattr(getattr(dte, 'vehiculo', None), 'patente', None) or '')
        if patente:
            lineas.append(f"Patente: {patente}")
        nombre_chofer = (getattr(dte, 'nombre_chofer', None) or getattr(getattr(dte, 'chofer', None), 'nombre', None) or '')
        if nombre_chofer:
            lineas.append(f"Chofer: {nombre_chofer[:width-8]}")
        fecha_salida = getattr(dte, 'fecha_salida', None)
        if fecha_salida:
            hora_salida = getattr(dte, 'hora_salida', None)
            try:
                salida_txt = fecha_salida.strftime('%d-%m-%Y')
            except Exception:
                salida_txt = str(fecha_salida)
            if hora_salida:
                try:
                    salida_txt += ' ' + hora_salida.strftime('%H:%M')
                except Exception:
                    pass
            lineas.append(f"Salida: {salida_txt}")
    
    tipo_doc = (getattr(venta, 'tipo_documento', '') or '').lower()
    tipo_dte = str(getattr(dte, 'tipo_dte', '') or '') if dte else ''
    es_guia_o_factura = tipo_doc in ('factura', 'factura_electronica', 'guia') or tipo_dte in ('33', '34', '52')
    cliente = getattr(venta, 'cliente', None)
    bodega_txt = ''
    try:
        from facturacion_electronica.views_dte import resolver_bodega_documento
        bodega_txt = resolver_bodega_documento(venta=venta, dte=dte)
    except Exception:
        bodega_txt = ''
    if es_guia_o_factura or (cliente and cliente.nombre != "Cliente Genérico"):
        try:
            from facturacion_electronica.views_dte import _build_receptor_display
            receptor = _build_receptor_display(dte, fallback_cliente=cliente)
            _escpos_campo(lineas, "Cliente", receptor.nombre, width)
            _escpos_campo(lineas, "RUT", receptor.rut, width)
            _escpos_campo(lineas, "Direccion", receptor.direccion, width)
            _escpos_campo(lineas, "Comuna", receptor.comuna, width)
            _escpos_campo(lineas, "Ciudad", receptor.ciudad, width)
            _escpos_campo(lineas, "Bodega", bodega_txt, width)
        except Exception:
            if cliente:
                lineas.append(f"Cliente: {cliente.nombre[:width]}")
                rut_cli = getattr(cliente, 'rut', '') or ''
                if rut_cli:
                    lineas.append(f"RUT: {rut_cli[:width]}")
            if bodega_txt:
                _escpos_campo(lineas, "Bodega", bodega_txt, width)
    elif bodega_txt:
        _escpos_campo(lineas, "Bodega", bodega_txt, width)
    
    name_w = width - 4 - 10 - 2
    lineas.append("-" * width)
    lineas.append(BOLD_ON + f"{'CANT':<4} {'DESCRIPCION':<{name_w}} {'TOTAL':>10}")
    lineas.append(BOLD_OFF + ("-" * width))
    
    # ITEMS
    for d_item in detalles:
        name_w = width - 4 - 10 - 2
        nombre = (getattr(d_item.articulo, "nombre", None) or "")[:name_w]
        cant = int(d_item.cantidad) if d_item.cantidad == int(d_item.cantidad) else round(d_item.cantidad, 2)
        total_item = int(d_item.precio_total)
        total_item_str = f"{total_item:,}".replace(',', '.')
        linea_item = f"{cant:<4} {nombre:<{name_w}} ${total_item_str:>9}"
        lineas.append(linea_item)
    
    lineas.append("-" * width)
    
    # FORMAS DE PAGO
    formas_pago_ticket = obtener_formas_pago_ticket(venta)
    if formas_pago_ticket:
        if len(formas_pago_ticket) == 1:
            pago = formas_pago_ticket[0]
            lineas.append(ALIGN_LEFT + f"MEDIO PAGO: {(pago.get('nombre') or '').upper()}")
            _agregar_linea_monto(lineas, "MONTO PAGO", pago['monto'], width)
        else:
            lineas.append(ALIGN_LEFT + BOLD_ON + "PAGO COMBINADO" + BOLD_OFF)
            for pago in formas_pago_ticket:
                _agregar_linea_monto(lineas, pago['nombre'], pago['monto'], width)

            total_pagado = sum(pago['monto'] for pago in formas_pago_ticket)
            _agregar_linea_monto(lineas, "TOTAL PAGADO", total_pagado, width)
        lineas.append("-" * width)

    # TOTALES: raya de separación + un respiro chico, sin líneas en blanco extra
    neto = int(venta.neto or 0)
    iva = int(venta.iva or 0)
    total = int(venta.total)
    neto_str = f"{neto:,}".replace(',', '.')
    iva_str = f"{iva:,}".replace(',', '.')
    total_str = f"{total:,}".replace(',', '.')
    lineas.append(ALIGN_RIGHT + BOLD_ON + SIZE_DOUBLE_H + f"NETO: ${neto_str}")
    lineas.append(f"IVA:  ${iva_str}")
    lineas.append(SIZE_DOUBLE_HW + f"TOTAL: ${total_str}")
    lineas.append(SIZE_NORMAL + BOLD_OFF)

    # OBSERVACIONES (si tiene)
    obs = (getattr(venta, 'observaciones', None) or '').strip()
    if obs:
        lineas.append("-" * width)
        lineas.append(ALIGN_LEFT + BOLD_ON + "OBSERVACION:" + BOLD_OFF)
        for tramo in textwrap.wrap(obs, width=width) or [obs[:width]]:
            lineas.append(tramo)

    # REFERENCIAS (guías consolidadas, órdenes de compra, etc.)
    refs = []
    try:
        from facturacion_electronica.views_dte import resolver_referencias_documento
        refs = resolver_referencias_documento(venta=venta, dte=dte)
    except Exception:
        pass

    if refs:
        lineas.append("-" * width)
        lineas.append(ALIGN_CENTER + BOLD_ON + "REFERENCIAS" + BOLD_OFF)
        lineas.append(ALIGN_LEFT)
        for r in refs:
            tipo_ref = r.get('tipo') or 'Doc Ref'
            folio_ref = r.get('folio') or ''
            fch_ref = r.get('fecha_display') or (r.get('fecha').strftime('%d-%m-%Y') if hasattr(r.get('fecha'), 'strftime') else str(r.get('fecha') or ''))
            razon_ref = r.get('razon') or ''

            lineas.append(f"Tipo: {tipo_ref}"[:width])
            lineas.append(f"Folio: {folio_ref} | Fecha: {fch_ref}"[:width])
            if razon_ref:
                lineas.append(f"Razon: {razon_ref}"[:width])
        lineas.append("-" * width)
    
    lineas.append(ALIGN_CENTER)
    
    # TIMBRE DTE o CÓDIGO DE BARRAS
    if dte and getattr(dte, 'timbre_pdf417', None):
        try:
            timbre_hex = img_to_escpos_hex(dte.timbre_pdf417.path, max_width=timbre_w, keep_modules=True)
            if timbre_hex:
                # Pegar raster + leyenda: el INIT post-gráfico deja un hueco enorme.
                lineas.append(ALIGN_CENTER + SIZE_NORMAL + timbre_hex)
                resolucion = (
                    f"Res. {dte.empresa.get_resolucion_sii()} de {dte.empresa.get_anio_resolucion_sii()}"
                    if hasattr(dte.empresa, 'get_resolucion_sii')
                    else "Res. 80 de 2014"
                )
                lineas.append(BOLD_ON + "TIMBRE ELECTRONICO SII")
                lineas.append(BOLD_OFF + resolucion)
                lineas.append("Verifique documento en sii.cl")
        except Exception:
            pass
    else:
        # Nota de venta: CODE128 ancho de papel, pegado al pie. Sin NRO ni INIT.
        barcode_hex = _barcode_code128_escpos(folio, target_width=barcode_w, bar_height=92)
        if barcode_hex:
            lineas.append(ALIGN_CENTER + barcode_hex)

    lineas.append("Gracias por su preferencia!")
    for tramo in textwrap.wrap("Desarrollado por www.kreasoft.cl", width=width) or ["Desarrollado por www.kreasoft.cl"]:
        lineas.append(tramo)

    lineas.append(SIZE_NORMAL)
    lineas.append(ALIGN_LEFT)
    lineas.append(FEED_CUT)
    lineas.append(CUT_PAPER)
    
    contenido_unico = "\n".join(_preparar_linea_escpos(linea) for linea in lineas) + "\n"
    
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


def resolver_caja_cola_impresion(empresa, estacion=None, sucursal=None, tipo_documento=None):
    """
    Destino de la cola de impresión.
    Vales/tickets: impresora de la estación (propia o compartida).
    DTE de caja: caja de cobro / vínculo / caja abierta.
    """
    from caja.models import AperturaCaja, Caja, CodigoVinculoImpresion
    from ventas.models import ensure_estacion_caja_impresion

    ensure_estacion_caja_impresion()

    tipo = (tipo_documento or '').lower()
    es_dte = tipo in ('dte', 'factura', 'boleta', 'guia', 'nota_credito', 'nota_debito')
    if not es_dte and estacion is not None:
        imp_vales = getattr(estacion, 'impresora_vales', None)
        if imp_vales is None and getattr(estacion, 'impresora_vales_id', None):
            from caja.models import ImpresoraAgente
            imp_vales = ImpresoraAgente.objects.select_related('caja').filter(
                pk=estacion.impresora_vales_id,
                empresa_id=estacion.empresa_id,
            ).first()
        if imp_vales is not None and getattr(imp_vales, 'caja', None) and getattr(imp_vales.caja, 'activo', True):
            return imp_vales.caja
        caja_est = getattr(estacion, 'caja_impresion', None)
        if caja_est is None and getattr(estacion, 'caja_impresion_id', None):
            caja_est = Caja.objects.filter(
                pk=estacion.caja_impresion_id, empresa_id=estacion.empresa_id, activo=True
            ).first()
        if caja_est and getattr(caja_est, 'activo', True):
            return caja_est

    qs_base = Caja.objects.filter(empresa=empresa, activo=True)
    qs_sucursal = qs_base.filter(sucursal=sucursal) if sucursal is not None else qs_base

    vinculo_qs = CodigoVinculoImpresion.objects.filter(empresa=empresa).select_related('caja')
    if sucursal is not None:
        vinculo_qs = vinculo_qs.filter(sucursal=sucursal)
    vinculo = vinculo_qs.order_by('-fecha_creacion').first()
    if vinculo and vinculo.caja_id and getattr(vinculo.caja, 'activo', False):
        return vinculo.caja

    ap_qs = (
        AperturaCaja.objects
        .filter(caja__empresa=empresa, estado='abierta')
        .select_related('caja')
        .order_by('-fecha_apertura')
    )
    if sucursal is not None:
        ap_suc = ap_qs.filter(caja__sucursal=sucursal).first()
        if ap_suc:
            return ap_suc.caja
    ap_abierta = ap_qs.first()
    if ap_abierta:
        return ap_abierta.caja

    return qs_sucursal.first() or qs_base.first()


def encolar_impresion_agente(empresa, venta, estacion=None, dte=None, tipo_documento=None):
    """
    Encola ESC/POS para el agente local.
    Si hay transacción abierta, espera al commit para generar el ticket
    con el DTE y los detalles ya persistidos.
    Devuelve True si se programó o creó el trabajo.
    """
    from caja.models import ColaImpresion
    from ventas.models import Venta

    if dte is not None:
        venta._dte_para_ticket = dte

    caja = resolver_caja_cola_impresion(
        empresa,
        estacion or getattr(venta, 'estacion_trabajo', None),
        getattr(venta, 'sucursal', None),
        tipo_documento=tipo_documento,
    )
    if not caja:
        logger.warning(
            "Impresión agente: no hay caja destino empresa=%s venta=%s",
            getattr(empresa, "id", None),
            getattr(venta, "id", None),
        )
        print("[IMPRESION] No hay caja destino para encolar")
        return False

    venta_id = venta.pk
    caja_id = caja.pk
    empresa_id = empresa.pk if empresa is not None else None
    dte_id = dte.pk if dte is not None else None
    tipo = tipo_documento or ('dte' if dte else 'vale')
    estacion_job = estacion or getattr(venta, 'estacion_trabajo', None)
    nombre_impresora = ''
    if (tipo or '').lower() not in ('dte', 'factura', 'boleta', 'guia', 'nota_credito', 'nota_debito'):
        imp_vales = getattr(estacion_job, 'impresora_vales', None) if estacion_job is not None else None
        if imp_vales is not None:
            nombre_impresora = imp_vales.nombre or ''
        elif estacion_job is not None:
            nombre_impresora = (estacion_job.info_impresora().get('nombre') or '')

    def _crear_trabajo():
        try:
            venta_db = (
                Venta.objects
                .select_related("empresa", "sucursal", "estacion_trabajo", "cliente", "vendedor")
                .prefetch_related("ventadetalle_set__articulo")
                .get(pk=venta_id)
            )
            if dte_id:
                from facturacion_electronica.models import DocumentoTributarioElectronico
                dte_db = DocumentoTributarioElectronico.objects.filter(pk=dte_id).first()
                if dte_db:
                    venta_db._dte_para_ticket = dte_db
            contenido = generar_esc_pos_ticket(venta_db)
            ColaImpresion.objects.create(
                caja_id=caja_id,
                empresa_id=empresa_id,
                venta_id=venta_id,
                tipo_documento=tipo,
                documento_id=dte_id or venta_id,
                contenido_raw=contenido,
                nombre_impresora=nombre_impresora,
                estado="pendiente",
            )
            print(f"[IMPRESION] Encolado venta={venta_id} caja={caja_id} tipo={tipo}")
            return True
        except Exception:
            logger.exception("Impresión agente: fallo al encolar venta=%s", venta_id)
            print(f"[IMPRESION] ERROR al encolar venta={venta_id}")
            import traceback
            traceback.print_exc()
            return False

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_crear_trabajo)
        return True
    return bool(_crear_trabajo())


AGENTE_TIMEOUT_SEGUNDOS = 30


def agente_impresion_en_linea(empresa, sucursal=None):
    """True si el agente consultó la cola hace menos de 30 segundos."""
    from datetime import timedelta

    from django.utils import timezone

    from caja.models import Caja

    if not empresa:
        return False
    limite = timezone.now() - timedelta(seconds=AGENTE_TIMEOUT_SEGUNDOS)
    qs = Caja.objects.filter(empresa=empresa, activo=True, agente_ultimo_ping__gte=limite)
    if sucursal is not None:
        qs = qs.filter(sucursal=sucursal)
    return qs.exists()
