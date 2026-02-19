from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.template import loader
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
from django.db.models import Q
from decimal import Decimal
from .models import Stock, Inventario
from .forms import StockModalForm
import logging

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def stock_update_modal(request, pk):
    """Editar registro de stock en modal"""
    try:
        # Obtener el stock directamente
        stock = get_object_or_404(Stock, pk=pk)
        empresa = stock.empresa
        
        logger.info(f"Stock ID: {pk}, Empresa: {empresa}, User: {request.user}, Method: {request.method}")
        
    except Exception as e:
        logger.error(f"Error al obtener stock: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'Error al obtener stock: {str(e)}'
            }, status=500)
        return HttpResponse(f"Error: {e}", status=500)
    
    if request.method == 'POST':
        logger.info(f"POST Data: {request.POST}")
        
        try:
            # Leer valores deseados
            cantidad_str = request.POST.get('cantidad', '0')
            stock_minimo_str = request.POST.get('stock_minimo')
            stock_maximo_str = request.POST.get('stock_maximo')
            
            desired = Decimal(str(cantidad_str or '0'))
            min_val = Decimal(str(stock_minimo_str)) if stock_minimo_str is not None else stock.stock_minimo
            max_val = Decimal(str(stock_maximo_str)) if stock_maximo_str is not None else stock.stock_maximo
            
            # Calcular cantidad actual basada en movimientos confirmados
            current = Decimal('0')
            inv_qs = (
                Inventario.objects
                .filter(empresa=empresa, articulo=stock.articulo, estado='confirmado')
                .select_related('bodega_origen', 'bodega_destino')
            )
            for inv in inv_qs:
                t = (inv.tipo_movimiento or '').lower()
                if t == 'entrada':
                    if inv.bodega_destino_id == stock.bodega_id:
                        current += inv.cantidad
                elif t == 'salida':
                    if inv.bodega_origen_id == stock.bodega_id:
                        current -= inv.cantidad
                elif t == 'ajuste':
                    if inv.bodega_destino_id == stock.bodega_id:
                        current += inv.cantidad
                elif t == 'transferencia':
                    if inv.bodega_origen_id == stock.bodega_id:
                        current -= inv.cantidad
                    if inv.bodega_destino_id == stock.bodega_id:
                        current += inv.cantidad
            
            delta = desired - current
            movimiento = None
            if abs(delta) >= Decimal('0.01'):
                if delta > 0:
                    movimiento = Inventario.objects.create(
                        empresa=empresa,
                        articulo=stock.articulo,
                        bodega_destino=stock.bodega,
                        tipo_movimiento='entrada',
                        cantidad=abs(delta),
                        descripcion='Ajuste manual (modal de stock)',
                        estado='confirmado',
                        creado_por=request.user
                    )
                else:
                    movimiento = Inventario.objects.create(
                        empresa=empresa,
                        articulo=stock.articulo,
                        bodega_origen=stock.bodega,
                        tipo_movimiento='salida',
                        cantidad=abs(delta),
                        descripcion='Ajuste manual (modal de stock)',
                        estado='confirmado',
                        creado_por=request.user
                    )
            
            # Actualizar Stock para compatibilidad con otras vistas
            stock.cantidad = desired
            stock.stock_minimo = min_val
            stock.stock_maximo = max_val
            stock.actualizado_por = request.user
            stock.save()
            
            logger.info(f"Stock y ajuste registrados correctamente: StockID={stock.pk}, Delta={delta}")
            
            return JsonResponse({
                'success': True,
                'message': 'Ajuste aplicado exitosamente.' if movimiento else 'Valores de stock guardados.',
                'data': {
                    'cantidad': float(stock.cantidad),
                    'stock_minimo': float(stock.stock_minimo),
                    'stock_maximo': float(stock.stock_maximo),
                    'delta': float(delta),
                    'movimiento': movimiento.tipo_movimiento if movimiento else None
                }
            })
        except Exception as e:
            logger.error(f"Error al guardar stock: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error al guardar: {str(e)}'
            }, status=500)
    else:
        # GET - Generar formulario HTML directamente
        csrf_token = get_token(request)
        
        # Calcular cantidad actual basada en movimientos (confirmados) para alinear con Kardex/stock_list
        cantidad_mov = Decimal('0')
        try:
            inv_qs = (
                Inventario.objects
                .filter(
                    empresa=empresa,
                    articulo=stock.articulo,
                    estado='confirmado'
                )
                .select_related('bodega_origen', 'bodega_destino')
            )
            for inv in inv_qs:
                t = (inv.tipo_movimiento or '').lower()
                if t == 'entrada':
                    if inv.bodega_destino_id == stock.bodega_id:
                        cantidad_mov += inv.cantidad
                elif t == 'salida':
                    if inv.bodega_origen_id == stock.bodega_id:
                        cantidad_mov -= inv.cantidad
                elif t == 'ajuste':
                    if inv.bodega_destino_id == stock.bodega_id:
                        cantidad_mov += inv.cantidad
                elif t == 'transferencia':
                    if inv.bodega_origen_id == stock.bodega_id:
                        cantidad_mov -= inv.cantidad
                    if inv.bodega_destino_id == stock.bodega_id:
                        cantidad_mov += inv.cantidad
        except Exception as e:
            logger.warning(f"No se pudo calcular cantidad por movimientos: {e}")
            cantidad_mov = stock.cantidad
        
        context = {
            'stock': stock,
            'cantidad_mov': cantidad_mov,
        }
        return render(request, 'inventario/includes/stock_form_modal.html', context)
