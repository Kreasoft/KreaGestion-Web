import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from core.decorators import requiere_empresa

@login_required
@requiere_empresa
@csrf_exempt
def vale_imprimir_local(request, pk):
    """Genera el contenido ESC/POS del vale y lo encola en ColaImpresion"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Solo POST permitido.'})

    try:
        from .models import Venta, VentaDetalle
        from caja.models import ColaImpresion
        from caja.impresion_utils import generar_esc_pos_ticket

        venta = Venta.objects.get(pk=pk, empresa=request.empresa)
        detalles = VentaDetalle.objects.filter(venta=venta)
        
        # Generar texto RAW para imprimir
        raw_content = generar_esc_pos_ticket(venta, detalles)
        
        # Encolar para impresión
        estacion = getattr(venta, 'estacion_trabajo', None)
        caja_id = 1
        
        # Buscar la caja id
        if estacion:
            from caja.models import AperturaCaja, Caja
            aperturas = AperturaCaja.objects.filter(
                caja__empresa=request.empresa, 
                activo=True
            )
            for ap in aperturas:
                if ap.caja.estaciones.filter(id=estacion.id).exists() or ap.caja.estacion == estacion:
                    caja_id = ap.caja.id
                    break
        
        ColaImpresion.objects.create(
            empresa=request.empresa,
            caja_id=caja_id,
            contenido_raw=raw_content,
            tipo_documento='vale',
            venta_id=venta.id
        )
        
        return JsonResponse({'success': True, 'message': 'Enviado a cola local de impresión'})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)})
