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
        
        html = f'''
<form method="post" id="formEditarStock">
    <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
    
    <div class="mb-3">
        <label class="form-label fw-bold">Artículo</label>
        <input type="text" class="form-control" value="{stock.articulo.nombre}" readonly>
        <small class="text-muted">Código: {stock.articulo.codigo}</small>
    </div>
    
    <div class="mb-3">
        <label class="form-label fw-bold">Bodega</label>
        <input type="text" class="form-control" value="{stock.bodega.nombre}" readonly>
    </div>
    
    <div class="row">
        <div class="col-md-4">
            <div class="mb-3">
                <label for="id_cantidad" class="form-label fw-bold">
                    <i class="fas fa-boxes me-1"></i>Cantidad Actual
                </label>
                <input type="number" name="cantidad" id="id_cantidad" class="form-control" 
                       step="0.01" value="{cantidad_mov}" required>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="mb-3">
                <label for="id_stock_minimo" class="form-label fw-bold">
                    <i class="fas fa-exclamation-triangle me-1"></i>Stock Mínimo
                </label>
                <input type="number" name="stock_minimo" id="id_stock_minimo" class="form-control" 
                       step="0.01" min="0" value="{stock.stock_minimo}" required>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="mb-3">
                <label for="id_stock_maximo" class="form-label fw-bold">
                    <i class="fas fa-check-circle me-1"></i>Stock Máximo
                </label>
                <input type="number" name="stock_maximo" id="id_stock_maximo" class="form-control" 
                       step="0.01" min="0" value="{stock.stock_maximo}" required>
            </div>
        </div>
    </div>
    
    <div class="alert alert-info">
        <i class="fas fa-info-circle me-2"></i>
        <strong>Nota:</strong> Este formulario solo permite ajustar los valores de stock.
    </div>
    
    <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
            <i class="fas fa-times me-1"></i>Cancelar
        </button>
        <button type="submit" class="btn btn-primary" style="background: linear-gradient(135deg, #8B7355 0%, #6F5B44 100%); border: none;">
            <i class="fas fa-save me-1"></i>Guardar Cambios
        </button>
    </div>
</form>
'''
        
        return HttpResponse(html)
