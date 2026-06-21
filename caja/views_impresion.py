import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import ColaImpresion, Caja
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

@csrf_exempt
@require_http_methods(["GET"])
def obtener_pendientes(request):
    """
    Retorna la lista de trabajos de impresión pendientes para una caja específica.
    """
    caja_id = request.GET.get('caja_id')
    if not caja_id:
        return JsonResponse({'error': 'caja_id es requerido'}, status=400)
    
    ahora = timezone.now()
    ColaImpresion.objects.filter(
        caja_id=caja_id,
        estado='imprimiendo',
        fecha_impresion__lt=ahora - timedelta(minutes=5)
    ).update(estado='pendiente', fecha_impresion=None)

    with transaction.atomic():
        pendientes = list(
            ColaImpresion.objects.select_for_update(skip_locked=True).filter(
                caja_id=caja_id,
                estado='pendiente'
            ).order_by('fecha_creacion')[:10]
        )

        for trabajo in pendientes:
            trabajo.estado = 'imprimiendo'
            trabajo.fecha_impresion = ahora
            trabajo.save(update_fields=['estado', 'fecha_impresion'])
    
    data = []
    for p in pendientes:
        data.append({
            'id': p.id,
            'contenido_raw': p.contenido_raw,
            'fecha_creacion': p.fecha_creacion.isoformat()
        })
        
    return JsonResponse({'pendientes': data})

@csrf_exempt
@require_http_methods(["POST"])
def marcar_impreso(request, trabajo_id=None):
    """
    Marca un trabajo como impreso o con error.
    """
    try:
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except (TypeError, ValueError):
            body = {}

        job_id = body.get('id') or trabajo_id
        status = body.get('status') or body.get('estado') or 'impreso'
        error_msg = body.get('error_msg') or body.get('error') or ''
        
        if not job_id or status not in ['impreso', 'error']:
            return JsonResponse({'error': 'Parámetros inválidos'}, status=400)
            
        job = ColaImpresion.objects.get(id=job_id)
        job.estado = status
        job.fecha_impresion = timezone.now()
        job.intentos += 1
        
        if error_msg:
            job.error_log = error_msg
            
        job.save()
        return JsonResponse({'success': True})
        
    except ColaImpresion.DoesNotExist:
        return JsonResponse({'error': 'Trabajo no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
