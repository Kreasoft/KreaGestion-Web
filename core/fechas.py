from datetime import datetime, timedelta

from django.utils import timezone


def fecha_documento_caja(apertura=None):
    """
    Fecha del documento para todo efecto: el día de la apertura de caja.
    No usa la hora de grabación en el sistema (fecha_creacion / registro).
    Si no hay caja abierta, usa el día local de Chile.
    """
    if apertura is not None:
        fa = getattr(apertura, 'fecha_apertura', None)
        if fa is not None:
            if hasattr(fa, 'hour'):
                if timezone.is_aware(fa):
                    return timezone.localtime(fa).date()
                return fa.date()
            return fa
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
