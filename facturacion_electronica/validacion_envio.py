"""
Utilidades para validación y envío seguro de DTEs
"""
import re
from django.utils import timezone
from datetime import datetime


MENSAJE_ACTECO_INVALIDO = (
    'El código de actividad económica (Acteco) de la empresa es obligatorio '
    'y debe ser un número mayor a 0 (código SII, ej. 620200). '
    'Configúrelo en Empresa → Facturación electrónica. '
    'No se emitirá el documento para no gastar un folio.'
)

TIPOS_SIN_PRECIO_CERO = {'33', '34', '39', '41', '56', '61'}
TRASLADOS_GUIA_OMITE_PRECIO = {'4', '5', '6', '8'}
MENSAJE_PRECIO_CERO = (
    'Este documento no puede llevar precio o total 0 en un producto. '
    'Corrija el precio del artículo antes de emitir. No se usará un folio.'
)


def normalizar_acteco(valor):
    """Devuelve el Acteco SII (entero >= 1) o None si es inválido / 0 / vacío."""
    digits = ''.join(ch for ch in str(valor or '') if ch.isdigit())
    if not digits:
        return None
    numero = int(digits)
    if numero < 1:
        return None
    return str(numero)


def acteco_empresa_valido(empresa):
    return bool(normalizar_acteco(getattr(empresa, 'codigo_actividad_economica', None)))


def xml_tiene_acteco_invalido(xml_texto):
    if not xml_texto:
        return False
    match = re.search(r'<Acteco>\s*([^<]+)\s*</Acteco>', str(xml_texto), re.I)
    if not match:
        return False
    return normalizar_acteco(match.group(1)) is None


def errores_emisor_para_dte(empresa, tipo_dte):
    """Validaciones de emisor que deben correr ANTES de consumir folio."""
    errores = []
    tipo = str(tipo_dte or '')
    if tipo not in ('39', '41') and not acteco_empresa_valido(empresa):
        errores.append(MENSAJE_ACTECO_INVALIDO)
    return errores


def _numero_precio(valor):
    texto = str(valor if valor not in (None, '') else '0').strip()
    if not texto:
        return 0.0
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    try:
        return float(texto)
    except (TypeError, ValueError):
        return 0.0


def traslado_guia_omite_precio(tipo_traslado):
    """Res. 154 / Circ. 103: si el traslado no es venta, se puede omitir el valor."""
    return str(tipo_traslado or '').strip() in TRASLADOS_GUIA_OMITE_PRECIO


def documento_exige_precio(tipo_dte, tipo_traslado=None):
    tipo = str(tipo_dte or '')
    if tipo in TIPOS_SIN_PRECIO_CERO:
        return True
    if tipo == '52':
        return not traslado_guia_omite_precio(tipo_traslado)
    return False


def xml_tiene_precio_cero(xml_texto, tipo_dte=None, tipo_traslado=None):
    """SII: si va PrcItem, no puede ser 0 (Dec12_6 minInclusive 0.000001)."""
    tipo = str(tipo_dte or '')
    if tipo == '52' and traslado_guia_omite_precio(tipo_traslado):
        for valor in re.findall(r'<PrcItem>\s*([^<]+)\s*</PrcItem>', str(xml_texto or ''), re.I):
            if _numero_precio(valor) <= 0:
                return True
        return False
    if tipo and tipo not in TIPOS_SIN_PRECIO_CERO and tipo != '52':
        return False
    if tipo == '52' and not documento_exige_precio(tipo, tipo_traslado):
        return False
    if not xml_texto:
        return False
    tags = ('PrcItem',) if tipo == '52' else ('PrcItem', 'MontoItem')
    for tag in tags:
        for valor in re.findall(rf'<{tag}>\s*([^<]+)\s*</{tag}>', str(xml_texto), re.I):
            if _numero_precio(valor) <= 0:
                return True
    return False


def _precio_catalogo_articulo(articulo):
    if not articulo:
        return 0.0
    for campo in ('precio_venta', 'precio_final'):
        precio = _numero_precio(getattr(articulo, campo, 0))
        if precio > 0:
            return precio
    return 0.0


def tipo_dte_y_traslado_desde_venta(venta):
    """Mapea vale/ticket/factura/guía al tipo DTE y al IndTraslado."""
    if not venta:
        return None, None
    doc = str(getattr(venta, 'tipo_documento', '') or '')
    planeado = str(getattr(venta, 'tipo_documento_planeado', '') or '') or doc
    traslado = str(getattr(venta, 'tipo_despacho', '') or '')
    if doc == 'cotizacion':
        return None, None
    if doc == 'guia' or planeado == 'guia':
        return '52', traslado
    if doc == 'factura' or planeado == 'factura':
        return '33', None
    if doc == 'boleta' or planeado == 'boleta':
        return '39', None
    return None, None


