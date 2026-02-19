"""
Vista para monitorear DTEs pendientes de envío
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from empresas.decorators import requiere_empresa
from .models import DocumentoTributarioElectronico
from .background_sender import get_background_sender


@login_required
@requiere_empresa
def monitor_envios(request):
    """
    Vista para monitorear el estado de los envíos al SII
    """
    # Obtener DTEs pendientes y en proceso
    dtes_pendientes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa,
        estado_sii__in=['pendiente', 'enviando', 'generado']
    ).select_related('venta').order_by('-fecha_emision')[:50]
    
    # Obtener estadísticas del sender
    sender = get_background_sender()
    stats = sender.get_stats()
    
    context = {
        'dtes_pendientes': dtes_pendientes,
        'stats': stats,
    }
    
    return render(request, 'facturacion_electronica/monitor_envios.html', context)


@login_required
@requiere_empresa
def reenviar_dte(request, dte_id):
    """
    Reenvía un DTE pendiente al SII
    """
    try:
        dte = DocumentoTributarioElectronico.objects.get(
            id=dte_id,
            empresa=request.empresa
        )
        
        # Agregar a la cola de envío
        sender = get_background_sender()
        if sender.enviar_dte(dte.id, request.empresa.id):
            return JsonResponse({
                'success': True,
                'message': f'DTE {dte.folio} agregado a la cola de envío'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No se pudo agregar el DTE a la cola'
            })
            
    except DocumentoTributarioElectronico.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'DTE no encontrado'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@login_required
@requiere_empresa
def reenviar_multiples(request):
    """
    Reenvía múltiples DTEs pendientes
    """
    try:
        # Obtener todos los DTEs pendientes
        dtes_pendientes = DocumentoTributarioElectronico.objects.filter(
            empresa=request.empresa,
            estado_sii='pendiente'
        )
        
        dte_ids = list(dtes_pendientes.values_list('id', flat=True))
        
        # Agregar a la cola
        sender = get_background_sender()
        count = sender.enviar_multiples(dte_ids, request.empresa.id)
        
        return JsonResponse({
            'success': True,
            'message': f'{count} DTEs agregados a la cola de envío'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@login_required
@requiere_empresa
def stats_envios(request):
    """
    Retorna estadísticas de envíos en formato JSON (para AJAX)
    """
    sender = get_background_sender()
    stats = sender.get_stats()
    
    # Contar DTEs por estado
    dtes_por_estado = {}
    for estado in ['pendiente', 'enviando', 'enviado', 'generado']:
        count = DocumentoTributarioElectronico.objects.filter(
            empresa=request.empresa,
            estado_sii=estado
        ).count()
        dtes_por_estado[estado] = count
    
    return JsonResponse({
        'success': True,
        'stats': stats,
        'dtes_por_estado': dtes_por_estado
    })



