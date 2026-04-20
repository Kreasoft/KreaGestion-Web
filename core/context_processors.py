import datetime
from django.db.models import Q
from ventas.models import Venta
from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF, ConfiguracionAlertaFolios

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
        # 1. ALERTAS DE GUÍAS PENDIENTES
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

        # 2. ALERTAS DE FOLIOS CAF
        active_cafs = ArchivoCAF.objects.filter(
            empresa=empresa,
            estado='activo'
        ).select_related('sucursal')
        
        # Obtener configuración de alertas (folios mínimos)
        alert_configs = {
            c.tipo_documento: c.folios_minimos 
            for c in ConfiguracionAlertaFolios.objects.filter(empresa=empresa, activo=True)
        }
        
        caf_alerts = []
        for caf in active_cafs:
            # Alerta por Vencimiento (menos de 15 días)
            dias = caf.dias_para_vencer()
            if dias <= 15:
                caf_alerts.append({
                    'tipo': 'vencimiento',
                    'urgencia': 'danger' if dias <= 5 else 'warning',
                    'mensaje': f'CAF {caf.get_tipo_documento_display()} vence en {dias} días',
                    'documento': caf.get_tipo_documento_display(),
                    'detalle': f'Vence el {caf.fecha_vencimiento.strftime("%d/%m/%Y")}'
                })
            
            # Alerta por Cantidad (bajo stock)
            min_folios = alert_configs.get(caf.tipo_documento, 20)
            disponibles = caf.folios_disponibles()
            if disponibles <= min_folios:
                caf_alerts.append({
                    'tipo': 'cantidad',
                    'urgencia': 'danger' if disponibles <= (min_folios / 2) else 'warning',
                    'mensaje': f'Quedan pocos folios para {caf.get_tipo_documento_display()}',
                    'documento': caf.get_tipo_documento_display(),
                    'detalle': f'{disponibles} folios restantes'
                })
        
        context['GLOBAL_CAF_ALERTS'] = caf_alerts
        context['GLOBAL_TOTAL_NOTIFICATIONS'] += len(caf_alerts)
        
        return context
        
    except Exception as e:
        print(f"Error in context processor: {e}")
        return context