def validar_precios_items_venta(venta, tipo_dte, tipo_traslado=None):
    """None si las líneas están bien; mensaje si el DTE exige precio y hay una en 0."""
    if tipo_traslado is None:
        tipo_traslado = str(getattr(venta, 'tipo_despacho', '') or '') if venta else None
    if not documento_exige_precio(tipo_dte, tipo_traslado) or not venta:
        return None
    detalles = getattr(venta, 'ventadetalle_set', None)
    if detalles is None:
        return None
    for item in detalles.all():
        if _numero_precio(getattr(item, 'cantidad', 0)) <= 0:
            continue
        precio = _numero_precio(getattr(item, 'precio_unitario', 0))
        total = _numero_precio(getattr(item, 'precio_total', 0) or getattr(item, 'total', 0))
        if precio > 0 or total > 0:
            continue
        if _precio_catalogo_articulo(getattr(item, 'articulo', None)) > 0:
            continue
        articulo = getattr(item, 'articulo', None)
        nombre = getattr(articulo, 'nombre', None) or 'producto'
        return (
            f'El producto "{nombre}" tiene precio 0. {MENSAJE_PRECIO_CERO}'
        )
    return None


def validar_dte_antes_envio(dte):
    """
    Valida que un DTE esté listo para ser enviado al SII.
    
    Args:
        dte: Instancia de DocumentoTributarioElectronico
        
    Returns:
        tuple: (es_valido: bool, mensaje_error: str or None)
    """
    
    # 1. Verificar que el estado admita un intento o reintento de envio
    reenvio_xml_corregido = bool(getattr(dte, 'permite_reenvio_xml_corregido', False))
    if getattr(dte, 'en_espera_reintento_sii', lambda: False)() and not reenvio_xml_corregido:
        mensaje = dte.get_mensaje_espera_reintento() if hasattr(dte, 'get_mensaje_espera_reintento') else (
            'El SII pidió esperar antes de reenviar este archivo.'
        )
        return False, mensaje
    if not dte.puede_enviarse_al_sii and not reenvio_xml_corregido:
        if dte.estado_sii in ['enviado', 'enviando'] and str(getattr(dte, 'track_id', None) or '').strip():
            return False, f"El DTE ya fue enviado (estado: {dte.estado_sii})"
        return False, f"El DTE no admite envio al SII en su estado actual ({dte.estado_sii})"
    
    # 2. Verificar que no esté anulado
    if dte.estado_sii == 'anulado':
        return False, "El DTE está anulado y no puede ser enviado"
    
    # 3. Verificar que tenga XML (firmado o el DTE; el envío puede regenerarlo)
    xml_disponible = (dte.xml_firmado or '').strip() or (getattr(dte, 'xml_dte', None) or '').strip()
    if not xml_disponible:
        return False, "El DTE no tiene XML firmado"
    
    # 4. Verificar que tenga CAF asignado
    if not dte.caf_utilizado:
        return False, "El DTE no tiene CAF asignado"
    
    # 5. Verificar que el CAF esté vigente
    if dte.caf_utilizado:
        if getattr(dte.caf_utilizado, 'estado', '') == 'anulado':
            return False, "El CAF asignado está anulado"

        hoy = timezone.localdate()
        
        # Verificar fecha de vencimiento
        try:
            fecha_venc = dte.caf_utilizado.fecha_vencimiento
            # Si es un método, llamarlo
            if callable(fecha_venc):
                fecha_venc = fecha_venc()
            
            if fecha_venc and fecha_venc < hoy:
                return False, f"El CAF está vencido (venció el {fecha_venc})"
        except (AttributeError, TypeError):
            # Si no tiene fecha de vencimiento, continuar
            pass
        
        # Verificar que el folio esté dentro del rango
        if not (dte.caf_utilizado.folio_desde <= dte.folio <= dte.caf_utilizado.folio_hasta):
            return False, f"El folio {dte.folio} está fuera del rango del CAF ({dte.caf_utilizado.folio_desde}-{dte.caf_utilizado.folio_hasta})"

        if getattr(dte.caf_utilizado, 'estado', '') == 'vencido':
            return False, "El CAF asignado ya está marcado como vencido"
    
    # 6. Verificar que tenga empresa asignada
    if not dte.empresa:
        return False, "El DTE no tiene empresa asignada"
    # 7. Verificar configuracion directa SII
    if not getattr(dte.empresa, 'facturacion_electronica', False):
        return False, f"La empresa {dte.empresa.nombre} no tiene facturacion electronica activa"

    if not getattr(dte.empresa, 'certificado_digital', None):
        return False, "La empresa no tiene certificado digital configurado"

    if not getattr(dte.empresa, 'password_certificado', None):
        return False, "La empresa no tiene contrasena de certificado configurada"

    # 7b. Acteco SII (facturas, guías, NC, ND): 0 o vacío invalida el schema
    if str(getattr(dte, 'tipo_dte', '')) not in ('39', '41'):
        if xml_tiene_acteco_invalido(xml_disponible) or not acteco_empresa_valido(dte.empresa):
            return False, MENSAJE_ACTECO_INVALIDO

    # 8. Verificar que tenga datos minimos
    if not dte.rut_receptor:
        return False, "El DTE no tiene RUT del receptor"
    
    if not dte.monto_total or dte.monto_total <= 0:
        return False, "El DTE no tiene monto total válido"

    if xml_tiene_precio_cero(
        xml_disponible,
        getattr(dte, 'tipo_dte', None),
        getattr(dte, 'tipo_traslado', None),
    ):
        return False, MENSAJE_PRECIO_CERO

    # 9. Validaciones de referencia para notas electrónicas
    if str(getattr(dte, 'tipo_dte', '')) in {'56', '61'}:
        nota = dte.notas_debito.first() if dte.tipo_dte == '56' else dte.notas_credito.first()
        if not nota:
            return False, "La nota electrónica no tiene documento fuente asociado"

        if not getattr(nota, 'tipo_doc_afectado', None) or not getattr(nota, 'numero_doc_afectado', None):
            return False, "La nota electrónica no tiene documento de referencia completo"

        from facturacion_electronica.models import DocumentoTributarioElectronico

        referencia = DocumentoTributarioElectronico.objects.filter(
            empresa=dte.empresa,
            tipo_dte=nota.tipo_doc_afectado,
            folio=str(nota.numero_doc_afectado).strip()
        ).first()

        if referencia and referencia.rut_receptor and dte.rut_receptor:
            rut_ref = str(referencia.rut_receptor).replace('.', '').strip()
            rut_dte = str(dte.rut_receptor).replace('.', '').strip()
            if rut_ref != rut_dte:
                return False, (
                    "El RUT receptor de la nota no coincide con el documento referenciado "
                    f"({referencia.tipo_dte}-{referencia.folio})"
                )
    
    # 10. Verificar que el XML sea válido (básico)
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(dte.xml_firmado)
    except Exception as e:
        return False, f"El XML firmado no es válido: {str(e)}"
    
    # ✅ Todas las validaciones pasaron
    return True, None


