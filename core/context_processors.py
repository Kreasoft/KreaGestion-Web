import datetime
from django.db.models import Q
from ventas.models import Venta
from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF, ConfiguracionAlertaFolios

# Factura y boleta se alertan aunque no exista ningún CAF cargado.
_TIPOS_FOLIO_SIEMPRE = ('33', '39')
_NOMBRES_TIPO_DTE = dict(ArchivoCAF.TIPO_DOCUMENTO_CHOICES)


def _alertas_folios_caf(empresa):
    """
    Sin CAF / agotado / bajo umbral / por vencer.
    El listado de solo CAF 'activo' no avisaba cuando no había boletas.
    """
    ambiente = getattr(empresa, 'ambiente_sii', 'certificacion') or 'certificacion'
    configs = {
        c.tipo_documento: c.folios_minimos
        for c in ConfiguracionAlertaFolios.objects.filter(empresa=empresa, activo=True)
    }
    tipos = set(configs) | set(_TIPOS_FOLIO_SIEMPRE)
    cafs_empresa = list(
        ArchivoCAF.objects.filter(empresa=empresa, ambiente=ambiente, oculto=False)
    )
    por_tipo = {}
    for caf in cafs_empresa:
        por_tipo.setdefault(caf.tipo_documento, []).append(caf)
        tipos.add(caf.tipo_documento)

    alerts = []
    vistos_sin = set()
    vistos_cantidad = set()
    for tipo in sorted(tipos):
        nombre = _NOMBRES_TIPO_DTE.get(tipo, tipo)
        lista = por_tipo.get(tipo, [])
        vigentes = [
            c for c in lista
            if c.estado == 'activo' and c.esta_vigente()
        ]
        disponibles = sum(c.folios_disponibles() for c in vigentes)
        umbral = configs.get(tipo, 20)
        aviso_vacio = tipo in _TIPOS_FOLIO_SIEMPRE or bool(lista)

        if disponibles <= 0 and aviso_vacio and tipo not in vistos_sin:
            vistos_sin.add(tipo)
            alerts.append({
                'tipo': 'sin_folios',
                'urgencia': 'danger',
                'mensaje': f'Sin folios de {nombre}',
                'documento': nombre,
                'detalle': 'No hay CAF vigente. Cargue un CAF para emitir.',
            })
            continue

        if disponibles > 0 and disponibles <= umbral and tipo not in vistos_cantidad:
            vistos_cantidad.add(tipo)
            alerts.append({
                'tipo': 'cantidad',
                'urgencia': 'danger' if disponibles <= max(1, umbral // 2) else 'warning',
                'mensaje': f'Quedan {disponibles} folios de {nombre}',
                'documento': nombre,
                'detalle': f'Umbral configurado: {umbral}',
            })

        for caf in vigentes:
            dias = caf.dias_para_vencer()
            if dias <= 15:
                fecha = caf.fecha_vencimiento.strftime('%d-%m-%Y') if caf.fecha_vencimiento else 's/fecha'
                alerts.append({
                    'tipo': 'vencimiento',
                    'urgencia': 'danger' if dias <= 5 else 'warning',
                    'mensaje': f'{nombre} vence en {dias} día{"s" if dias != 1 else ""}',
                    'documento': nombre,
                    'detalle': f'Vence el {fecha}',
                })
    return alerts


def global_notifications_processor(request):
    """
    Context processor para centralizar todas las notificaciones globales del sistema.
    """
    if not request.user.is_authenticated:
        return {}

    empresa = getattr(request, 'empresa', None)
    if not empresa:
        return {}

    context = {
        'GLOBAL_GUIAS_PENDIENTES_COUNT': 0,
        'GLOBAL_GUIAS_URGENCIA_MES': False,
        'GLOBAL_CAF_ALERTS': [],
        'GLOBAL_TOTAL_NOTIFICATIONS': 0
    }

    try:
        invoiced_ventas_ids = DocumentoTributarioElectronico.objects.filter(
            empresa=empresa,
            tipo_dte__in=['33', '34'],
            orden_despacho__isnull=False
        ).values_list('orden_despacho__id', flat=True)

        cant_guias = Venta.objects.filter(
            empresa=empresa,
            estado='confirmada'
        ).filter(
            Q(tipo_documento='guia') | Q(dte__tipo_dte='52')
        ).exclude(id__in=invoiced_ventas_ids).distinct().count()

        hoy = datetime.date.today()
        urgencia_fin_mes = hoy.day >= 25

        context['GLOBAL_GUIAS_PENDIENTES_COUNT'] = cant_guias
        context['GLOBAL_GUIAS_URGENCIA_MES'] = urgencia_fin_mes
        if cant_guias > 0:
            context['GLOBAL_TOTAL_NOTIFICATIONS'] += 1

        context['GLOBAL_CAF_ALERTS'] = _alertas_folios_caf(empresa)
        context['GLOBAL_TOTAL_NOTIFICATIONS'] += len(context['GLOBAL_CAF_ALERTS'])

        return context

    except Exception:
        return context
