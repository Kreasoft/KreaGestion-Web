from datetime import datetime, timedelta

from django.utils import timezone


def fecha_apertura_caja(apertura=None):
    """Retorna la fecha local (date) en que fue abierta la caja, o None."""
    if apertura is not None:
        fa = getattr(apertura, 'fecha_apertura', None)
        if fa is not None:
            if hasattr(fa, 'hour'):
                if timezone.is_aware(fa):
                    return timezone.localtime(fa).date()
                return fa.date()
            return fa
    return None


def caja_es_del_dia_actual(apertura=None):
    """Valida si la caja abierta corresponde a la fecha actual local de Chile."""
    if apertura is None:
        return False
    if getattr(apertura, 'estado', 'abierta') != 'abierta':
        return False
    fecha_ap = fecha_apertura_caja(apertura)
    if fecha_ap is None:
        return False
    return fecha_ap == timezone.localdate()


def mensaje_caja_desfasada(apertura=None):
    """Mensaje de error cuando la fecha de apertura de la caja no corresponde al día actual."""
    hoy = timezone.localdate()
    fecha_ap = fecha_apertura_caja(apertura)
    nombre_caja = getattr(getattr(apertura, 'caja', None), 'nombre', None) or 'Caja'
    if fecha_ap:
        return (
            f'La fecha de apertura de "{nombre_caja}" ({fecha_ap.strftime("%d-%m-%Y")}) '
            f'no corresponde al día actual ({hoy.strftime("%d-%m-%Y")}). '
            f'Debe cerrar la caja pendiente y abrir una nueva caja con fecha de hoy antes de procesar o imprimir.'
        )
    return 'La caja abierta no corresponde al día actual. Debe cerrarla y abrir una nueva caja con fecha de hoy.'


def fecha_documento_caja(apertura=None):
    """
    Fecha del documento para todo efecto: usa siempre el día actual local de Chile.
    Evita que cajas abiertas en días o meses anteriores asignen fechas pasadas
    a ventas y DTEs recién emitidos (lo que los ocultaba del Libro de Ventas del mes actual).
    """
    return timezone.localdate()


def parse_fecha(valor):
    """Convierte string o date a date. Vacío → None."""
    if not valor:
        return None
    if hasattr(valor, 'year') and not hasattr(valor, 'hour'):
        return valor
    if hasattr(valor, 'date'):
        return valor.date()
    text = str(valor).strip()[:10]
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def dias_pago_efectivos(dias_pago):
    """Días de crédito. 0 / vacío / inválido = contado (vence el mismo día)."""
    try:
        dias = int(dias_pago)
    except (TypeError, ValueError):
        return 0
    return max(dias, 0)


def calcular_fecha_vencimiento(fecha_emision, dias_pago=None):
    """
    Fecha de vencimiento = emisión + días de pago.
    Si no hay días de pago, vence el mismo día de emisión.
    """
    fecha = parse_fecha(fecha_emision)
    if not fecha:
        return None
    dias = dias_pago_efectivos(dias_pago)
    if dias <= 0:
        return fecha
    return fecha + timedelta(days=dias)


def resolver_fecha_vencimiento(fecha_emision, dias_pago=None, fecha_vencimiento=None):
    """Usa la fecha ingresada si es válida; si no, emisión + días de pago."""
    venc = parse_fecha(fecha_vencimiento)
    if venc:
        return venc
    return calcular_fecha_vencimiento(fecha_emision, dias_pago)
