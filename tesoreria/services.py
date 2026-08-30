from decimal import Decimal

from django.db.models import Sum

from core.fechas import calcular_fecha_vencimiento, dias_pago_efectivos

from .models import (
    CuentaCorrienteCliente,
    DocumentoCliente,
    MovimientoCuentaCorrienteCliente,
    PagoDocumentoCliente,
)


TIPO_DOCUMENTO_TESORERIA_MAP = {
    '33': 'factura',
    '34': 'factura',
    '39': 'boleta',
    '41': 'boleta',
    '56': 'nota_debito',
    '61': 'nota_credito',
}


def _decimal(valor):
    return Decimal(str(valor or 0))


def _tipo_documento_tesoreria(venta, dte=None):
    if dte and str(getattr(dte, 'tipo_dte', '') or '') in TIPO_DOCUMENTO_TESORERIA_MAP:
        return TIPO_DOCUMENTO_TESORERIA_MAP[str(dte.tipo_dte)]

    tipo_venta = str(getattr(venta, 'tipo_documento', '') or '').strip().lower()
    if tipo_venta in {'factura', 'factura_electronica'}:
        return 'factura'
    if tipo_venta in {'boleta', 'boleta_electronica'}:
        return 'boleta'
    return 'factura'


def _numero_documento_tesoreria(venta, dte=None):
    if dte and getattr(dte, 'folio', None):
        return f"{dte.tipo_dte}-{dte.folio}"
    return str(getattr(venta, 'numero_venta', '') or '')


def _recalcular_cuenta(cuenta):
    documentos = DocumentoCliente.objects.filter(
        empresa=cuenta.empresa,
        cliente=cuenta.cliente,
    )
    cuenta.saldo_total = documentos.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    cuenta.saldo_pendiente = documentos.filter(
        estado_pago__in=['pendiente', 'parcial']
    ).aggregate(total=Sum('saldo_pendiente'))['total'] or Decimal('0.00')
    cuenta.saldo_vencido = documentos.filter(
        estado_pago='vencido'
    ).aggregate(total=Sum('saldo_pendiente'))['total'] or Decimal('0.00')
    cuenta.save(update_fields=['saldo_total', 'saldo_pendiente', 'saldo_vencido', 'fecha_modificacion'])