def obtener_dtes_pendientes_envio(empresa=None, solo_mes_actual=True):
    """
    DTEs sin Track del mes en curso (los más recientes).
    No reintenta historial ni CAF vencido.
    """
    from facturacion_electronica.models import DocumentoTributarioElectronico
    from django.db.models import Q

    estados_pendientes = ['generado', 'firmado', 'pendiente', 'error_envio', 'error']
    sin_track = Q(track_id__isnull=True) | Q(track_id='')
    hoy = timezone.localdate()
    caf_ok = (
        Q(caf_utilizado__isnull=True) |
        Q(caf_utilizado__fecha_vencimiento__isnull=True) |
        Q(caf_utilizado__fecha_vencimiento__gte=hoy)
    )

    query = DocumentoTributarioElectronico.objects.filter(
        sin_track
    ).filter(
        Q(estado_sii__in=estados_pendientes) |
        Q(estado_sii='enviando')
    ).filter(caf_ok).exclude(
        error_envio__icontains='CAF está vencido'
    ).exclude(
        error_envio__icontains='PrcItem'
    ).exclude(
        error_envio__icontains='precio o total 0'
    ).select_related('empresa', 'caf_utilizado')

    if solo_mes_actual:
        inicio = hoy.replace(day=1)
        query = query.filter(
            Q(fecha_emision__gte=inicio, fecha_emision__lte=hoy) |
            Q(fecha__gte=inicio, fecha__lte=hoy)
        )

    if empresa:
        query = query.filter(empresa=empresa)

    return query.order_by('-fecha_emision', '-folio', '-id')


def diagnosticar_dte(dte):
    """
    Genera un diagnóstico completo de un DTE.
    
    Args:
        dte: Instancia de DocumentoTributarioElectronico
        
    Returns:
        dict con información de diagnóstico
    """
    es_valido, error = validar_dte_antes_envio(dte)
    
    # Verificar CAF vigente de forma segura
    caf_vigente = None
    if dte.caf_utilizado:
        try:
            fecha_venc = dte.caf_utilizado.fecha_vencimiento
            if callable(fecha_venc):
                fecha_venc = fecha_venc()
            if fecha_venc:
                caf_vigente = fecha_venc >= timezone.localdate()
        except (AttributeError, TypeError):
            pass
    
    return {
        'id': dte.id,
        'tipo_dte': dte.tipo_dte,
        'folio': dte.folio,
        'fecha_emision': dte.fecha_emision,
        'estado_sii': dte.estado_sii,
        'monto_total': dte.monto_total,
        'receptor': dte.razon_social_receptor,
        'rut_receptor': dte.rut_receptor,
        'tiene_xml': bool(dte.xml_firmado),
        'tiene_caf': bool(dte.caf_utilizado),
        'caf_vigente': caf_vigente,
        'es_valido_para_envio': es_valido,
        'error_validacion': error,
        'ultimo_error_envio': dte.error_envio if hasattr(dte, 'error_envio') else None,
    }
