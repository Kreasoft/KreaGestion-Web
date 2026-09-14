import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from core.decorators import requiere_empresa
from caja.models import Caja, ColaImpresion, ImpresoraAgente
from caja.impresion_utils import generar_esc_pos_ticket, resolver_caja_cola_impresion

logger = logging.getLogger(__name__)

@login_required
@requiere_empresa
@csrf_exempt
def vale_imprimir_local(request, pk):
    """Genera el contenido ESC/POS del vale/venta y lo encola en ColaImpresion para el agente"""
    if request.method == 'GET':
        trabajo_id = request.GET.get('trabajo_id')
        if trabajo_id:
            try:
                job = ColaImpresion.objects.get(pk=int(trabajo_id), empresa=request.empresa)
                mensajes = {
                    'pendiente': 'Trabajo en cola. Esperando al agente.',
                    'imprimiendo': 'El agente recibió el trabajo y lo está procesando.',
                    'impreso': 'El agente confirmó el envío a la impresora.',
                    'error': 'El agente informó un error al imprimir.',
                }
                return JsonResponse({'success': True, 'trabajo_id': job.pk, 'estado': job.estado, 'message': mensajes.get(job.estado, '')})
            except Exception:
                return JsonResponse({'success': False, 'message': 'Trabajo no encontrado.'}, status=404)
        return JsonResponse({'success': True})

    try:
        from .models import Venta, VentaDetalle
        venta = get_object_or_404(Venta, pk=pk, empresa=request.empresa)
        detalles = VentaDetalle.objects.filter(venta=venta)
        raw_content = generar_esc_pos_ticket(venta, detalles)
        
        caja = resolver_caja_cola_impresion(
            request.empresa,
            estacion=getattr(venta, 'estacion_trabajo', None),
            sucursal=getattr(venta, 'sucursal', None),
            tipo_documento='vale'
        )
        if not caja:
            caja = Caja.objects.filter(empresa=request.empresa, activo=True).first()

        if not caja:
            return JsonResponse({'success': False, 'message': 'No hay cajas disponibles.'}, status=400)

        impresora = ImpresoraAgente.objects.filter(empresa=request.empresa, caja=caja, en_uso=True).order_by('-ultimo_reporte').first()
        if not impresora:
            impresora = ImpresoraAgente.objects.filter(empresa=request.empresa, caja=caja).order_by('-ultimo_reporte').first()

        # Reutilizar si ya hay un trabajo pendiente o imprimiendo para esta venta
        previo = ColaImpresion.objects.filter(
            empresa=request.empresa, caja=caja, documento_id=venta.id, tipo_documento='vale',
            estado__in=['pendiente', 'imprimiendo']
        ).order_by('-pk').first()
        if previo:
            return JsonResponse({'success': True, 'trabajo_id': previo.pk, 'estado': previo.estado, 'message': 'Trabajo en cola.'})

        job = ColaImpresion.objects.create(
            empresa=request.empresa,
            caja=caja,
            contenido_raw=raw_content,
            tipo_documento='vale',
            documento_id=venta.id,
            venta_id=venta.id,
            nombre_impresora=impresora.nombre if impresora else '',
            estado='pendiente'
        )
        return JsonResponse({'success': True, 'trabajo_id': job.pk, 'estado': job.estado, 'message': 'Trabajo en cola. Esperando al agente.'}, status=201)
    except Exception as e:
        logger.exception("Error al imprimir vale con agente: %s", e)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