def sincronizar_venta_credito_en_tesoreria(venta, dte=None, usuario=None, descripcion=None):
    """
    Registra o actualiza la cuenta corriente del cliente para una venta a crédito.
    Debe ser idempotente para poder invocarse desde distintos flujos.
    """
    if not venta or not getattr(venta, 'cliente', None):
        return False

    tipo_dte = str(getattr(dte, 'tipo_dte', '') or '')
    tipo_venta = str(getattr(venta, 'tipo_documento', '') or '').strip().lower()
    es_factura = tipo_dte in ('33', '34') or tipo_venta in ('factura', 'factura_electronica')
    if not es_factura:
        return False

    forma_pago = getattr(venta, 'forma_pago', None)
    total = _decimal(getattr(venta, 'total', 0))
    monto_pagado = _decimal(getattr(venta, 'monto_pagado', 0))
    saldo_pendiente = _decimal(getattr(venta, 'saldo_pendiente', 0))
    es_credito = bool(getattr(forma_pago, 'es_cuenta_corriente', False)) or saldo_pendiente > 0

    if not es_credito or total <= 0 or saldo_pendiente <= 0:
        return False

    usuario = usuario or getattr(venta, 'usuario_creacion', None)
    if usuario is None:
        return False

    cuenta, _ = CuentaCorrienteCliente.objects.get_or_create(
        empresa=venta.empresa,
        cliente=venta.cliente,
        defaults={
            'limite_credito': getattr(venta.cliente, 'limite_credito', Decimal('0.00')) or Decimal('0.00'),
            'dias_credito': dias_pago_efectivos(getattr(venta.cliente, 'plazo_pago', 0)),
        }
    )

    tipo_documento = _tipo_documento_tesoreria(venta, dte=dte)
    numero_documento = _numero_documento_tesoreria(venta, dte=dte)
    observacion_base = descripcion or (
        f"Documento a crédito {numero_documento}"
        if numero_documento else f"Venta a crédito {venta.numero_venta}"
    )
    fecha_vencimiento = getattr(venta, 'fecha_vencimiento', None) or calcular_fecha_vencimiento(
        venta.fecha, getattr(venta.cliente, 'plazo_pago', 0)
    )
    estado_documento = 'parcial' if monto_pagado > 0 else 'pendiente'

    documento, created = DocumentoCliente.objects.get_or_create(
        empresa=venta.empresa,
        tipo_documento=tipo_documento,
        numero_documento=numero_documento,
        defaults={
            'cliente': venta.cliente,
            'fecha_emision': venta.fecha,
            'fecha_vencimiento': fecha_vencimiento,
            'total': int(round(total)),
            'monto_pagado': monto_pagado,
            'saldo_pendiente': saldo_pendiente,
            'estado_pago': estado_documento,
            'observaciones': observacion_base,
            'creado_por': usuario,
        }
    )
    if not created:
        documento.cliente = venta.cliente
        documento.fecha_emision = venta.fecha
        documento.fecha_vencimiento = fecha_vencimiento
        documento.total = int(round(total))
        documento.monto_pagado = monto_pagado
        documento.saldo_pendiente = saldo_pendiente
        documento.estado_pago = estado_documento
        if observacion_base:
            documento.observaciones = observacion_base
        documento.save(
            update_fields=[
                'cliente', 'fecha_emision', 'fecha_vencimiento', 'total',
                'monto_pagado', 'saldo_pendiente', 'estado_pago',
                'observaciones', 'fecha_modificacion'
            ]
        )

    movimiento_debe = MovimientoCuentaCorrienteCliente.objects.filter(
        cuenta_corriente=cuenta,
        venta=venta,
        tipo_movimiento='debe',
        estado='confirmado',
    ).order_by('id').first()

    saldo_base = _decimal(getattr(cuenta, 'saldo_pendiente', 0))
    if movimiento_debe is None:
        MovimientoCuentaCorrienteCliente.objects.create(
            cuenta_corriente=cuenta,
            venta=venta,
            tipo_movimiento='debe',
            monto=total,
            saldo_anterior=saldo_base,
            saldo_nuevo=saldo_base + total,
            estado='confirmado',
            observaciones=observacion_base,
            registrado_por=usuario,
        )
    elif _decimal(movimiento_debe.monto) != total or movimiento_debe.observaciones != observacion_base:
        movimiento_debe.monto = total
        movimiento_debe.observaciones = observacion_base
        movimiento_debe.save(update_fields=['monto', 'observaciones'])

    pagos_registrados = PagoDocumentoCliente.objects.filter(documento=documento).aggregate(
        total=Sum('monto')
    )['total'] or Decimal('0.00')

    diferencia_pago = monto_pagado - _decimal(pagos_registrados)
    if diferencia_pago > 0:
        forma_pago_nombre = getattr(forma_pago, 'nombre', '') or 'Abono'
        PagoDocumentoCliente.objects.create(
            documento=documento,
            monto=diferencia_pago,
            forma_pago=forma_pago_nombre,
            observaciones='Abono inicial registrado automaticamente al emitir documento a crédito',
            registrado_por=usuario,
        )

        saldo_despues_debe = saldo_base + total
        MovimientoCuentaCorrienteCliente.objects.create(
            cuenta_corriente=cuenta,
            venta=venta,
            tipo_movimiento='haber',
            monto=diferencia_pago,
            saldo_anterior=saldo_despues_debe,
            saldo_nuevo=saldo_despues_debe - diferencia_pago,
            estado='confirmado',
            observaciones=f"Abono inicial {numero_documento}",
            registrado_por=usuario,
        )

    _recalcular_cuenta(cuenta)
    return True
