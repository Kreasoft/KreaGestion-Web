"""Líneas de artículos de un DTE para la vista de detalle."""
import re
from decimal import Decimal, InvalidOperation


def _dec(valor, default='0'):
    try:
        return Decimal(str(valor if valor not in (None, '') else default).replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _linea(codigo, descripcion, cantidad, precio_unitario, total=None):
    qty = _dec(cantidad)
    if qty <= 0:
        return None
    precio = _dec(precio_unitario)
    monto = _dec(total) if total not in (None, '') else (qty * precio)
    return {
        'codigo': (codigo or '').strip(),
        'descripcion': (descripcion or '').strip() or 'Ítem',
        'cantidad': qty,
        'precio_unitario': precio,
        'total': monto,
    }


def _append(lineas, **kwargs):
    fila = _linea(**kwargs)
    if fila:
        lineas.append(fila)


def _desde_venta(venta):
    lineas = []
    if not venta:
        return lineas
    detalles = venta.ventadetalle_set.select_related('articulo').all()
    for item in detalles:
        articulo = getattr(item, 'articulo', None)
        descripcion = (getattr(item, 'comentario', None) or '').strip()
        if not descripcion and articulo:
            descripcion = articulo.nombre
        _append(
            lineas,
            codigo=articulo.codigo if articulo else '',
            descripcion=descripcion,
            cantidad=item.cantidad,
            precio_unitario=item.precio_unitario,
            total=item.precio_total,
        )
    return lineas


def _desde_nota(nota):
    lineas = []
    if not nota:
        return lineas
    for item in nota.items.select_related('articulo').all():
        articulo = getattr(item, 'articulo', None)
        _append(
            lineas,
            codigo=getattr(item, 'codigo', None) or (articulo.codigo if articulo else ''),
            descripcion=getattr(item, 'descripcion', None) or (articulo.nombre if articulo else ''),
            cantidad=item.cantidad,
            precio_unitario=item.precio_unitario,
            total=getattr(item, 'total', None),
        )
    return lineas


def _desde_despacho(qs):
    lineas = []
    for item in qs.select_related('item_pedido__articulo').filter(cantidad__gt=0):
        pedido = getattr(item, 'item_pedido', None)
        articulo = getattr(pedido, 'articulo', None) if pedido else None
        precio = getattr(pedido, 'precio_unitario', 0) if pedido else 0
        desc_pct = _dec(getattr(pedido, 'descuento_porcentaje', 0) if pedido else 0)
        subtotal = _dec(item.cantidad) * _dec(precio)
        total = subtotal - (subtotal * desc_pct / Decimal('100'))
        _append(
            lineas,
            codigo=articulo.codigo if articulo else '',
            descripcion=articulo.nombre if articulo else '',
            cantidad=item.cantidad,
            precio_unitario=precio,
            total=total,
        )
    return lineas


def _desde_transferencia(dte):
    lineas = []
    try:
        transferencias = dte.transferencias.all()
    except Exception:
        return lineas
    for transf in transferencias:
        for item in transf.detalles.select_related('articulo').all():
            articulo = getattr(item, 'articulo', None)
            _append(
                lineas,
                codigo=articulo.codigo if articulo else '',
                descripcion=(item.descripcion or (articulo.nombre if articulo else '')),
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
                total=item.total,
            )
    return lineas


def _desde_xml(xml_text):
    lineas = []
    if not xml_text:
        return lineas
    bloques = re.findall(r'<Detalle\b[^>]*>(.*?)</Detalle>', xml_text, re.DOTALL | re.IGNORECASE)
    for bloque in bloques:
        def tag(nombre):
            match = re.search(rf'<{nombre}>([^<]*)</{nombre}>', bloque, re.IGNORECASE)
            return match.group(1).strip() if match else ''

        qty = _dec(tag('QtyItem'))
        if qty <= 0:
            continue
        precio = _dec(tag('PrcItem'))
        monto = tag('MontoItem')
        _append(
            lineas,
            codigo=tag('VlrCodigo'),
            descripcion=tag('NmbItem') or tag('DscItem'),
            cantidad=qty,
            precio_unitario=precio,
            total=monto or (qty * precio),
        )
    return lineas


def obtener_lineas_dte(dte):
    """Devuelve código, descripción, cantidad, precio y total de cada ítem del DTE."""
    try:
        lineas = _desde_venta(getattr(dte, 'venta', None))
        if lineas:
            return lineas

        tipo = str(getattr(dte, 'tipo_dte', '') or '')
        if tipo == '52':
            lineas = _desde_despacho(dte.detalles_despacho_guia)
        elif tipo in ('33', '34'):
            try:
                lineas = _desde_despacho(dte.detalles_despacho_factura)
            except Exception:
                lineas = []
            if not lineas:
                try:
                    lineas = _desde_despacho(dte.detalles_despacho_guia)
                except Exception:
                    lineas = []
        if lineas:
            return lineas

        lineas = _desde_transferencia(dte)
        if lineas:
            return lineas

        try:
            nota = dte.notas_credito.first()
            lineas = _desde_nota(nota)
            if lineas:
                return lineas
        except Exception:
            pass
        try:
            nota = dte.notas_debito.first()
            lineas = _desde_nota(nota)
            if lineas:
                return lineas
        except Exception:
            pass

        return _desde_xml(getattr(dte, 'xml_firmado', None) or getattr(dte, 'xml_dte', None) or '')
    except Exception:
        try:
            return _desde_xml(getattr(dte, 'xml_firmado', None) or getattr(dte, 'xml_dte', None) or '')
        except Exception:
            return []
