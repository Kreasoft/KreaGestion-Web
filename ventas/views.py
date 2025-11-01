from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse, Http404
from django.utils import timezone
from django.urls import reverse
from django.template.loader import get_template
from decimal import Decimal
from datetime import datetime, timedelta
from core.decorators import requiere_empresa
from .models import Vendedor, FormaPago, Venta, VentaDetalle, EstacionTrabajo, TIPO_DOCUMENTO_CHOICES
from .forms import VendedorForm, FormaPagoForm, EstacionTrabajoForm
from articulos.models import Articulo, KitOferta
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# ========== VENDEDORES ==========

@login_required
@requiere_empresa
@permission_required('ventas.view_vendedor', raise_exception=True)
def vendedor_list(request):
    """Lista de vendedores"""
    vendedores = Vendedor.objects.filter(empresa=request.empresa).order_by('codigo')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        vendedores = vendedores.filter(
            Q(codigo__icontains=search) |
            Q(nombre__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(vendedores, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    
    return render(request, 'ventas/vendedor_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_vendedor', raise_exception=True)
def vendedor_create(request):
    """Crear nuevo vendedor"""
    if request.method == 'POST':
        form = VendedorForm(request.POST)
        if form.is_valid():
            vendedor = form.save(commit=False)
            vendedor.empresa = request.empresa
            vendedor.save()
            messages.success(request, f'Vendedor {vendedor.nombre} creado exitosamente.')
            return redirect('ventas:vendedor_list')
        else:
            messages.error(request, 'Error al crear el vendedor. Por favor verifica los datos.')
            return redirect('ventas:vendedor_list')
    else:
        return redirect('ventas:vendedor_list')


@login_required
@requiere_empresa
@permission_required('ventas.view_vendedor', raise_exception=True)
def vendedor_detail(request, pk):
    """Detalle de vendedor - Fragmento para modal"""
    vendedor = get_object_or_404(Vendedor, pk=pk, empresa=request.empresa)
    
    html = f"""
    <div class="row">
        <div class="col-6 mb-3">
            <label class="text-muted small">Código</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{vendedor.codigo}</p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Nombre</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{vendedor.nombre}</p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">% Comisión</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{vendedor.porcentaje_comision}%</p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Estado</label>
            <p class="mb-0">
                {'<span class="badge bg-success">Activo</span>' if vendedor.activo else '<span class="badge bg-danger">Inactivo</span>'}
            </p>
        </div>
    </div>
    """
    
    from django.http import HttpResponse
    return HttpResponse(html)


@login_required
@requiere_empresa
@permission_required('ventas.change_vendedor', raise_exception=True)
def vendedor_update(request, pk):
    """Editar vendedor - Fragmento para modal"""
    vendedor = get_object_or_404(Vendedor, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = VendedorForm(request.POST, instance=vendedor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Vendedor {vendedor.nombre} actualizado exitosamente.')
            from django.http import JsonResponse
            return JsonResponse({'success': True})
        else:
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'errors': form.errors})
    
    from django.middleware.csrf import get_token
    csrf_token = get_token(request)
    
    html = f"""
    <form method="post" action="/ventas/vendedores/{vendedor.id}/editar/" id="formEditarVendedorSubmit">
        <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
        <div class="mb-3">
            <label class="form-label" style="font-weight: 600;">Código *</label>
            <input type="text" name="codigo" class="form-control" value="{vendedor.codigo}" required>
        </div>
        <div class="mb-3">
            <label class="form-label" style="font-weight: 600;">Nombre *</label>
            <input type="text" name="nombre" class="form-control" value="{vendedor.nombre}" required>
        </div>
        <div class="mb-3">
            <label class="form-label" style="font-weight: 600;">% Comisión</label>
            <div class="input-group">
                <input type="number" name="porcentaje_comision" class="form-control" min="0" max="100" step="0.01" value="{vendedor.porcentaje_comision}">
                <span class="input-group-text">%</span>
            </div>
        </div>
        <div class="mb-3">
            <div class="form-check form-switch">
                <input type="checkbox" name="activo" class="form-check-input" id="activoEditar" {'checked' if vendedor.activo else ''}>
                <label class="form-check-label" for="activoEditar">Vendedor activo</label>
            </div>
        </div>
        <div class="d-flex justify-content-between">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                <i class="fas fa-times me-2"></i>Cancelar
            </button>
            <button type="submit" class="btn" style="background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%); border: none; color: white;">
                <i class="fas fa-save me-2"></i>Guardar Cambios
            </button>
        </div>
    </form>
    """
    
    from django.http import HttpResponse
    return HttpResponse(html)


@login_required
@requiere_empresa
@permission_required('ventas.delete_vendedor', raise_exception=True)
def vendedor_delete(request, pk):
    """Eliminar vendedor"""
    vendedor = get_object_or_404(Vendedor, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nombre = vendedor.nombre
        vendedor.delete()
        from django.http import JsonResponse
        return JsonResponse({'success': True, 'message': f'Vendedor {nombre} eliminado exitosamente.'})
    
    from django.http import JsonResponse
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# ========== FORMAS DE PAGO ==========

@login_required
@requiere_empresa
@permission_required('ventas.view_formapago', raise_exception=True)
def formapago_list(request):
    """Lista de formas de pago"""
    formas_pago = FormaPago.objects.filter(empresa=request.empresa).order_by('codigo')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        formas_pago = formas_pago.filter(
            Q(codigo__icontains=search) |
            Q(nombre__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(formas_pago, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    
    return render(request, 'ventas/formapago_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_formapago', raise_exception=True)
def formapago_create(request):
    """Crear nueva forma de pago"""
    if request.method == 'POST':
        form = FormaPagoForm(request.POST)
        if form.is_valid():
            forma_pago = form.save(commit=False)
            forma_pago.empresa = request.empresa
            forma_pago.save()
            messages.success(request, f'Forma de pago {forma_pago.nombre} creada exitosamente.')
            return redirect('ventas:formapago_list')
    else:
        form = FormaPagoForm()
    
    context = {
        'form': form,
        'titulo': 'Crear Forma de Pago',
    }
    
    return render(request, 'ventas/formapago_form.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_formapago', raise_exception=True)
def formapago_detail(request, pk):
    """Detalle de forma de pago - Fragmento para modal"""
    forma_pago = get_object_or_404(FormaPago, pk=pk, empresa=request.empresa)
    
    html = f"""
    <div class="row">
        <div class="col-6 mb-3">
            <label class="text-muted small">Código</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{forma_pago.codigo}</p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Nombre</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{forma_pago.nombre}</p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Es Cuenta Corriente</label>
            <p class="mb-0">
                {'<span class="badge" style="background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%); color: #212529;"><i class="fas fa-check me-1"></i>Sí</span>' if forma_pago.es_cuenta_corriente else '<span class="badge" style="background: linear-gradient(135deg, #6c757d 0%, #545b62 100%); color: white;"><i class="fas fa-times me-1"></i>No</span>'}
            </p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Requiere Cheque</label>
            <p class="mb-0">
                {'<span class="badge" style="background: linear-gradient(135deg, #17a2b8 0%, #117a8b 100%); color: white;"><i class="fas fa-check me-1"></i>Sí</span>' if forma_pago.requiere_cheque else '<span class="badge" style="background: linear-gradient(135deg, #6c757d 0%, #545b62 100%); color: white;"><i class="fas fa-times me-1"></i>No</span>'}
            </p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Estado</label>
            <p class="mb-0">
                {'<span class="badge" style="background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%); color: white;">Activo</span>' if forma_pago.activo else '<span class="badge" style="background: linear-gradient(135deg, #dc3545 0%, #bd2130 100%); color: white;">Inactivo</span>'}
            </p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Fecha de Creación</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{forma_pago.fecha_creacion.strftime('%d/%m/%Y %H:%M')}</p>
        </div>
    </div>
    """
    
    from django.http import HttpResponse
    return HttpResponse(html)


@login_required
@requiere_empresa
@permission_required('ventas.change_formapago', raise_exception=True)
def formapago_update(request, pk):
    """Editar forma de pago - Fragmento para modal"""
    forma_pago = get_object_or_404(FormaPago, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = FormaPagoForm(request.POST, instance=forma_pago)
        if form.is_valid():
            form.save()
            messages.success(request, f'Forma de pago {forma_pago.nombre} actualizada exitosamente.')
            from django.http import JsonResponse
            return JsonResponse({'success': True})
        else:
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'errors': form.errors})
    
    from django.middleware.csrf import get_token
    csrf_token = get_token(request)
    
    html = f"""
    <form method="post" action="/ventas/formas-pago/{forma_pago.id}/editar/" id="formEditarFormaPagoSubmit">
        <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
        <div class="mb-3">
            <label class="form-label" style="font-weight: 600;">Código *</label>
            <input type="text" name="codigo" class="form-control" value="{forma_pago.codigo}" required>
        </div>
        <div class="mb-3">
            <label class="form-label" style="font-weight: 600;">Nombre *</label>
            <input type="text" name="nombre" class="form-control" value="{forma_pago.nombre}" required>
        </div>
        <div class="mb-3">
            <div class="form-check form-switch">
                <input type="checkbox" name="es_cuenta_corriente" class="form-check-input" id="esCuentaCorrienteEditar" {'checked' if forma_pago.es_cuenta_corriente else ''}>
                <label class="form-check-label" for="esCuentaCorrienteEditar">
                    Es Cuenta Corriente
                    <small class="text-muted d-block">Si está marcado, la factura pasa a cuenta corriente del cliente</small>
                </label>
            </div>
        </div>
        <div class="mb-3">
            <div class="form-check form-switch">
                <input type="checkbox" name="requiere_cheque" class="form-check-input" id="requiereChequeEditar" {'checked' if forma_pago.requiere_cheque else ''}>
                <label class="form-check-label" for="requiereChequeEditar">
                    Requiere Cheque
                    <small class="text-muted d-block">Si está marcado, se debe registrar información del cheque</small>
                </label>
            </div>
        </div>
        <div class="mb-3">
            <div class="form-check form-switch">
                <input type="checkbox" name="activo" class="form-check-input" id="activoEditar" {'checked' if forma_pago.activo else ''}>
                <label class="form-check-label" for="activoEditar">Forma de pago activa</label>
            </div>
        </div>
    </form>
    """
    
    from django.http import HttpResponse
    return HttpResponse(html)


@login_required
@requiere_empresa
@permission_required('ventas.delete_formapago', raise_exception=True)
def formapago_delete(request, pk):
    """Eliminar forma de pago"""
    forma_pago = get_object_or_404(FormaPago, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nombre = forma_pago.nombre
        forma_pago.delete()
        messages.success(request, f'Forma de pago {nombre} eliminada exitosamente.')
        return redirect('ventas:formapago_list')
    
    context = {
        'forma_pago': forma_pago,
    }
    
    return render(request, 'ventas/formapago_confirm_delete.html', context)


# ========== POS (PUNTO DE VENTA) ==========

@login_required
@requiere_empresa
def pos_main(request):
    """Vista principal del POS"""
    # Obtener datos necesarios
    clientes = Cliente.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    # Crear venta en borrador si no existe
    venta_actual, created = Venta.objects.get_or_create(
        empresa=request.empresa,
        numero_venta='TEMP',
        defaults={
            'fecha': timezone.now().date(),
            'usuario_creacion': request.user,
            'estado': 'borrador'
        }
    )
    
    context = {
        'clientes': clientes,
        'vendedores': vendedores,
        'formas_pago': formas_pago,
        'venta_actual': venta_actual,
    }
    
    return render(request, 'ventas/pos_main.html', context)


@login_required
@requiere_empresa
def pos_buscar_articulo(request):
    """API para buscar artículos por código de barras, código o descripción"""
    try:
        query = request.GET.get('q', '').strip()
        lista_precio_id = request.GET.get('lista_precio', '').strip()
        print(f"=== BÚSQUEDA POS: '{query}' | Lista Precio: {lista_precio_id} ===")
        
        if not query:
            return JsonResponse({'articulos': []})
        
        # Buscar por código de barras, código, nombre o descripción
        articulos = Articulo.objects.filter(
            empresa=request.empresa,
            activo=True
        ).filter(
            Q(codigo_barras__icontains=query) |
            Q(codigo__icontains=query) |
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query)
        ).select_related('categoria', 'categoria__impuesto_especifico').order_by('nombre')[:100]
        
        print(f"Artículos encontrados: {articulos.count()}")
        
        # Obtener precios de la lista si está seleccionada
        precios_lista = {}
        if lista_precio_id:
            from articulos.models import PrecioArticulo
            precios = PrecioArticulo.objects.filter(
                lista_precio_id=lista_precio_id,
                articulo__in=articulos
            ).select_related('articulo')
            
            for precio in precios:
                precios_lista[precio.articulo_id] = float(precio.precio)
        
        results = []
        for articulo in articulos:
            try:
                # Usar precio de la lista si existe, sino usar precio_venta del artículo
                if articulo.id in precios_lista:
                    precio_neto = precios_lista[articulo.id]
                else:
                    precio_neto = float(articulo.precio_venta)
                
                # Calcular IVA solo si la categoría NO está exenta
                if articulo.categoria and articulo.categoria.exenta_iva:
                    iva = 0.0
                else:
                    iva = precio_neto * 0.19
                
                # Calcular impuesto específico si aplica
                impuesto_especifico = 0.0
                impuesto_esp_pct = 0
                if articulo.categoria and articulo.categoria.impuesto_especifico:
                    try:
                        porcentaje_decimal = float(articulo.categoria.impuesto_especifico.get_porcentaje_decimal())
                        impuesto_especifico = precio_neto * porcentaje_decimal
                        impuesto_esp_pct = float(articulo.categoria.impuesto_especifico.porcentaje)
                    except:
                        pass
                
                precio_final = round(precio_neto + iva + impuesto_especifico)
                
                # Obtener stock desde la bodega activa
                from inventario.models import Stock
                stock_disponible = 0
                try:
                    stock_obj = Stock.objects.filter(articulo=articulo, bodega__activa=True).first()
                    if stock_obj:
                        stock_disponible = float(stock_obj.cantidad)
                except:
                    pass
                
                results.append({
                    'id': articulo.id,
                    'codigo': articulo.codigo or '',
                    'codigo_barras': articulo.codigo_barras or '',
                    'nombre': articulo.nombre or '',
                    'descripcion': articulo.descripcion or articulo.nombre or '',
                    'precio': precio_final,
                    'stock': stock_disponible,
                    'categoria_exenta_iva': articulo.categoria.exenta_iva if articulo.categoria else False,
                    'impuesto_especifico_porcentaje': impuesto_esp_pct,
                })
            except Exception as e:
                print(f"Error procesando artículo {articulo.id}: {e}")
                continue
        
        print(f"Retornando {len(results)} artículos para búsqueda '{query}'")
        return JsonResponse({'articulos': results})
    except Exception as e:
        print(f"Error en pos_buscar_articulo: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e), 'articulos': []}, status=500)


@login_required
@requiere_empresa
def pos_agregar_articulo(request):
    """API para agregar un artículo a la venta actual"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    articulo_id = request.POST.get('articulo_id')
    cantidad = request.POST.get('cantidad', '1')
    venta_id = request.POST.get('venta_id')
    
    try:
        articulo = Articulo.objects.get(id=articulo_id, empresa=request.empresa)
        venta = Venta.objects.get(id=venta_id, empresa=request.empresa)
        cantidad = Decimal(cantidad)
        
        if cantidad <= 0:
            return JsonResponse({'success': False, 'error': 'La cantidad debe ser mayor a 0'})
        
        # Verificar stock disponible si el artículo tiene control de stock
        if articulo.control_stock:
            stock_disponible = articulo.stock_disponible
            
            # Verificar si el artículo ya está en la venta para calcular el total
            detalle_existente = VentaDetalle.objects.filter(venta=venta, articulo=articulo).first()
            cantidad_en_venta = detalle_existente.cantidad if detalle_existente else Decimal('0')
            cantidad_total = cantidad_en_venta + cantidad
            
            if cantidad_total > stock_disponible:
                return JsonResponse({
                    'success': False, 
                    'error': f'Stock insuficiente. Disponible: {stock_disponible}, Solicitado: {cantidad_total}'
                })
        
        # Obtener precio considerando cliente (si existe)
        from .utils_precios import obtener_precio_articulo
        precio_unitario = obtener_precio_articulo(
            articulo=articulo,
            cliente=venta.cliente if venta.cliente else None,
            empresa=request.empresa
        )
        
        # Verificar si el artículo ya está en la venta
        detalle_existente = VentaDetalle.objects.filter(venta=venta, articulo=articulo).first()
        
        if detalle_existente:
            # Actualizar cantidad
            detalle_existente.cantidad += cantidad
            detalle_existente.save()
        else:
            # Crear nuevo detalle con precio especial si aplica
            VentaDetalle.objects.create(
                venta=venta,
                articulo=articulo,
                cantidad=cantidad,
                precio_unitario=precio_unitario
            )
        
        return JsonResponse({'success': True})
        
    except Articulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Artículo no encontrado'})
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Venta no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@requiere_empresa
def pos_actualizar_detalle(request):
    """API para actualizar un detalle de la venta"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    detalle_id = request.POST.get('detalle_id')
    cantidad = request.POST.get('cantidad')
    
    try:
        detalle = VentaDetalle.objects.get(id=detalle_id, venta__empresa=request.empresa)
        cantidad = Decimal(cantidad)
        
        if cantidad <= 0:
            return JsonResponse({'success': False, 'error': 'La cantidad debe ser mayor a 0'})
        
        # Verificar stock disponible si el artículo tiene control de stock
        if detalle.articulo.control_stock:
            stock_disponible = detalle.articulo.stock_disponible
            
            if cantidad > stock_disponible:
                return JsonResponse({
                    'success': False, 
                    'error': f'Stock insuficiente. Disponible: {stock_disponible}, Solicitado: {cantidad}'
                })
        
        detalle.cantidad = cantidad
        detalle.save()
        
        return JsonResponse({'success': True})
        
    except VentaDetalle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Detalle no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@requiere_empresa
def pos_eliminar_detalle(request):
    """API para eliminar un detalle de la venta"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    detalle_id = request.POST.get('detalle_id')
    
    try:
        detalle = VentaDetalle.objects.get(id=detalle_id, venta__empresa=request.empresa)
        detalle.delete()
        
        return JsonResponse({'success': True})
        
    except VentaDetalle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Detalle no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@requiere_empresa
def pos_actualizar_venta(request):
    """API para actualizar datos de la venta (cliente, vendedor, etc.)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    venta_id = request.POST.get('venta_id')
    cliente_id = request.POST.get('cliente_id', '')
    vendedor_id = request.POST.get('vendedor_id', '')
    forma_pago_id = request.POST.get('forma_pago_id', '')
    descuento = request.POST.get('descuento', '0')
    
    try:
        venta = Venta.objects.get(id=venta_id, empresa=request.empresa)
        
        # Actualizar campos
        if cliente_id:
            cliente = Cliente.objects.get(id=cliente_id, empresa=request.empresa)
            venta.cliente = cliente
        else:
            venta.cliente = None
            
        if vendedor_id:
            vendedor = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa)
            venta.vendedor = vendedor
        else:
            venta.vendedor = None
            
        if forma_pago_id:
            forma_pago = FormaPago.objects.get(id=forma_pago_id, empresa=request.empresa)
            venta.forma_pago = forma_pago
        else:
            venta.forma_pago = None
        
        venta.descuento = Decimal(descuento)
        venta.save()
        
        return JsonResponse({'success': True})
        
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Venta no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@requiere_empresa
def pos_detalles_venta(request, venta_id):
    """API para obtener los detalles de una venta"""
    try:
        venta = Venta.objects.get(id=venta_id, empresa=request.empresa)
        detalles = VentaDetalle.objects.filter(venta=venta).select_related('articulo')
        
        detalles_data = []
        for detalle in detalles:
            detalles_data.append({
                'id': detalle.id,
                'cantidad': float(detalle.cantidad),
                'precio_unitario': float(detalle.precio_unitario),
                'precio_total': float(detalle.precio_total),
                'impuesto_especifico': float(detalle.impuesto_especifico),
                'articulo': {
                    'codigo': detalle.articulo.codigo,
                    'descripcion': detalle.articulo.descripcion,
                }
            })
        
        totales_data = {
            'subtotal': float(venta.subtotal),
            'descuento': float(venta.descuento),
            'neto': float(venta.neto),
            'iva': float(venta.iva),
            'impuesto_especifico': float(venta.impuesto_especifico),
            'total': float(venta.total),
        }
        
        return JsonResponse({
            'success': True,
            'detalles': detalles_data,
            'totales': totales_data
        })
        
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Venta no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ========== PUNTO DE VENTA (POS) ==========

@login_required
@requiere_empresa
@permission_required('ventas.add_venta', raise_exception=True)
def pos_view(request):
    """Vista principal del Punto de Venta"""
    from articulos.models import Articulo
    from clientes.models import Cliente
    from caja.models import Caja
    from caja.forms import AperturaCajaForm
    from django.contrib import messages
    from django.shortcuts import render
    
    # DEBUG CRÍTICO: Verificar sesión POS
    print("[DEBUG] ==================== POS VIEW ====================")
    print(f"[DEBUG] Session Key: {request.session.session_key}")
    print(f"[DEBUG] pos_estacion_id en sesion: {request.session.get('pos_estacion_id')}")
    print(f"[DEBUG] pos_vendedor_id en sesion: {request.session.get('pos_vendedor_id')}")
    
    # VALIDAR SESIÓN POS ANTES DE CONTINUAR
    estacion_id = request.session.get('pos_estacion_id')
    vendedor_id = request.session.get('pos_vendedor_id')
    
    if not estacion_id or not vendedor_id:
        print("[ERROR] Sesion POS perdida - Redirigiendo a seleccion")
        messages.warning(request, 'Sesión POS perdida. Por favor, seleccione estación y vendedor nuevamente.')
        return redirect('ventas:pos_seleccion')
    
    print(f"[OK] Sesion POS valida - Estacion ID: {estacion_id}, Vendedor ID: {vendedor_id}")
    
    # VALIDACIÓN CRÍTICA: Verificar que haya sucursal activa
    if not hasattr(request, 'sucursal_activa') or not request.sucursal_activa:
        # Renderizar página con SweetAlert
        context = {
            'mostrar_alerta_sucursal': True,
            'mensaje_error': 'No puede operar en el POS sin una sucursal asignada',
            'mensaje_detalle': 'Contacte al administrador para que le asigne una sucursal en su perfil de usuario.'
        }
        return render(request, 'ventas/pos_sin_sucursal.html', context)
    
    # Verificar si hay caja abierta
    apertura_activa = None
    for caja in Caja.objects.filter(empresa=request.empresa, activo=True):
        apertura = caja.get_apertura_activa()
        if apertura:
            apertura_activa = apertura
            break
    
    # Si no hay caja abierta, preparar formulario de apertura
    mostrar_modal_apertura = False
    form_apertura = None
    if not apertura_activa:
        mostrar_modal_apertura = True
        form_apertura = AperturaCajaForm(empresa=request.empresa)
    
    # Obtener datos para el POS con impuesto específico incluido
    articulos_queryset = (
        Articulo.objects
        .filter(empresa=request.empresa, activo=True)
        .select_related('categoria', 'categoria__impuesto_especifico')
        .order_by('-en_oferta', 'nombre')[:500]
    )
    
    # Calcular precios finales directamente en la vista
    articulos = []
    for articulo in articulos_queryset:
        precio_neto = float(articulo.precio_venta)
        
        # Calcular IVA solo si la categoría NO está exenta
        if articulo.categoria and articulo.categoria.exenta_iva:
            iva = 0.0
        else:
            iva = precio_neto * 0.19
        
        # Calcular impuesto específico si aplica
        impuesto_especifico = 0.0
        if articulo.categoria and articulo.categoria.impuesto_especifico:
            porcentaje_decimal = float(articulo.categoria.impuesto_especifico.get_porcentaje_decimal()) / 100
            impuesto_especifico = precio_neto * porcentaje_decimal
        
        precio_final = round(precio_neto + iva + impuesto_especifico)
        articulo.precio_final_calculado = precio_final
        articulos.append(articulo)
    clientes = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')  # Todos los clientes activos
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    estaciones = EstacionTrabajo.objects.filter(empresa=request.empresa, activo=True).order_by('numero')
    
    # Generar próximo número de venta
    ultima_venta = Venta.objects.filter(empresa=request.empresa).order_by('-numero_venta').first()
    if ultima_venta:
        try:
            numero_actual = int(ultima_venta.numero_venta)
            proximo_numero = f"{numero_actual + 1:06d}"
        except ValueError:
            proximo_numero = "000001"
    else:
        proximo_numero = "000001"
    
    # Detectar modo POS de la estación activa
    modo_pos = 'normal'  # Default
    estacion_activa = None
    estacion_id = request.session.get('pos_estacion_id')
    
    if estacion_id:
        try:
            estacion_activa = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa)
            modo_pos = estacion_activa.modo_pos
        except EstacionTrabajo.DoesNotExist:
            pass
    
    # Cargar kits de ofertas disponibles
    kits = KitOferta.objects.filter(
        empresa=request.empresa,
        activo=True
    ).prefetch_related('items__articulo').order_by('-destacado', 'nombre')
    
    # Filtrar solo kits vigentes y con stock
    kits_disponibles = [kit for kit in kits if kit.esta_disponible]
    
    context = {
        'articulos': articulos,
        'clientes': clientes,
        'vendedores': vendedores,
        'formas_pago': formas_pago,
        'estaciones': estaciones,
        'proximo_numero': proximo_numero,
        'apertura_activa': apertura_activa,
        'mostrar_modal_apertura': mostrar_modal_apertura,
        'form_apertura': form_apertura,
        'modo_pos': modo_pos,  # Nuevo
        'estacion_activa': estacion_activa,  # Nuevo
        'kits': kits_disponibles,  # Kits de ofertas
        'max_descuento_lineal': request.empresa.max_descuento_lineal,
        'max_descuento_total': request.empresa.max_descuento_total,
    }
    
    return render(request, 'ventas/pos.html', context)


@login_required
@requiere_empresa
def pos_seleccion_estacion(request):
    """Vista para seleccionar estación de trabajo y vendedor"""
    estaciones = EstacionTrabajo.objects.filter(empresa=request.empresa, activo=True).order_by('numero')
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    context = {
        'estaciones': estaciones,
        'vendedores': vendedores,
    }
    
    return render(request, 'ventas/pos_seleccion.html', context)


@login_required
@requiere_empresa
def pos_iniciar(request):
    """Iniciar POS con estación y vendedor seleccionados"""
    print("[DEBUG] ==================== POS INICIAR ====================")
    print(f"[DEBUG] Metodo: {request.method}")
    print(f"[DEBUG] Usuario: {request.user}")
    print(f"[DEBUG] Empresa: {request.empresa}")
    print(f"[DEBUG] Session Key ANTES: {request.session.session_key}")
    
    if request.method == 'POST':
        estacion_id = request.POST.get('estacion_id')
        vendedor_id = request.POST.get('vendedor_id')
        
        print(f"[DEBUG] POST - Estacion ID: {estacion_id}")
        print(f"[DEBUG] POST - Vendedor ID: {vendedor_id}")
        
        if not estacion_id or not vendedor_id:
            print("[ERROR] Estacion o vendedor no proporcionados")
            return JsonResponse({'success': False, 'message': 'Debe seleccionar estación y vendedor'})
        
        try:
            estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa, activo=True)
            vendedor = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa, activo=True)
            
            print(f"[DEBUG] Estacion encontrada: {estacion.nombre}")
            print(f"[DEBUG] Vendedor encontrado: {vendedor.nombre}")
            
            # Guardar en sesión CON CICLO ASEGURADO
            request.session['pos_estacion_id'] = int(estacion.id)
            request.session['pos_vendedor_id'] = int(vendedor.id)
            request.session['pos_estacion_nombre'] = str(estacion.nombre)
            request.session['pos_vendedor_nombre'] = str(vendedor.nombre)
            request.session['pos_cierre_directo'] = bool(getattr(estacion, 'cierre_directo', False))
            request.session['pos_flujo_directo'] = str(getattr(estacion, 'flujo_cierre_directo', 'rut_final'))
            request.session['pos_enviar_sii_directo'] = bool(getattr(estacion, 'enviar_sii_directo', True))
            
            # TRIPLE GUARDADO FORZADO (evitar race conditions)
            request.session.modified = True
            request.session.save()
            
            # Verificar que se guardó
            print(f"[DEBUG] Verificando guardado...")
            print(f"[DEBUG] - pos_estacion_id: {request.session.get('pos_estacion_id')}")
            print(f"[DEBUG] - pos_vendedor_id: {request.session.get('pos_vendedor_id')}")
            print(f"[DEBUG] - pos_estacion_nombre: {request.session.get('pos_estacion_nombre')}")
            print(f"[DEBUG] - pos_vendedor_nombre: {request.session.get('pos_vendedor_nombre')}")
            print(f"[DEBUG] Session Key DESPUES: {request.session.session_key}")
            print("[OK] Sesion guardada exitosamente")
            
            return JsonResponse({
                'success': True, 
                'message': f'POS iniciado - Estación: {estacion.nombre}, Vendedor: {vendedor.nombre}',
                'redirect_url': reverse('ventas:pos_view'),
                'debug': {
                    'session_key': request.session.session_key,
                    'estacion_id': estacion.id,
                    'vendedor_id': vendedor.id
                }
            })
            
        except (EstacionTrabajo.DoesNotExist, Vendedor.DoesNotExist) as e:
            print(f"[ERROR] Estacion o vendedor no encontrados: {e}")
            return JsonResponse({'success': False, 'message': 'Estación o vendedor no válidos'})
        except Exception as e:
            print(f"[ERROR] Error inesperado en pos_iniciar: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
def pos_session_info(request):
    """Obtener información de la sesión del POS"""
    try:
        print("[DEBUG] ==================== POS SESSION INFO ====================")
        print(f"[DEBUG] Usuario: {request.user}")
        print(f"[DEBUG] Empresa: {request.empresa}")
        
        estacion_id = request.session.get('pos_estacion_id')
        vendedor_id = request.session.get('pos_vendedor_id')
        estacion_nombre = request.session.get('pos_estacion_nombre')
        vendedor_nombre = request.session.get('pos_vendedor_nombre')
        
        print(f"[DEBUG] Estacion ID en sesion: {estacion_id}")
        print(f"[DEBUG] Vendedor ID en sesion: {vendedor_id}")
        print(f"[DEBUG] Estacion Nombre en sesion: {estacion_nombre}")
        print(f"[DEBUG] Vendedor Nombre en sesion: {vendedor_nombre}")
        
        if not estacion_id or not vendedor_id:
            print("[ERROR] Sesion POS no encontrada - Redirigiendo a seleccion")
            return JsonResponse({'success': False, 'message': 'Sesión no encontrada'})
        
        try:
            print(f"[DEBUG] Buscando estacion ID={estacion_id} y vendedor ID={vendedor_id}")
            estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa, activo=True)
            vendedor = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa, activo=True)
            print(f"[OK] Estacion y vendedor encontrados: {estacion.nombre}, {vendedor.nombre}")
            
            # Obtener folios disponibles reales desde la base de datos
            from facturacion_electronica.models import ArchivoCAF
            
            folios_factura = 0
            folios_boleta = 0
            folios_guia = 0
            
            try:
                # Facturas (tipo 33)
                caf_factura = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='33',
                    estado='activo'
                ).first()
                if caf_factura:
                    folios_factura = caf_factura.folio_hasta - caf_factura.folio_actual + 1
                
                # Boletas (tipo 39)
                caf_boleta = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='39',
                    estado='activo'
                ).first()
                if caf_boleta:
                    folios_boleta = caf_boleta.folio_hasta - caf_boleta.folio_actual + 1
                
                # Guías (tipo 52)
                caf_guia = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='52',
                    estado='activo'
                ).first()
                if caf_guia:
                    folios_guia = caf_guia.folio_hasta - caf_guia.folio_actual + 1
            except Exception as e:
                print(f"[WARN] Error al obtener folios disponibles: {e}")
            
            print(f"[DEBUG] Folios disponibles - Factura: {folios_factura}, Boleta: {folios_boleta}, Guia: {folios_guia}")
            print("[OK] Sesion POS valida - Devolviendo datos al frontend")
            
            return JsonResponse({
                'success': True,
                'estacion_id': estacion.id,
                'vendedor_id': vendedor.id,
                'estacion_nombre': estacion_nombre,
                'vendedor_nombre': vendedor_nombre,
                'estacion': {
                    'id': estacion.id,
                    'numero': estacion.numero,
                    'nombre': estacion.nombre,
                    'tipos_documentos': estacion.get_tipos_documentos_permitidos(),
                    'correlativo_ticket': estacion.correlativo_ticket,
                    'max_items': {
                        'factura': estacion.max_items_factura,
                        'boleta': estacion.max_items_boleta,
                        'guia': estacion.max_items_guia,
                        'cotizacion': estacion.max_items_cotizacion,
                        'vale': estacion.max_items_vale,
                    },
                    'folios_factura': folios_factura,
                    'folios_boleta': folios_boleta,
                    'folios_guia': folios_guia,
                }
            })
            
        except (EstacionTrabajo.DoesNotExist, Vendedor.DoesNotExist) as e:
            print(f"[ERROR] Estacion o vendedor no encontrados: {e}")
            return JsonResponse({'success': False, 'message': 'Estación o vendedor no válidos'})
    except Exception as e:
        print(f"[ERROR] Error inesperado en pos_session_info: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'})


@login_required
@requiere_empresa
def pos_buscar_cliente(request):
    """Buscar cliente por RUT o nombre"""
    q = request.GET.get('q', '').strip()
    
    if not q:
        return JsonResponse({'success': False, 'message': 'Término de búsqueda requerido'})
    
    try:
        from clientes.models import Cliente
        from django.db.models import Q
        
        # Búsqueda con filtro de empresa correcto
        if hasattr(request, 'empresa') and request.empresa:
            # Primero buscar en la empresa actual
            clientes = Cliente.objects.filter(
                Q(rut__icontains=q) | Q(nombre__icontains=q),
                empresa=request.empresa,
                estado='activo'
            ).order_by('nombre')[:10]
            
            # Si no hay clientes en esta empresa, mover todos los clientes a esta empresa
            if clientes.count() == 0:
                Cliente.objects.filter(estado='activo').update(empresa=request.empresa)
                
                # Buscar de nuevo
                clientes = Cliente.objects.filter(
                    Q(rut__icontains=q) | Q(nombre__icontains=q),
                    empresa=request.empresa,
                    estado='activo'
                ).order_by('nombre')[:10]
        else:
            # Si no hay empresa, devolver error
            return JsonResponse({'success': False, 'message': 'No se pudo identificar la empresa'})
        
        if clientes.exists():
            clientes_data = []
            for cliente in clientes:
                clientes_data.append({
                    'id': cliente.id,
                    'rut': cliente.rut,
                    'nombre': cliente.nombre,
                    'giro': cliente.giro,
                    'direccion': cliente.direccion,
                    'comuna': cliente.comuna,
                    'ciudad': cliente.ciudad,
                    'telefono': cliente.telefono,
                    'email': cliente.email
                })
            
            return JsonResponse({
                'success': True,
                'clientes': clientes_data
            })
        else:
            return JsonResponse({'success': False, 'message': 'No se encontraron clientes'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error en la búsqueda: {str(e)}'})


@login_required
@requiere_empresa
@permission_required('clientes.add_cliente', raise_exception=True)
def pos_crear_cliente_boleta(request):
    """Crear cliente automático para boletas"""
    if request.method == 'POST':
        try:
            from clientes.models import Cliente
            
            # Verificar si ya existe el cliente de boleta
            cliente_boleta, created = Cliente.objects.get_or_create(
                rut='66666666-6',
                empresa=request.empresa,
                defaults={
                    'nombre': 'CLIENTE BOLETA',
                    'giro': 'Consumidor Final',
                    'direccion': request.empresa.direccion or 'Sin dirección',
                    'comuna': request.empresa.comuna or 'Santiago',
                    'ciudad': request.empresa.ciudad or 'Santiago',
                    'telefono': request.empresa.telefono or '',
                    'email': request.empresa.email or '',
                    'estado': 'activo'
                }
            )
            
            return JsonResponse({
                'success': True,
                'cliente': {
                    'id': cliente_boleta.id,
                    'rut': cliente_boleta.rut,
                    'nombre': cliente_boleta.nombre,
                    'giro': cliente_boleta.giro,
                    'direccion': cliente_boleta.direccion,
                    'comuna': cliente_boleta.comuna,
                    'ciudad': cliente_boleta.ciudad,
                    'telefono': cliente_boleta.telefono,
                    'email': cliente_boleta.email
                },
                'created': created
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al crear cliente: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
@permission_required('clientes.add_cliente', raise_exception=True)
def pos_crear_cliente(request):
    """Crear nuevo cliente"""
    if request.method == 'POST':
        try:
            import json
            from clientes.models import Cliente

            data = json.loads(request.body)

            # Validar datos requeridos
            if not data.get('rut') or not data.get('nombre'):
                return JsonResponse({'success': False, 'message': 'RUT y nombre son requeridos'})

            # Crear cliente con todos los campos requeridos
            cliente = Cliente.objects.create(
                empresa=request.empresa,
                rut=data['rut'],
                nombre=data['nombre'],
                giro=data.get('giro', 'Sin giro'),
                direccion=data.get('direccion', 'Sin dirección'),
                comuna=data.get('comuna', 'Sin especificar'),
                ciudad=data.get('ciudad', 'Sin especificar'),
                region=data.get('region', 'Sin especificar'),  # ← AGREGADO
                telefono=data.get('telefono', 'Sin teléfono'),
                email=data.get('email', ''),
                estado='activo'
            )
            
            return JsonResponse({
                'success': True,
                'cliente': {
                    'id': cliente.id,
                    'rut': cliente.rut,
                    'nombre': cliente.nombre,
                    'giro': cliente.giro,
                    'direccion': cliente.direccion,
                    'comuna': cliente.comuna,
                    'ciudad': cliente.ciudad,
                    'telefono': cliente.telefono,
                    'email': cliente.email
                }
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al crear cliente: {str(e)}'})

    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
def pos_procesar_preventa(request):
    """Procesar preventa"""
    if request.method == 'POST':
        try:
            import json
            from clientes.models import Cliente
            from articulos.models import Articulo

            data = json.loads(request.body)
            
            # Función de limpieza para IDs (elimina espacios, caracteres especiales, etc)
            def clean_id(value):
                """Limpia un ID eliminando espacios no separables y otros caracteres"""
                if value is None:
                    return None
                if isinstance(value, int):
                    return value
                if isinstance(value, str):
                    # Eliminar espacios normales, espacios no separables (\xa0), y otros caracteres raros
                    cleaned = ''.join(filter(str.isdigit, value))
                    return int(cleaned) if cleaned else None
                return value
            
            # Limpiar y obtener IDs
            estacion_id = clean_id(data.get('estacion_id'))
            vendedor_id = clean_id(data.get('vendedor_id'))
            cliente_id = clean_id(data.get('cliente_id'))
            vehiculo_id = clean_id(data.get('vehiculo_id'))
            chofer_id = clean_id(data.get('chofer_id'))
            
            print(f"[DEBUG] IDs limpiados:")
            print(f"  Estacion ID: {data.get('estacion_id')} -> {estacion_id}")
            print(f"  Vendedor ID: {data.get('vendedor_id')} -> {vendedor_id}")
            print(f"  Cliente ID: {data.get('cliente_id')} -> {cliente_id}")
            print(f"  Vehiculo ID: {data.get('vehiculo_id')} -> {vehiculo_id}")
            print(f"  Chofer ID: {data.get('chofer_id')} -> {chofer_id}")

            # Obtener objetos con IDs limpios
            estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa)
            vendedor = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa)
            cliente = Cliente.objects.get(id=cliente_id, empresa=request.empresa)
            
            # Obtener vehículo y chofer si están presentes
            vehiculo = None
            chofer = None
            if vehiculo_id:
                from pedidos.models_transporte import Vehiculo
                vehiculo = Vehiculo.objects.get(id=vehiculo_id, empresa=request.empresa)
            if chofer_id:
                from pedidos.models_transporte import Chofer
                chofer = Chofer.objects.get(id=chofer_id, empresa=request.empresa)
            
            # Generar número de preventa único
            # Buscar el último número de venta de la empresa
            ultima_venta = Venta.objects.filter(empresa=request.empresa).order_by('-id').first()
            if ultima_venta and ultima_venta.numero_venta and ultima_venta.numero_venta != 'TEMP':
                try:
                    ultimo_numero = int(ultima_venta.numero_venta)
                    proximo_numero = f"{ultimo_numero + 1:06d}"
                except ValueError:
                    # Si el número no es convertible, usar correlativo de ticket
                    numero_ticket = estacion.incrementar_correlativo_ticket()
                    proximo_numero = f"{int(numero_ticket):06d}"
            else:
                # Si no hay ventas previas, usar correlativo de ticket
                numero_ticket = estacion.incrementar_correlativo_ticket()
                proximo_numero = f"{int(numero_ticket):06d}"
            
            # Verificar que el número no exista (por seguridad)
            while Venta.objects.filter(empresa=request.empresa, numero_venta=proximo_numero).exists():
                proximo_numero = f"{int(proximo_numero) + 1:06d}"
            
            # Debug: verificar datos recibidos
            print(f"DEBUG - Datos recibidos:")
            print(f"  Estacion ID: {data['estacion_id']} (tipo: {type(data['estacion_id'])})")
            print(f"  Vendedor ID: {data['vendedor_id']} (tipo: {type(data['vendedor_id'])})")
            print(f"  Cliente ID: {data['cliente_id']} (tipo: {type(data['cliente_id'])})")
            print(f"  Items: {len(data['items'])}")
            for i, item in enumerate(data['items']):
                print(f"    Item {i}: {item}")
            print(f"  Totales: {data['totales']}")
            
            # Convertir valores a Decimal para evitar errores de tipo
            from decimal import Decimal
            
            # Crear preventa
            # Usar los valores calculados correctamente desde el frontend
            subtotal = Decimal(str(data['totales']['subtotal']))
            neto = Decimal(str(data['totales']['neto']))
            iva = Decimal(str(data['totales']['iva']))
            impuesto_especifico = Decimal(str(data['totales']['impuesto_especifico']))
            total = Decimal(str(data['totales']['total']))
            descuento = Decimal(str(data['totales']['descuento']))
            
            print(f"DEBUG - Valores a guardar en BD:")
            print(f"  Subtotal: {subtotal}")
            print(f"  Neto: {neto}")
            print(f"  IVA: {iva}")
            print(f"  Impuesto Específico: {impuesto_especifico}")
            print(f"  Total: {total}")

            # VALIDACIÓN CRÍTICA: Verificar sucursal activa
            if not hasattr(request, 'sucursal_activa') or not request.sucursal_activa:
                return JsonResponse({
                    'success': False,
                    'error': 'No puede procesar ventas sin una sucursal asignada. Contacte al administrador.'
                }, status=400)
            
            preventa = Venta.objects.create(
                empresa=request.empresa,
                sucursal=request.sucursal_activa,  # ← ASIGNAR SUCURSAL AUTOMÁTICAMENTE
                numero_venta=proximo_numero,
                cliente=cliente,
                vendedor=vendedor,
                vehiculo=vehiculo,  # ← GUARDAR VEHÍCULO
                chofer=chofer,  # ← GUARDAR CHOFER
                estacion_trabajo=estacion,
                tipo_documento=data['tipo_documento'],
                tipo_documento_planeado=data.get('tipo_documento_planeado', data['tipo_documento']),  # ← GUARDAR TIPO PLANEADO
                tipo_despacho=data.get('tipo_despacho'),  # ← GUARDAR TIPO DE DESPACHO
                subtotal=subtotal,
                descuento=descuento,
                neto=neto,
                iva=iva,
                impuesto_especifico=impuesto_especifico,
                total=total,
                estado='borrador',
                estado_cotizacion='pendiente' if data['tipo_documento'] == 'cotizacion' else None,
                usuario_creacion=request.user
            )
            
            # Crear detalles
            print("DEBUG - Creando detalles de venta...")
            for i, item in enumerate(data['items']):
                print(f"DEBUG - Procesando item {i}: {item}")
                articulo_id_limpio = clean_id(item.get('articuloId'))
                print(f"DEBUG - Buscando artículo ID: {item.get('articuloId')} -> {articulo_id_limpio}")
                articulo = Articulo.objects.get(id=articulo_id_limpio, empresa=request.empresa)
                print(f"DEBUG - Artículo encontrado: {articulo.nombre}")
                
                print(f"DEBUG - Creando VentaDetalle...")
                print(f"DEBUG - Valores a crear:")
                print(f"  cantidad: {Decimal(str(item['cantidad']))}")
                print(f"  precio_unitario: {Decimal(str(item['precio']))}")
                print(f"  precio_total: {Decimal(str(item['total']))}")
                
                try:
                    VentaDetalle.objects.create(
                        venta=preventa,
                        articulo=articulo,
                        cantidad=Decimal(str(item['cantidad'])),
                        precio_unitario=Decimal(str(item['precio'])),
                        precio_total=Decimal(str(item['total'])),
                        impuesto_especifico=Decimal('0.00')
                    )
                    print(f"DEBUG - VentaDetalle creado exitosamente")
                except Exception as e:
                    print(f"ERROR al crear VentaDetalle: {e}")
                    print(f"Tipo de error: {type(e)}")
                    raise e
            
            # Crear referencias si existen
            if data.get('referencias'):
                print(f"DEBUG - Creando {len(data['referencias'])} referencias...")
                from .models import VentaReferencia
                from datetime import datetime
                
                for ref in data['referencias']:
                    try:
                        VentaReferencia.objects.create(
                            venta=preventa,
                            tipo_referencia=ref['tipo'],
                            folio_referencia=ref['folio'],
                            fecha_referencia=datetime.strptime(ref['fecha'], '%Y-%m-%d').date(),
                            razon_referencia=ref.get('razon', '')
                        )
                        print(f"DEBUG - Referencia creada: {ref['tipo']} - {ref['folio']}")
                    except Exception as e:
                        print(f"ERROR al crear referencia: {e}")
                        # No detenemos el proceso si falla una referencia
            
            # Si el documento es factura, boleta o guía, generar también un ticket facturable (vale)
            ticket_vale_id = None
            ticket_vale_numero = None
            if data['tipo_documento'] in ['factura', 'boleta', 'guia']:
                print(f"DEBUG - Generando ticket facturable (vale) para {data['tipo_documento']}...")
                
                # Generar número de vale único
                ultima_venta_vale = Venta.objects.filter(empresa=request.empresa).order_by('-id').first()
                if ultima_venta_vale and ultima_venta_vale.numero_venta and ultima_venta_vale.numero_venta != 'TEMP':
                    try:
                        ultimo_numero_vale = int(ultima_venta_vale.numero_venta)
                        numero_vale = f"{ultimo_numero_vale + 1:06d}"
                    except ValueError:
                        numero_ticket_vale = estacion.incrementar_correlativo_ticket()
                        numero_vale = f"{int(numero_ticket_vale):06d}"
                else:
                    numero_ticket_vale = estacion.incrementar_correlativo_ticket()
                    numero_vale = f"{int(numero_ticket_vale):06d}"
                
                # Verificar que el número no exista
                while Venta.objects.filter(empresa=request.empresa, numero_venta=numero_vale).exists():
                    numero_vale = f"{int(numero_vale) + 1:06d}"
                
                # Crear el vale
                print(f"DEBUG - Creando ticket vale...")
                print(f"DEBUG - Items recibidos: {len(data['items'])}")
                
                ticket_vale = Venta.objects.create(
                    empresa=request.empresa,
                    numero_venta=numero_vale,
                    fecha=timezone.now().date(),  # Establecer fecha explícitamente
                    cliente=cliente,
                    vendedor=vendedor,
                    estacion_trabajo=estacion,
                    tipo_documento='vale',
                    tipo_documento_planeado=data['tipo_documento'],  # ← GUARDAR TIPO PLANEADO
                    subtotal=subtotal,
                    descuento=descuento,
                    neto=neto,
                    iva=iva,
                    impuesto_especifico=impuesto_especifico,
                    total=total,
                    estado='borrador',
                    usuario_creacion=request.user,
                    observaciones=f"Ticket generado automáticamente para {data['tipo_documento']} #{proximo_numero}"
                )

                # Crear detalles del vale
                for item in data['items']:
                    articulo_id_limpio = clean_id(item.get('articuloId'))
                    articulo = Articulo.objects.get(id=articulo_id_limpio, empresa=request.empresa)
                    
                    # Obtener impuesto específico del item (viene del carrito del POS)
                    impuesto_esp_item = Decimal(str(item.get('impuesto_especifico', 0)))
                    
                    print(f"DEBUG - Item: {item.get('nombre', 'Sin nombre')}")
                    print(f"DEBUG - Impuesto específico unitario: {impuesto_esp_item}")
                    print(f"DEBUG - Cantidad: {item['cantidad']}")
                    print(f"DEBUG - Impuesto específico total: {impuesto_esp_item * Decimal(str(item['cantidad']))}")
                    
                    VentaDetalle.objects.create(
                        venta=ticket_vale,
                        articulo=articulo,
                        cantidad=Decimal(str(item['cantidad'])),
                        precio_unitario=Decimal(str(item['precio'])),
                        precio_total=Decimal(str(item['total'])),
                        impuesto_especifico=impuesto_esp_item * Decimal(str(item['cantidad']))
                    )

                ticket_vale_id = ticket_vale.id
                ticket_vale_numero = numero_vale
                print(f"DEBUG - Ticket facturable (vale) #{numero_vale} generado exitosamente")
                
                # CIERRE DIRECTO: Procesar automáticamente el ticket y generar DTE
                if estacion.cierre_directo:
                    print(f"[CIERRE DIRECTO] Procesando ticket automaticamente")
                    
                    # Procesar el ticket automáticamente
                    try:
                        from caja.models import AperturaCaja, Caja, VentaProcesada, MovimientoCaja
                        from django.db import transaction
                        
                        # Buscar apertura activa
                        apertura_activa = None
                        for caja in Caja.objects.filter(empresa=request.empresa, activo=True):
                            apertura = caja.get_apertura_activa()
                            if apertura:
                                apertura_activa = apertura
                                break
                        
                        if not apertura_activa:
                            # Si no hay caja abierta, redirigir a pantalla de caja normal
                            print(f"[WARN] CIERRE DIRECTO: No hay caja abierta, redirigiendo a pantalla de caja")
                            return JsonResponse({
                                'success': True,
                                'numero_preventa': proximo_numero,
                                'tipo_documento': data['tipo_documento'],
                                'preventa_id': preventa.id,
                                'ticket_vale_id': ticket_vale_id,
                                'ticket_vale_numero': ticket_vale_numero,
                                'cierre_directo': False,
                                'error_caja': 'No hay caja abierta'
                            })
                        
                        # Obtener forma de pago por defecto (Efectivo)
                        forma_pago = FormaPago.objects.filter(
                            empresa=request.empresa,
                            codigo__iexact='EF'
                        ).first()
                        
                        if not forma_pago:
                            # Si no existe efectivo, usar la primera forma de pago activa
                            forma_pago = FormaPago.objects.filter(
                                empresa=request.empresa,
                                activo=True
                            ).first()
                        
                        if not forma_pago:
                            print(f"[WARN] CIERRE DIRECTO: No hay formas de pago configuradas")
                            return JsonResponse({
                                'success': False,
                                'message': 'No hay formas de pago configuradas'
                            }, status=400)
                        
                        # Procesar el ticket con transacción atómica
                        with transaction.atomic():
                            # Generar número de venta temporal (será reemplazado por el folio del DTE)
                            # Buscar el número más alto existente
                            ventas_existentes = Venta.objects.filter(
                                empresa=request.empresa
                            ).order_by('-numero_venta')
                            
                            numero = 1
                            if ventas_existentes.exists():
                                for venta_temp in ventas_existentes[:20]:
                                    try:
                                        num_actual = int(venta_temp.numero_venta)
                                        if num_actual >= numero:
                                            numero = num_actual + 1
                                    except ValueError:
                                        continue
                            
                            # Buscar número disponible
                            numero_venta_temp = f"{numero:06d}"
                            while Venta.objects.filter(
                                empresa=request.empresa,
                                numero_venta=numero_venta_temp
                            ).exists():
                                numero += 1
                                numero_venta_temp = f"{numero:06d}"
                            
                            print(f"[CIERRE DIRECTO] Numero de venta temporal: {numero_venta_temp}")
                            
                            # Primero generar el DTE para obtener el folio correcto
                            dte = None
                            numero_venta_final = numero_venta_temp
                            
                            if data['tipo_documento'] in ['factura', 'boleta', 'guia']:
                                try:
                                    from facturacion_electronica.dte_service import DTEService
                                    from facturacion_electronica.models import DocumentoTributarioElectronico, CAF
                                    
                                    print(f"[CIERRE DIRECTO] Verificando si ya existe DTE para ticket {ticket_vale.id}...")
                                    
                                    # Mapear tipo de documento a código SII
                                    tipo_dte_map = {
                                        'factura': '33',  # Factura Electrónica
                                        'boleta': '39',   # Boleta Electrónica
                                        'guia': '52',     # Guía de Despacho Electrónica
                                    }
                                    tipo_dte_codigo = tipo_dte_map.get(data['tipo_documento'], '39')
                                    
                                    # VALIDAR FOLIOS DISPONIBLES ANTES DE CONTINUAR
                                    print(f"[VALIDACION] Verificando folios disponibles para tipo DTE {tipo_dte_codigo}...")
                                    from facturacion_electronica.models import ArchivoCAF
                                    caf_disponible = ArchivoCAF.objects.filter(
                                        empresa=request.empresa,
                                        tipo_documento=tipo_dte_codigo,
                                        estado='activo'
                                    ).first()
                                    
                                    if not caf_disponible:
                                        nombres_doc = {'33': 'Facturas', '39': 'Boletas', '52': 'Guías de Despacho'}
                                        nombre_doc = nombres_doc.get(tipo_dte_codigo, 'Documentos')
                                        
                                        print(f"[ERROR] NO HAY FOLIOS DISPONIBLES para {nombre_doc}")
                                        return JsonResponse({
                                            'success': False,
                                            'error': 'sin_folios',
                                            'message': f'No hay folios disponibles para emitir {nombre_doc}',
                                            'detalle': f'Debe cargar un archivo CAF activo para {nombre_doc} en Facturación Electrónica → Gestión de CAF',
                                            'tipo_documento': data['tipo_documento']
                                        }, status=400)
                                    
                                    # Verificar si ya existe un DTE para este ticket
                                    # Buscar por VentaProcesada asociada al ticket
                                    from caja.models import VentaProcesada as VentaProcesadaCheck
                                    venta_proc_existente = VentaProcesadaCheck.objects.filter(
                                        venta_preventa=ticket_vale,
                                        dte_generado__isnull=False
                                    ).first()
                                    
                                    if venta_proc_existente and venta_proc_existente.dte_generado:
                                        # Ya existe un DTE para este ticket, reutilizarlo
                                        dte = venta_proc_existente.dte_generado
                                        numero_venta_final = f"{dte.folio:06d}"
                                        print(f"[OK] CIERRE DIRECTO: DTE ya existe - Folio {dte.folio} (reutilizando)")
                                        
                                        # Actualizar el número de venta del ticket_vale
                                        ticket_vale.numero_venta = numero_venta_final
                                        ticket_vale.tipo_documento = data['tipo_documento']
                                        ticket_vale.estado = 'confirmada'
                                        ticket_vale.save()
                                    else:
                                        # No existe DTE, generar uno nuevo
                                        print(f"[CIERRE DIRECTO] Generando DTE nuevo para obtener folio...")
                                        
                                        # Preparar venta temporal para generar DTE
                                        ticket_vale.numero_venta = numero_venta_temp
                                        ticket_vale.tipo_documento = data['tipo_documento']
                                        ticket_vale.estado = 'confirmada'
                                        ticket_vale.save()
                                        
                                        # Generar DTE
                                        dte_service = DTEService(request.empresa)
                                        dte = dte_service.generar_dte_desde_venta(ticket_vale, tipo_dte_codigo)
                                        
                                        if dte:
                                            # Usar el folio del DTE como número de venta final
                                            numero_venta_final = f"{dte.folio:06d}"
                                            print(f"[OK] CIERRE DIRECTO: DTE generado - Folio {dte.folio}")
                                            print(f"[OK] CIERRE DIRECTO: Número de venta final actualizado a: {numero_venta_final}")
                                            
                                            # Actualizar el número de venta del ticket_vale con el folio
                                            ticket_vale.numero_venta = numero_venta_final
                                            ticket_vale.save()
                                        
                                except Exception as e_dte:
                                    print(f"[ERROR] CIERRE DIRECTO: Error al generar DTE: {e_dte}")
                                    import traceback
                                    traceback.print_exc()
                                    # Continuar sin DTE, usar número temporal
                            
                            # Verificar si ya existe una venta final con ese folio
                            venta_final = Venta.objects.filter(
                                empresa=request.empresa,
                                tipo_documento=data['tipo_documento'],
                                numero_venta=numero_venta_final
                            ).first()
                            
                            if not venta_final:
                                # Crear venta final definitiva solo si no existe
                                venta_final = Venta.objects.create(
                                    empresa=request.empresa,
                                    sucursal=ticket_vale.sucursal,  # Usar sucursal del ticket
                                    tipo_documento=data['tipo_documento'],
                                    numero_venta=numero_venta_final,
                                    cliente=cliente,
                                    vendedor=ticket_vale.vendedor,
                                    estado='confirmada',
                                    subtotal=ticket_vale.subtotal,
                                    descuento=ticket_vale.descuento,
                                    neto=ticket_vale.neto,
                                    iva=ticket_vale.iva,
                                    total=ticket_vale.total,
                                    fecha=timezone.now().date(),
                                    usuario_creacion=request.user
                                )
                                
                                # Copiar detalles del ticket a la venta final
                                for detalle in ticket_vale.detalles.all():
                                    VentaDetalle.objects.create(
                                        venta=venta_final,
                                        articulo=detalle.articulo,
                                        cantidad=detalle.cantidad,
                                        precio_unitario=detalle.precio_unitario,
                                        precio_total=detalle.precio_total,
                                        impuesto_especifico=detalle.impuesto_especifico
                                    )
                                print(f"[OK] CIERRE DIRECTO: Venta final creada - ID {venta_final.id}")
                            else:
                                print(f"[INFO] CIERRE DIRECTO: Venta final ya existe - ID {venta_final.id}, reutilizando")
                            
                            # Si hay DTE, asociarlo a la venta final
                            if dte:
                                dte.venta = venta_final
                                dte.save()
                            
                            # Crear movimiento de caja (solo si no es guía de despacho)
                            movimiento_caja = None
                            if data['tipo_documento'] != 'guia':
                                movimiento_caja = MovimientoCaja.objects.create(
                                    apertura=apertura_activa,
                                    tipo='ingreso',
                                    forma_pago=forma_pago,
                                    monto=total,
                                    descripcion=f"{data['tipo_documento'].title()} #{numero_venta_final}",
                                    registrado_por=request.user
                                )
                            
                            # Crear venta procesada con los campos correctos del modelo
                            venta_procesada = VentaProcesada.objects.create(
                                venta_preventa=ticket_vale,
                                venta_final=venta_final,
                                apertura_caja=apertura_activa,
                                movimiento_caja=movimiento_caja,
                                usuario_proceso=request.user,
                                monto_recibido=total,
                                monto_cambio=Decimal('0.00'),
                                stock_descontado=True,
                                dte_generado=dte
                            )
                            
                            # Descontar stock
                            from inventario.models import Inventario
                            bodega_caja = apertura_activa.caja.bodega
                            
                            for detalle in ticket_vale.detalles.all():
                                # Buscar inventario en la bodega de la caja
                                inventario = Inventario.objects.filter(
                                    empresa=request.empresa,
                                    bodega=bodega_caja,
                                    articulo=detalle.articulo,
                                    activo=True
                                ).first()
                                
                                if inventario:
                                    inventario.cantidad_disponible -= detalle.cantidad
                                    inventario.save()
                            
                            # Generar URL del documento y enviar al SII si corresponde
                            doc_url = None
                            if dte:
                                # Generar URL del documento electrónico
                                from django.urls import reverse
                                doc_url = reverse('facturacion_electronica:ver_factura_electronica', args=[dte.pk])
                                
                                # Enviar al SII si está configurado
                                if estacion.enviar_sii_directo and request.empresa.facturacion_electronica:
                                    try:
                                        from facturacion_electronica.dte_service import DTEService
                                        dte_service = DTEService(request.empresa)
                                        print("[INFO] CIERRE DIRECTO: Enviando DTE al SII...")
                                        dte_service.enviar_dte_al_sii(dte)
                                        print("[OK] CIERRE DIRECTO: DTE enviado al SII")
                                    except Exception as e_envio:
                                        print(f"[WARN] CIERRE DIRECTO: Error al enviar DTE al SII: {e_envio}")
                            
                            # Marcar ticket como procesado
                            ticket_vale.estado = 'confirmada'
                            ticket_vale.save()
                            
                            print("=" * 80)
                            print("[OK] VENTA PROCESADA EXITOSAMENTE")
                            print(f"   Venta Final ID: {venta_final.id}")
                            print(f"   Numero: {numero_venta_final}")
                            print(f"   Tipo: {data['tipo_documento']}")
                            print(f"   Total: ${total}")
                            print(f"   DTE Generado: {dte.id if dte else None}")
                            print("=" * 80)
                            
                            # Retornar respuesta con documento generado
                            return JsonResponse({
                                'success': True,
                                'cierre_directo': True,
                                'tipo_documento': data['tipo_documento'],
                                'numero_venta': numero_venta_final,
                                'doc_url': doc_url or '',
                                'ticket_vale_id': ticket_vale_id,
                                'ticket_vale_numero': ticket_vale_numero,
                                'venta_final_id': venta_final.id
                            })
                    
                    except Exception as e_cierre:
                        print(f"[ERROR] ERROR en cierre directo: {e_cierre}")
                        import traceback
                        traceback.print_exc()
                        # Si falla el cierre directo, redirigir a pantalla de caja normal
                        return JsonResponse({
                            'success': True,
                            'numero_preventa': proximo_numero,
                            'tipo_documento': data['tipo_documento'],
                            'preventa_id': preventa.id,
                            'ticket_vale_id': ticket_vale_id,
                            'ticket_vale_numero': ticket_vale_numero,
                            'cierre_directo': False,
                            'error_cierre': str(e_cierre)
                        })
            
            # Retorno normal (sin cierre directo)
            return JsonResponse({
                'success': True,
                'numero_preventa': proximo_numero,
                'tipo_documento': data['tipo_documento'],
                'preventa_id': preventa.id,
                'ticket_vale_id': ticket_vale_id,
                'ticket_vale_numero': ticket_vale_numero
            })
            
        except Exception as e:
            import traceback
            print("=" * 80)
            print("ERROR AL PROCESAR PREVENTA:")
            print(f"Error: {str(e)}")
            print("Traceback completo:")
            print(traceback.format_exc())
            print("=" * 80)
            return JsonResponse({'success': False, 'message': f'Error al procesar preventa: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# ========== ESTACIONES DE TRABAJO ==========

@login_required
@requiere_empresa
@permission_required('ventas.view_estaciontrabajo', raise_exception=True)
def estaciontrabajo_list(request):
    """Lista de estaciones de trabajo"""
    estaciones = EstacionTrabajo.objects.filter(empresa=request.empresa).order_by('numero')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        estaciones = estaciones.filter(
            Q(numero__icontains=search) |
            Q(nombre__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(estaciones, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    
    return render(request, 'ventas/estaciontrabajo_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_estaciontrabajo', raise_exception=True)
def estaciontrabajo_create(request):
    """Crear nueva estación de trabajo"""
    if request.method == 'POST':
        form = EstacionTrabajoForm(request.POST)
        if form.is_valid():
            estacion = form.save(commit=False)
            estacion.empresa = request.empresa
            estacion.save()
            response = JsonResponse({'success': True, 'message': 'Estación de trabajo creada exitosamente'})
            response['Content-Type'] = 'application/json'
            return response
        else:
            response = JsonResponse({'success': False, 'errors': form.errors})
            response['Content-Type'] = 'application/json'
            return response

    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
@permission_required('ventas.view_estaciontrabajo', raise_exception=True)
def estaciontrabajo_detail(request, pk):
    """Detalle de estación de trabajo"""
    try:
        estacion = EstacionTrabajo.objects.get(pk=pk, empresa=request.empresa)
        return render(request, 'ventas/estaciontrabajo_detail.html', {'estacion': estacion})
    except EstacionTrabajo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Estación de trabajo no encontrada'})


@login_required
@requiere_empresa
@permission_required('ventas.change_estaciontrabajo', raise_exception=True)
def estaciontrabajo_edit(request, pk):
    """Editar estación de trabajo"""
    try:
        estacion = EstacionTrabajo.objects.get(pk=pk, empresa=request.empresa)

        if request.method == 'POST':
            form = EstacionTrabajoForm(request.POST, instance=estacion)
            if form.is_valid():
                form.save()
                response = JsonResponse({'success': True, 'message': 'Estación de trabajo actualizada exitosamente'})
                response['Content-Type'] = 'application/json'
                return response
            else:
                response = JsonResponse({'success': False, 'errors': form.errors})
                response['Content-Type'] = 'application/json'
                return response

        # Para peticiones GET, devolver HTML del formulario modal
        form = EstacionTrabajoForm(instance=estacion)

        from django.middleware.csrf import get_token
        csrf_token = get_token(request)

        html = f"""
        <form method="post" action="/ventas/estaciones-trabajo/{estacion.id}/editar/" id="formEditarEstacionSubmit">
            <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">

            <div class="row">
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label" style="font-weight: 600;">Número de Estación *</label>
                        <input type="text" name="numero" class="form-control" value="{estacion.numero}" required maxlength="10">
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label" style="font-weight: 600;">Nombre *</label>
                        <input type="text" name="nombre" class="form-control" value="{estacion.nombre}" required>
                    </div>
                </div>
            </div>

            <div class="mb-3">
                <label class="form-label" style="font-weight: 600;">Descripción</label>
                <textarea name="descripcion" class="form-control" rows="3">{estacion.descripcion}</textarea>
            </div>

            <!-- Modo de Operación POS -->
            <div class="mb-4">
                <h6 style="color: #2c3e50; font-weight: 600; margin-bottom: 15px;">
                    <i class="fas fa-cog me-2"></i>Configuración del POS
                </h6>
                <div class="mb-3">
                    <label class="form-label" style="font-weight: 600;">Modo de Operación POS *</label>
                    <select name="modo_pos" class="form-select" required>
                        <option value="normal" {'selected' if estacion.modo_pos == 'normal' else ''}>Normal - Cliente al final</option>
                        <option value="con_cliente" {'selected' if estacion.modo_pos == 'con_cliente' else ''}>Con Cliente - Cliente al inicio</option>
                    </select>
                    <small class="text-muted d-block mt-1">
                        <i class="fas fa-info-circle me-1"></i>
                        <strong>Normal:</strong> Cliente opcional al final de la venta (modo tradicional).<br>
                        <i class="fas fa-info-circle me-1"></i>
                        <strong>Con Cliente:</strong> Selección obligatoria de cliente al inicio para aplicar precios especiales y descuentos personalizados.
                    </small>
                </div>
            </div>

            <!-- Cierre directo -->
            <div class="row">
                <div class="col-md-12">
                    <div class="form-check form-switch mb-3">
                        <input type="checkbox" name="cierre_directo" class="form-check-input" id="cierreDirectoEditar" {'checked' if getattr(estacion, 'cierre_directo', False) else ''}>
                        <label class="form-check-label" for="cierreDirectoEditar">
                            <i class="fas fa-bolt me-2"></i>Cierre directo (Cerrar y Emitir DTE)
                        </label>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label" style="font-weight: 600;">Flujo para cierre directo</label>
                        <select name="flujo_cierre_directo" class="form-select">
                            <option value="rut_inicio" {'selected' if getattr(estacion, 'flujo_cierre_directo', 'rut_final') == 'rut_inicio' else ''}>RUT al inicio</option>
                            <option value="rut_final" {'selected' if getattr(estacion, 'flujo_cierre_directo', 'rut_final') == 'rut_final' else ''}>RUT al final</option>
                        </select>
                        <small class="text-muted d-block mt-1">
                            <i class="fas fa-info-circle me-1"></i>
                            RUT al inicio: solicita cliente antes de vender. RUT al final: cliente al cierre.
                        </small>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="form-check form-switch mb-3">
                        <input type="checkbox" name="enviar_sii_directo" class="form-check-input" id="enviarSIIEditar" {'checked' if getattr(estacion, 'enviar_sii_directo', True) else ''}>
                        <label class="form-check-label" for="enviarSIIEditar">
                            <i class="fas fa-paper-plane me-2"></i>Enviar al SII automáticamente
                        </label>
                    </div>
                </div>
            </div>

            <div class="mb-3">
                <label class="form-label" style="font-weight: 600;">Correlativo de Ticket</label>
                <input type="number" name="correlativo_ticket" class="form-control" value="{estacion.correlativo_ticket}" min="1">
                <div class="form-text">Número inicial para el correlativo único de tickets</div>
            </div>

            <!-- Tipos de documentos permitidos -->
            <div class="mb-4">
                <h6 style="color: #2c3e50; font-weight: 600; margin-bottom: 15px;">
                    <i class="fas fa-file-alt me-2"></i>Tipos de Documentos Permitidos
                </h6>
                <div class="row">
                    <div class="col-md-6">
                        <div class="form-check form-switch mb-3">
                            <input type="checkbox" name="puede_facturar" class="form-check-input" id="puedeFacturarEditar" {'checked' if estacion.puede_facturar else ''}>
                            <label class="form-check-label" for="puedeFacturarEditar">
                                <i class="fas fa-file-invoice me-2"></i>Puede Emitir Facturas
                            </label>
                        </div>
                        <div class="form-check form-switch mb-3">
                            <input type="checkbox" name="puede_boletar" class="form-check-input" id="puedeBoletarEditar" {'checked' if estacion.puede_boletar else ''}>
                            <label class="form-check-label" for="puedeBoletarEditar">
                                <i class="fas fa-receipt me-2"></i>Puede Emitir Boletas
                            </label>
                        </div>
                        <div class="form-check form-switch mb-3">
                            <input type="checkbox" name="puede_guia" class="form-check-input" id="puedeGuiaEditar" {'checked' if estacion.puede_guia else ''}>
                            <label class="form-check-label" for="puedeGuiaEditar">
                                <i class="fas fa-truck me-2"></i>Puede Emitir Guías
                            </label>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="form-check form-switch mb-3">
                            <input type="checkbox" name="puede_cotizar" class="form-check-input" id="puedeCotizarEditar" {'checked' if estacion.puede_cotizar else ''}>
                            <label class="form-check-label" for="puedeCotizarEditar">
                                <i class="fas fa-calculator me-2"></i>Puede Emitir Cotizaciones
                            </label>
                        </div>
                        <div class="form-check form-switch mb-3">
                            <input type="checkbox" name="puede_vale" class="form-check-input" id="puedeValeEditar" {'checked' if estacion.puede_vale else ''}>
                            <label class="form-check-label" for="puedeValeEditar">
                                <i class="fas fa-ticket-alt me-2"></i>Puede Emitir Vales
                            </label>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Límites de items -->
            <div class="mb-4">
                <h6 style="color: #2c3e50; font-weight: 600; margin-bottom: 15px;">
                    <i class="fas fa-list-ol me-2"></i>Límites de Items por Documento
                </h6>
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label">Máx. Items Factura</label>
                            <input type="number" name="max_items_factura" class="form-control" value="{estacion.max_items_factura}" min="1" max="100">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Máx. Items Boleta</label>
                            <input type="number" name="max_items_boleta" class="form-control" value="{estacion.max_items_boleta}" min="1" max="100">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Máx. Items Guía</label>
                            <input type="number" name="max_items_guia" class="form-control" value="{estacion.max_items_guia}" min="1" max="100">
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label">Máx. Items Cotización</label>
                            <input type="number" name="max_items_cotizacion" class="form-control" value="{estacion.max_items_cotizacion}" min="1" max="100">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Máx. Items Vale</label>
                            <input type="number" name="max_items_vale" class="form-control" value="{estacion.max_items_vale}" min="1" max="100">
                        </div>
                    </div>
                </div>
            </div>

            <div class="form-check form-switch">
                <input type="checkbox" name="activo" class="form-check-input" id="activoEditar" {'checked' if estacion.activo else ''}>
                <label class="form-check-label" for="activoEditar">Estación activa</label>
            </div>
        </form>
        """

        from django.http import HttpResponse
        return HttpResponse(html)

    except EstacionTrabajo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Estación de trabajo no encontrada'})


@login_required
@requiere_empresa
@permission_required('ventas.delete_estaciontrabajo', raise_exception=True)
def estaciontrabajo_delete(request, pk):
    """Eliminar estación de trabajo"""
    if request.method == 'POST':
        try:
            estacion = EstacionTrabajo.objects.get(pk=pk, empresa=request.empresa)
            estacion.delete()
            response = JsonResponse({'success': True, 'message': 'Estación de trabajo eliminada exitosamente'})
            response['Content-Type'] = 'application/json'
            return response
        except EstacionTrabajo.DoesNotExist:
            response = JsonResponse({'success': False, 'message': 'Estación de trabajo no encontrada'})
            response['Content-Type'] = 'application/json'
            return response
    
    response = JsonResponse({'success': False, 'message': 'Método no permitido'})
    response['Content-Type'] = 'application/json'
    return response


# ========== VALES ==========

@login_required
@requiere_empresa
def vale_html(request, pk):
    """Vista para imprimir vale de venta con código de barras"""
    try:
        # Intentar primero con tipo_documento='vale'
        try:
            venta = Venta.objects.get(pk=pk, empresa=request.empresa, tipo_documento='vale')
        except Venta.DoesNotExist:
            # Si no es vale, buscar cualquier tipo de documento
            venta = Venta.objects.get(pk=pk, empresa=request.empresa)
        
        detalles = VentaDetalle.objects.filter(venta=venta)
        
        context = {
            'venta': venta,
            'detalles': detalles,
            'empresa': request.empresa,
        }
        
        return render(request, 'ventas/vale_html.html', context)
    
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Documento no encontrado'})


# ========== COTIZACIONES ==========

@login_required
@requiere_empresa
@permission_required('ventas.view_cotizacion', raise_exception=True)
def cotizacion_list(request):
    """Lista de cotizaciones"""
    cotizaciones = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='cotizacion'
    ).order_by('-fecha_creacion')
    
    # Filtro por estado - por defecto excluir rechazadas
    estado = request.GET.get('estado', '')
    if estado:
        cotizaciones = cotizaciones.filter(estado_cotizacion=estado)
    else:
        # Por defecto, excluir las rechazadas
        cotizaciones = cotizaciones.exclude(estado_cotizacion='rechazada')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        cotizaciones = cotizaciones.filter(
            Q(numero_venta__icontains=search) |
            Q(cliente__nombre__icontains=search) |
            Q(cliente__rut__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(cotizaciones, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opciones de estado para el filtro
    ESTADO_CHOICES = [
        ('', 'Todos los estados'),
        ('pendiente', 'Pendiente'),
        ('enviada', 'Enviada'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
        ('vencida', 'Vencida'),
        ('convertida', 'Convertida'),
    ]
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'estado': estado,
        'estado_choices': ESTADO_CHOICES,
    }
    
    return render(request, 'ventas/cotizacion_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_cotizacion', raise_exception=True)
def cotizacion_detail(request, pk):
    """Detalle de cotización"""
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    detalles = VentaDetalle.objects.filter(venta=cotizacion).select_related('articulo')
    
    context = {
        'cotizacion': cotizacion,
        'detalles': detalles,
    }
    
    return render(request, 'ventas/cotizacion_detail.html', context)


@login_required
@requiere_empresa
def cotizacion_pdf(request, pk):
    """Generar PDF de cotización"""
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    detalles = VentaDetalle.objects.filter(venta=cotizacion).select_related('articulo')
    
    # Crear buffer para el PDF
    buffer = io.BytesIO()
    
    # Crear documento PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo personalizado para el título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    # Estilo para subtítulos
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.HexColor('#34495e')
    )
    
    # Estilo para texto normal
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Contenido del PDF
    story = []
    
    # Logo de la empresa (si existe)
    if cotizacion.empresa.logo:
        try:
            logo_path = cotizacion.empresa.logo.path
            logo = Image(logo_path, width=2*inch, height=1*inch)
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 20))
        except:
            pass
    
    # Título
    story.append(Paragraph("COTIZACIÓN", title_style))
    story.append(Spacer(1, 20))
    
    # Información de la empresa
    empresa_info = f"""
    <b>{cotizacion.empresa.razon_social}</b><br/>
    RUT: {cotizacion.empresa.rut}<br/>
    {cotizacion.empresa.direccion}<br/>
    {cotizacion.empresa.comuna}, {cotizacion.empresa.ciudad}<br/>
    Teléfono: {cotizacion.empresa.telefono}<br/>
    Email: {cotizacion.empresa.email}
    """
    story.append(Paragraph(empresa_info, normal_style))
    story.append(Spacer(1, 20))
    
    # Información de la cotización
    cotizacion_info = f"""
    <b>Número de Cotización:</b> {cotizacion.numero_venta}<br/>
    <b>Fecha:</b> {cotizacion.fecha.strftime('%d/%m/%Y')}<br/>
    <b>Válida hasta:</b> {(cotizacion.fecha + timezone.timedelta(days=30)).strftime('%d/%m/%Y')}<br/>
    <b>Vendedor:</b> {cotizacion.vendedor.nombre if cotizacion.vendedor else 'No asignado'}
    """
    story.append(Paragraph(cotizacion_info, normal_style))
    story.append(Spacer(1, 20))
    
    # Información del cliente
    if cotizacion.cliente:
        cliente_info = f"""
        <b>Cliente:</b><br/>
        {cotizacion.cliente.nombre}<br/>
        RUT: {cotizacion.cliente.rut}<br/>
        {cotizacion.cliente.direccion}<br/>
        {cotizacion.cliente.comuna}, {cotizacion.cliente.ciudad}<br/>
        Teléfono: {cotizacion.cliente.telefono}<br/>
        Email: {cotizacion.cliente.email}
        """
        story.append(Paragraph(cliente_info, normal_style))
        story.append(Spacer(1, 20))
    
    # Tabla de productos
    story.append(Paragraph("DETALLE DE PRODUCTOS", subtitle_style))
    
    # Datos de la tabla
    table_data = [['Código', 'Descripción', 'Cantidad', 'Precio Unit.', 'Total']]
    
    for detalle in detalles:
        table_data.append([
            detalle.articulo.codigo,
            detalle.articulo.descripcion,
            str(detalle.cantidad),
            f"${detalle.precio_unitario:,.0f}".replace(',', '.'),
            f"${detalle.precio_total:,.0f}".replace(',', '.')
        ])
    
    # Crear tabla
    table = Table(table_data, colWidths=[1*inch, 3*inch, 0.8*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Totales
    totales_data = [
        ['', '', '', 'Subtotal:', f"${cotizacion.subtotal:,.0f}".replace(',', '.')],
        ['', '', '', 'Descuento:', f"${cotizacion.descuento:,.0f}".replace(',', '.')],
        ['', '', '', 'Neto:', f"${cotizacion.neto:,.0f}".replace(',', '.')],
        ['', '', '', 'IVA (19%):', f"${cotizacion.iva:,.0f}".replace(',', '.')],
        ['', '', '', 'Imp. Específico:', f"${cotizacion.impuesto_especifico:,.0f}".replace(',', '.')],
        ['', '', '', 'TOTAL:', f"${cotizacion.total:,.0f}".replace(',', '.')],
    ]
    
    totales_table = Table(totales_data, colWidths=[1*inch, 3*inch, 0.8*inch, 1*inch, 1*inch])
    totales_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
    ]))
    
    story.append(totales_table)
    story.append(Spacer(1, 30))
    
    # Observaciones
    if cotizacion.observaciones:
        story.append(Paragraph("OBSERVACIONES", subtitle_style))
        story.append(Paragraph(cotizacion.observaciones, normal_style))
        story.append(Spacer(1, 20))
    
    # Términos y condiciones
    terminos = """
    <b>TÉRMINOS Y CONDICIONES:</b><br/>
    • Esta cotización tiene una validez de 30 días desde su emisión.<br/>
    • Los precios están expresados en pesos chilenos e incluyen IVA.<br/>
    • Los productos están sujetos a disponibilidad de stock.<br/>
    • El pago debe realizarse según las condiciones acordadas.<br/>
    • Cualquier modificación debe ser aprobada por escrito.
    """
    story.append(Paragraph(terminos, normal_style))
    
    # Construir PDF
    doc.build(story)
    
    # Obtener el PDF del buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Crear respuesta HTTP
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cotizacion_{cotizacion.numero_venta}.pdf"'
    
    return response


def cotizacion_html_debug(request, pk):
    """Vista HTML de cotización - VERSIÓN DEBUG SIN DECORADORES"""
    print(f"DEBUG - Buscando cotización ID: {pk}")
    print(f"DEBUG - Usuario: {request.user}")
    print(f"DEBUG - Usuario autenticado: {request.user.is_authenticated}")
    print(f"DEBUG - Es superusuario: {request.user.is_superuser}")
    
    # Verificar si tiene empresa
    if hasattr(request, 'empresa'):
        print(f"DEBUG - Empresa: {request.empresa}")
    else:
        print("DEBUG - No tiene empresa asignada")
    
    try:
        # Buscar sin filtros primero
        cotizacion = Venta.objects.get(pk=pk)
        print(f"DEBUG - Cotización encontrada: {cotizacion.numero_venta}")
        print(f"DEBUG - Empresa de la cotización: {cotizacion.empresa.nombre}")
        print(f"DEBUG - Tipo de documento: {cotizacion.tipo_documento}")
        
        # Verificar si es cotización
        if cotizacion.tipo_documento != 'cotizacion':
            print(f"DEBUG - ERROR: No es una cotización, es: {cotizacion.tipo_documento}")
            raise Http404("No es una cotización")
        
        # Verificar empresa si no es superusuario
        if not request.user.is_superuser and hasattr(request, 'empresa') and request.empresa:
            if cotizacion.empresa != request.empresa:
                print(f"DEBUG - ERROR: Empresa no coincide. Usuario: {request.empresa.nombre}, Cotización: {cotizacion.empresa.nombre}")
                raise Http404("Empresa no coincide")
        
    except Venta.DoesNotExist:
        print("DEBUG - Cotización no existe en absoluto")
        raise Http404("Cotización no encontrada")
    
    detalles = VentaDetalle.objects.filter(venta=cotizacion).select_related('articulo')
    
    context = {
        'cotizacion': cotizacion,
        'detalles': detalles,
    }
    
    return render(request, 'ventas/cotizacion_html.html', context)

@login_required
def cotizacion_html(request, pk):
    """Vista HTML de cotización"""
    print(f"DEBUG - Buscando cotización ID: {pk}")
    print(f"DEBUG - Usuario: {request.user}")
    print(f"DEBUG - Es superusuario: {request.user.is_superuser}")
    
    try:
        # Buscar la cotización
        cotizacion = Venta.objects.get(pk=pk, tipo_documento='cotizacion')
        print(f"DEBUG - Cotización encontrada: {cotizacion.numero_venta}")
        print(f"DEBUG - Empresa de la cotización: {cotizacion.empresa.nombre}")
        
        # Verificar permisos de empresa
        if not request.user.is_superuser:
            if hasattr(request, 'empresa') and request.empresa:
                if cotizacion.empresa != request.empresa:
                    print(f"DEBUG - ERROR: Empresa no coincide. Usuario: {request.empresa.nombre}, Cotización: {cotizacion.empresa.nombre}")
                    raise Http404("No tiene permisos para acceder a esta cotización")
            else:
                print("DEBUG - ERROR: Usuario no tiene empresa asignada")
                raise Http404("No tiene permisos para acceder a esta cotización")
        
    except Venta.DoesNotExist:
        print("DEBUG - Cotización no existe")
        raise Http404("Cotización no encontrada")
    
    detalles = VentaDetalle.objects.filter(venta=cotizacion).select_related('articulo')
    
    # Obtener configuración de impresora
    empresa = cotizacion.empresa
    tipo_impresora = getattr(empresa, 'impresora_cotizacion', 'laser')
    nombre_impresora = getattr(empresa, 'impresora_cotizacion_nombre', None)
    
    # Seleccionar template según configuración
    if tipo_impresora == 'termica':
        template = 'ventas/cotizacion_termica.html'
        print(f"[PRINT] Cotizacion -> Formato TERMICO 80mm")
    else:
        template = 'ventas/cotizacion_html.html'
        print(f"[PRINT] Cotizacion -> Formato LASER A4")
    
    if nombre_impresora:
        print(f"[PRINT] Impresora fisica configurada: {nombre_impresora}")
    
    context = {
        'cotizacion': cotizacion,
        'detalles': detalles,
        'empresa': empresa,
        'nombre_impresora': nombre_impresora,
    }
    
    return render(request, template, context)


@login_required
def venta_html(request, pk):
    """Vista HTML de venta (detecta automáticamente el tipo de documento)"""
    try:
        venta = Venta.objects.get(pk=pk)
        
        # Verificar permisos de empresa
        if not request.user.is_superuser:
            if hasattr(request, 'empresa') and request.empresa:
                if venta.empresa != request.empresa:
                    raise Http404("No tiene permisos para acceder a esta venta")
            else:
                raise Http404("No tiene permisos para acceder a esta venta")
    except Venta.DoesNotExist:
        raise Http404("Venta no encontrada")
    
    detalles = VentaDetalle.objects.filter(venta=venta).select_related('articulo')
    
    # Verificar si existe DTE asociado (para facturas/boletas/guías electrónicas)
    dte = None
    if venta.tipo_documento in ['factura', 'boleta', 'guia']:
        try:
            from facturacion_electronica.models import DocumentoTributarioElectronico
            
            # Buscar DTE directamente asociado a la venta
            if hasattr(venta, 'dte'):
                dte = venta.dte
                print(f"[OK] DTE encontrado directamente en venta: Tipo {dte.tipo_dte}, Folio {dte.folio}")
            else:
                # Buscar por relación en VentaProcesada
                from caja.models import VentaProcesada
                venta_procesada = VentaProcesada.objects.filter(venta_final=venta).first()
                if venta_procesada and hasattr(venta_procesada, 'dte_generado'):
                    dte = venta_procesada.dte_generado
                    print(f"[OK] DTE encontrado en VentaProcesada: Tipo {dte.tipo_dte}, Folio {dte.folio}")
                    print(f"   Timbre PDF417: {'SI' if dte.timbre_pdf417 else 'NO'}")
            
            # Si no se encontró DTE, buscar directamente en DocumentoTributarioElectronico
            if not dte:
                tipo_dte_map = {'factura': '33', 'boleta': '39', 'guia': '52'}
                tipo_dte_codigo = tipo_dte_map.get(venta.tipo_documento)
                dte = DocumentoTributarioElectronico.objects.filter(
                    venta=venta,
                    tipo_dte=tipo_dte_codigo
                ).first()
                if dte:
                    print(f"[OK] DTE encontrado por búsqueda directa: Tipo {dte.tipo_dte}, Folio {dte.folio}")
        except Exception as e:
            print(f"[WARN] Error al buscar DTE: {str(e)}")
            pass
    
    # Determinar el template según el tipo de documento Y tipo de impresora configurado
    empresa = venta.empresa
    
    # Obtener nombre de impresora física configurada (para pasarlo al template)
    nombre_impresora = None
    
    if venta.tipo_documento == 'factura':
        # Verificar si usa impresora térmica o láser
        tipo_impresora = getattr(empresa, 'impresora_factura', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_factura_nombre', None)
        
        if tipo_impresora == 'termica':
            template_name = 'ventas/factura_electronica_termica.html'
            print(f"[PRINT] Factura -> Formato TERMICO 80mm")
        else:
            template_name = 'ventas/factura_electronica_html.html'
            print(f"[PRINT] Factura -> Formato LASER A4")
    
    elif venta.tipo_documento == 'boleta':
        # Verificar si usa impresora térmica o láser
        tipo_impresora = getattr(empresa, 'impresora_boleta', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_boleta_nombre', None)
        
        if dte:  # Si tiene DTE, usar templates electrónicos
            if tipo_impresora == 'termica':
                template_name = 'ventas/boleta_electronica_termica.html'
                print(f"[PRINT] Boleta Electronica -> Formato TERMICO 80mm")
            else:
                template_name = 'ventas/factura_electronica_html.html'  # Usa el mismo que factura en A4
                print(f"[PRINT] Boleta Electronica -> Formato LASER A4")
        else:
            # Boleta sin DTE (boleta manual)
            template_name = 'ventas/boleta_html.html'
            print(f"[PRINT] Boleta Manual -> Formato estandar")
    
    elif venta.tipo_documento == 'guia':
        # Guías de despacho electrónicas
        tipo_impresora = getattr(empresa, 'impresora_guia', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_guia_nombre', None)
        
        if dte:  # Guía electrónica con DTE
            if tipo_impresora == 'termica':
                template_name = 'inventario/guia_despacho_electronica_termica.html'
                print(f"[PRINT] Guia Electronica -> Formato TERMICO 80mm")
            else:
                template_name = 'inventario/guia_despacho_electronica_html.html'
                print(f"[PRINT] Guia Electronica -> Formato LASER A4")
        else:
            # Guía manual sin DTE
            template_name = 'inventario/guia_despacho_html.html'
            print(f"[PRINT] Guia Manual -> Formato estandar")
    
    else:
        # Otros documentos (vale, cotización, NC, ND)
        # Obtener impresora configurada según tipo
        if venta.tipo_documento == 'vale':
            tipo_impresora = getattr(empresa, 'impresora_vale', 'laser')
            nombre_impresora = getattr(empresa, 'impresora_vale_nombre', None)
            
            if tipo_impresora == 'termica':
                template_name = 'ventas/vale_termica.html'
                print(f"[PRINT] Vale -> Formato TERMICO 80mm")
            else:
                template_name = 'ventas/vale_html.html'
                print(f"[PRINT] Vale -> Formato LASER A4")
                
        elif venta.tipo_documento == 'cotizacion':
            tipo_impresora = getattr(empresa, 'impresora_cotizacion', 'laser')
            nombre_impresora = getattr(empresa, 'impresora_cotizacion_nombre', None)
            
            if tipo_impresora == 'termica':
                template_name = 'ventas/cotizacion_termica.html'
                print(f"[PRINT] Cotizacion -> Formato TERMICO 80mm")
            else:
                template_name = 'ventas/cotizacion_html.html'
                print(f"[PRINT] Cotizacion -> Formato LASER A4")
        else:
            # Default para otros tipos
            template_name = 'ventas/boleta_html.html'
    
    # Log de impresora física
    if nombre_impresora:
        print(f"[PRINT] Impresora fisica configurada: {nombre_impresora}")
    
    # Obtener formas de pago múltiples (desde MovimientoCaja)
    formas_pago_list = []
    try:
        from caja.models import VentaProcesada, MovimientoCaja
        
        # Buscar VentaProcesada para esta venta
        venta_procesada = VentaProcesada.objects.filter(venta_final=venta).first()
        
        if venta_procesada and venta_procesada.apertura_caja:
            # Obtener todos los movimientos de caja asociados a esta venta
            movimientos = MovimientoCaja.objects.filter(
                apertura_caja=venta_procesada.apertura_caja,
                descripcion__icontains=venta.numero_venta
            ).select_related('forma_pago')
            
            for mov in movimientos:
                if mov.forma_pago and mov.tipo == 'ingreso':
                    formas_pago_list.append({
                        'forma_pago': mov.forma_pago.nombre,
                        'monto': abs(mov.monto)
                    })
            
            if formas_pago_list:
                print(f"[PRINT] Formas de pago encontradas: {len(formas_pago_list)}")
                for fp in formas_pago_list:
                    print(f"   - {fp['forma_pago']}: ${fp['monto']}")
    except Exception as e:
        print(f"[WARN] Error al obtener formas de pago: {str(e)}")
    
    context = {
        'venta': venta,
        'detalles': detalles,
        'empresa': empresa,
        'dte': dte,  # DTE si existe (puede ser None)
        'nombre_impresora': nombre_impresora,  # Nombre de impresora física
        'formas_pago_list': formas_pago_list,  # Lista de formas de pago múltiples
        # Alias para compatibilidad con templates específicos
        'boleta': venta if venta.tipo_documento == 'boleta' else None,
        'factura': venta if venta.tipo_documento == 'factura' else None,
        'vale': venta if venta.tipo_documento == 'vale' else None,
        'cotizacion': venta if venta.tipo_documento == 'cotizacion' else None,
    }
    
    # Para guías, pasar el DTE como 'guia' para compatibilidad con template de transferencias
    if venta.tipo_documento == 'guia' and dte:
        context['guia'] = dte
    elif venta.tipo_documento == 'guia':
        # Si no hay DTE, crear objeto temporal con datos de la venta
        class GuiaTemp:
            def __init__(self, venta):
                self.folio = venta.numero_venta
                self.monto_neto = venta.neto
                self.monto_iva = venta.iva
                self.monto_total = venta.total
                # Datos receptor
                if venta.cliente:
                    self.rut_receptor = venta.cliente.rut
                    self.razon_social_receptor = venta.cliente.nombre
                    self.giro_receptor = getattr(venta.cliente, 'giro', '')
                    self.direccion_receptor = venta.cliente.direccion or ''
                    self.comuna_receptor = venta.cliente.comuna or ''
                    self.ciudad_receptor = venta.cliente.ciudad or ''
                else:
                    self.rut_receptor = '66666666-6'
                    self.razon_social_receptor = 'Cliente Genérico'
                    self.giro_receptor = ''
                    self.direccion_receptor = ''
                    self.comuna_receptor = ''
                    self.ciudad_receptor = ''
                # Generar placeholder PDF417 en base64 para mostrar timbre
                try:
                    from facturacion_electronica.pdf417_generator import PDF417Generator
                    placeholder_bytes = PDF417Generator._generar_placeholder(280, 100)
                    import base64
                    self.datos_pdf417 = base64.b64encode(placeholder_bytes).decode('ascii')
                    self.timbre_pdf417 = None  # Usamos datos base64
                except Exception:
                    self.timbre_pdf417 = None
                    self.datos_pdf417 = None
                # Tipo traslado display helper
                self.get_tipo_traslado_display = lambda: 'Venta'
        context['guia'] = GuiaTemp(venta)
        # Pasar detalles para template compacto
        context['detalles'] = list(venta.ventadetalle_set.all())

    return render(request, template_name, context)


@login_required
def venta_imprimir_y_volver(request, pk):
    """Wrapper de impresión: abre el documento asociado a la venta, dispara impresión y retorna al POS"""
    try:
        venta = Venta.objects.get(pk=pk)
        # Verificar permisos de empresa, salvo superusuario
        if not request.user.is_superuser:
            if hasattr(request, 'empresa') and request.empresa:
                if venta.empresa != request.empresa:
                    raise Http404("No tiene permisos para acceder a esta venta")
            else:
                raise Http404("No tiene permisos para acceder a esta venta")
    except Venta.DoesNotExist:
        raise Http404("Venta no encontrada")

    # Intentar preferir la vista de DTE con timbre si existe
    dte = None
    try:
        if venta.tipo_documento in ['factura', 'boleta', 'guia']:
            if hasattr(venta, 'dte') and venta.dte:
                dte = venta.dte
            else:
                from caja.models import VentaProcesada
                venta_proc = VentaProcesada.objects.filter(venta_final=venta).first()
                if venta_proc and getattr(venta_proc, 'dte_generado', None):
                    dte = venta_proc.dte_generado
    except Exception:
        dte = None

    if dte:
        try:
            doc_url = reverse('facturacion_electronica:ver_factura_electronica', args=[dte.id])
        except Exception:
            doc_url = reverse('ventas:venta_html', args=[venta.id])
    else:
        doc_url = reverse('ventas:venta_html', args=[venta.id])

    # Agregar indicador de auto-impresión para facilitar retorno al POS si se abre en la misma pestaña
    if '?' in doc_url:
        doc_url = f"{doc_url}&auto=1"
    else:
        doc_url = f"{doc_url}?auto=1"

    return render(request, 'ventas/venta_imprimir_y_volver.html', {
        'venta': venta,
        'doc_url': doc_url,
    })

@login_required
@requiere_empresa
@permission_required('ventas.change_cotizacion', raise_exception=True)
def cotizacion_cambiar_estado(request, pk):
    """Cambiar estado de una cotización"""
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['pendiente', 'enviada', 'aceptada', 'rechazada', 'vencida']:
            cotizacion.estado_cotizacion = nuevo_estado
            cotizacion.save()
            
            messages.success(request, f'Estado de cotización actualizado a: {cotizacion.get_estado_cotizacion_display()}')
            return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)
    
    context = {
        'cotizacion': cotizacion,
        'estados': Venta.ESTADO_COTIZACION_CHOICES
    }
    
    return render(request, 'ventas/cotizacion_cambiar_estado.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_venta', raise_exception=True)
def cotizacion_convertir_venta(request, pk):
    """Convertir cotización en venta"""
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    
    if request.method == 'POST':
        tipo_venta = request.POST.get('tipo_venta')
        
        if tipo_venta in ['factura', 'boleta', 'guia']:
            # Generar número único para la nueva venta
            ultima_venta = Venta.objects.filter(empresa=cotizacion.empresa).order_by('-id').first()
            if ultima_venta and ultima_venta.numero_venta and ultima_venta.numero_venta != 'TEMP':
                try:
                    ultimo_numero = int(ultima_venta.numero_venta)
                    numero_nueva_venta = f"{ultimo_numero + 1:06d}"
                except ValueError:
                    # Si no se puede convertir, usar un número basado en la cotización
                    numero_nueva_venta = f"V{cotizacion.numero_venta}"
            else:
                numero_nueva_venta = f"V{cotizacion.numero_venta}"
            
            # Verificar que el número no exista
            while Venta.objects.filter(empresa=cotizacion.empresa, numero_venta=numero_nueva_venta).exists():
                try:
                    numero_nueva_venta = f"{int(numero_nueva_venta) + 1:06d}"
                except ValueError:
                    # Si tiene prefijo, agregar sufijo numérico
                    import random
                    numero_nueva_venta = f"{numero_nueva_venta}{random.randint(1000, 9999)}"
            
            # Crear nueva venta basada en la cotización
            nueva_venta = Venta.objects.create(
                empresa=cotizacion.empresa,
                numero_venta=numero_nueva_venta,
                cliente=cotizacion.cliente,
                vendedor=cotizacion.vendedor,
                estacion_trabajo=cotizacion.estacion_trabajo,
                tipo_documento=tipo_venta,
                subtotal=cotizacion.subtotal,
                descuento=cotizacion.descuento,
                neto=cotizacion.neto,
                iva=cotizacion.iva,
                impuesto_especifico=cotizacion.impuesto_especifico,
                total=cotizacion.total,
                estado='confirmada',
                observaciones=f"Convertida desde cotización #{cotizacion.numero_venta}",
                usuario_creacion=request.user
            )
            
            # Copiar detalles
            for detalle in cotizacion.ventadetalle_set.all():
                VentaDetalle.objects.create(
                    venta=nueva_venta,
                    articulo=detalle.articulo,
                    cantidad=detalle.cantidad,
                    precio_unitario=detalle.precio_unitario,
                    precio_total=detalle.precio_total,
                    impuesto_especifico=detalle.impuesto_especifico
                )
            
            # Actualizar estado de la cotización
            cotizacion.estado_cotizacion = 'convertida'
            cotizacion.save()
            
            messages.success(request, f'Cotización convertida en {tipo_venta} #{nueva_venta.numero_venta}')
            return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)
    
    context = {
        'cotizacion': cotizacion,
        'tipos_venta': [
            ('factura', 'Factura'),
            ('boleta', 'Boleta'),
            ('guia', 'Guía de Despacho'),
        ]
    }
    
    return render(request, 'ventas/cotizacion_convertir_venta.html', context)


# ========================================
# GESTIÓN DE TICKETS/VALES
# ========================================

@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def ticket_list(request):
    """Lista de todos los tickets/vales"""
    from datetime import datetime, timedelta
    
    # Obtener parámetros de filtro
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    estacion_id = request.GET.get('estacion')
    
    # Por defecto, mostrar tickets del día actual
    if not fecha_desde:
        fecha_desde = timezone.now().date()
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    
    if not fecha_hasta:
        fecha_hasta = fecha_desde
    else:
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Consultar tickets
    tickets = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        fecha__gte=fecha_desde,
        fecha__lte=fecha_hasta
    ).select_related('cliente', 'vendedor', 'estacion_trabajo').order_by('-fecha_creacion')
    
    # Filtrar por estación si se especifica
    if estacion_id:
        tickets = tickets.filter(estacion_trabajo_id=estacion_id)
    
    # Obtener estaciones para el filtro
    estaciones = EstacionTrabajo.objects.filter(empresa=request.empresa, activo=True)
    
    # Calcular totales
    total_tickets = tickets.count()
    total_monto = sum(ticket.total for ticket in tickets)
    
    context = {
        'tickets': tickets,
        'estaciones': estaciones,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'estacion_id': estacion_id,
        'total_tickets': total_tickets,
        'total_monto': total_monto,
    }
    
    return render(request, 'ventas/ticket_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def ticket_detail(request, pk):
    """Detalle de un ticket"""
    ticket = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='vale')
    
    detalles = VentaDetalle.objects.filter(venta=ticket).select_related('articulo')
    
    context = {
        'ticket': ticket,
        'detalles': detalles,
    }
    
    return render(request, 'ventas/ticket_detail.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def ticket_reimprimir(request, pk):
    """Reimprimir un ticket (redirige al HTML del vale)"""
    ticket = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='vale')
    return redirect('ventas:vale_html', pk=ticket.pk)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def pos_tickets_hoy(request):
    """API JSON: Retorna los tickets del día actual para el POS"""
    from django.http import JsonResponse
    
    # Tickets del día actual
    hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    tickets = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        fecha_creacion__gte=hoy_inicio,
        fecha_creacion__lte=hoy_fin
    ).select_related('cliente', 'vendedor', 'estacion_trabajo').order_by('-fecha_creacion')
    
    # Convertir a JSON
    tickets_data = []
    for ticket in tickets:
        # Determinar el tipo de documento de cierre
        tipo_doc = ticket.tipo_documento_planeado or ticket.tipo_documento
        tipo_doc_display = {
            'boleta': 'BOL',
            'factura': 'FACT',
            'guia': 'GUÍA',
            'nota_credito': 'N/C',
            'nota_debito': 'N/D',
            'cotizacion': 'COT',
            'vale': 'VALE'
        }.get(tipo_doc, tipo_doc.upper())
        
        tickets_data.append({
            'id': ticket.id,
            'numero': ticket.numero_venta,
            'fecha': ticket.fecha_creacion.strftime('%H:%M:%S'),
            'cliente': ticket.cliente.nombre if ticket.cliente else 'Sin cliente',
            'vendedor': ticket.vendedor.nombre if ticket.vendedor else 'Sin vendedor',
            'estacion': ticket.estacion_trabajo.nombre if ticket.estacion_trabajo else 'Sin estación',
            'total': float(ticket.total),
            'estado': ticket.get_estado_display(),
            'tipo_documento': tipo_doc_display,
        })
    
    return JsonResponse({
        'success': True,
        'tickets': tickets_data,
        'total_count': len(tickets_data),
    })


# ========== LIBRO DE VENTAS ==========

@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def libro_ventas(request):
    """
    Libro de Ventas - Listado completo de documentos emitidos (Ventas + DTEs)
    con filtros avanzados por tipo, fecha, cliente, vendedor y forma de pago
    """
    from facturacion_electronica.models import DocumentoTributarioElectronico
    from itertools import chain
    from operator import attrgetter
    
    # Fecha por defecto: mes actual
    hoy = timezone.now().date()
    primer_dia_mes = hoy.replace(day=1)
    
    # Obtener parámetros de filtros
    fecha_desde = request.GET.get('fecha_desde', primer_dia_mes.strftime('%Y-%m-%d'))
    fecha_hasta = request.GET.get('fecha_hasta', hoy.strftime('%Y-%m-%d'))
    tipo_documento = request.GET.get('tipo_documento', '')
    cliente_id = request.GET.get('cliente', '')
    vendedor_id = request.GET.get('vendedor', '')
    forma_pago_id = request.GET.get('forma_pago', '')
    estado = request.GET.get('estado', '')
    search = request.GET.get('search', '')
    
    # Consulta base: ventas confirmadas SIN DTE asociado
    # (para evitar duplicación: si una venta tiene DTE, se muestra solo el DTE)
    ventas = Venta.objects.filter(
        empresa=request.empresa,
        estado='confirmada',
        dte__isnull=True  # SOLO ventas sin DTE (vales, cotizaciones, etc.)
    ).select_related('cliente', 'vendedor', 'forma_pago', 'estacion_trabajo')
    
    # Consulta DTEs (Documentos Tributarios Electrónicos)
    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa
    ).select_related('caf_utilizado', 'usuario_creacion', 'venta').prefetch_related('usuario_creacion', 'notas_credito')
    
    # Aplicar filtros de fecha
    try:
        fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
        ventas = ventas.filter(fecha__gte=fecha_desde_obj, fecha__lte=fecha_hasta_obj)
        dtes = dtes.filter(fecha_emision__gte=fecha_desde_obj, fecha_emision__lte=fecha_hasta_obj)
    except ValueError:
        pass
    
    # Filtrar por tipo de documento
    if tipo_documento:
        if tipo_documento in ['33', '34', '39', '41', '52', '56', '61']:
            # Es un DTE
            dtes = dtes.filter(tipo_dte=tipo_documento)
            ventas = ventas.none()
        else:
            # Es una venta del POS
            ventas = ventas.filter(tipo_documento=tipo_documento)
            dtes = dtes.none()
    
    # Filtros adicionales para ventas y DTEs
    if ventas.exists():
        if cliente_id:
            ventas = ventas.filter(cliente_id=cliente_id)
        
        if vendedor_id:
            ventas = ventas.filter(vendedor_id=vendedor_id)
        
        if forma_pago_id:
            ventas = ventas.filter(forma_pago_id=forma_pago_id)
        
        if estado:
            ventas = ventas.filter(estado=estado)
    
    # Filtros para DTEs (usar venta asociada si existe)
    if dtes.exists():
        if cliente_id:
            dtes = dtes.filter(
                Q(venta__cliente_id=cliente_id) |
                Q(rut_receptor__icontains=cliente_id)
            )
        
        if vendedor_id:
            dtes = dtes.filter(venta__vendedor_id=vendedor_id)
        
        if forma_pago_id:
            dtes = dtes.filter(venta__forma_pago_id=forma_pago_id)
    
    # Búsqueda en ambos tipos
    if search:
        if ventas.exists():
            ventas = ventas.filter(
                Q(numero_venta__icontains=search) |
                Q(cliente__nombre__icontains=search) |
                Q(cliente__rut__icontains=search) |
                Q(observaciones__icontains=search)
            )
        if dtes.exists():
            dtes = dtes.filter(
                Q(folio__icontains=search) |
                Q(razon_social_receptor__icontains=search) |
                Q(rut_receptor__icontains=search) |
                Q(glosa_sii__icontains=search)
            )
    
    # Combinar ventas y DTEs
    ventas_list = list(ventas)
    dtes_list = list(dtes)
    
    for venta in ventas_list:
        venta.fecha_documento = venta.fecha
        venta.es_dte = False
    
    for dte in dtes_list:
        dte.fecha_documento = dte.fecha_emision
        dte.es_dte = True
        # Marcar y ajustar montos para Notas de Crédito (tipo 61) como negativos
        dte.es_nota_credito = (getattr(dte, 'tipo_dte', '') == '61')
        if dte.es_nota_credito:
            dte.monto_neto = -(dte.monto_neto or 0)
            dte.monto_iva = -(dte.monto_iva or 0)
            dte.monto_total = -(dte.monto_total or 0)
            # Exponer ID de Nota de Crédito asociada (si existe) para el template
            try:
                nc = dte.notas_credito.all()[0] if hasattr(dte, 'notas_credito') and dte.notas_credito.all() else None
                dte.notacredito_id = nc.id if nc else None
            except Exception:
                dte.notacredito_id = None
    
    documentos = sorted(
        chain(ventas_list, dtes_list),
        key=attrgetter('fecha_documento'),
        reverse=True
    )
    
    # Estadísticas del período (solo si hay datos)
    if ventas.exists():
        stats_ventas = ventas.aggregate(
            total_neto=Sum('neto'),
            total_iva=Sum('iva'),
            total_general=Sum('total')
        )
    else:
        stats_ventas = {'total_neto': 0, 'total_iva': 0, 'total_general': 0}
    
    # Calcular stats DTE desde la lista ajustada (NC negativas)
    if dtes_list:
        from decimal import Decimal as _Dec
        stats_dtes = {
            'total_neto': sum((d.monto_neto or 0) for d in dtes_list) or _Dec('0'),
            'total_iva': sum((d.monto_iva or 0) for d in dtes_list) or _Dec('0'),
            'total_general': sum((d.monto_total or 0) for d in dtes_list) or _Dec('0'),
        }
    else:
        stats_dtes = {'total_neto': 0, 'total_iva': 0, 'total_general': 0}
    
    estadisticas = {
        'total_documentos': len(documentos),
        'total_neto': (stats_ventas['total_neto'] or 0) + (stats_dtes['total_neto'] or 0),
        'total_iva': (stats_ventas['total_iva'] or 0) + (stats_dtes['total_iva'] or 0),
        'total_general': (stats_ventas['total_general'] or 0) + (stats_dtes['total_general'] or 0),
    }
    
    # Estadísticas por tipo
    stats_ventas_tipo = ventas.values('tipo_documento').annotate(
        cantidad=Count('id'),
        total=Sum('total')
    )
    
    # Construir stats por tipo DTE desde la lista (NC como negativas)
    from collections import defaultdict
    from decimal import Decimal as _Dec
    dte_stats_map = defaultdict(lambda: {'cantidad': 0, 'total': _Dec('0')})
    for d in dtes_list:
        t = getattr(d, 'tipo_dte', None)
        if not t:
            continue
        dte_stats_map[t]['cantidad'] += 1
        dte_stats_map[t]['total'] += (d.monto_total or _Dec('0'))
    stats_dtes_tipo = [
        {'tipo_documento': k, 'cantidad': v['cantidad'], 'total': v['total']}
        for k, v in dte_stats_map.items()
    ]

    stats_por_tipo = list(stats_ventas_tipo) + stats_dtes_tipo
    
    # Paginación
    paginator = Paginator(documentos, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opciones para filtros
    clientes = request.empresa.cliente_set.filter(estado='activo').order_by('nombre')
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    # Tipos de documento: Solo DTEs con códigos SII + tipos POS sin equivalente DTE
    tipos_documento_dict = {
        # DTEs (Documentos Tributarios Electrónicos)
        '33': 'Factura Electrónica (33)',
        '34': 'Factura Exenta Electrónica (34)',
        '39': 'Boleta Electrónica (39)',
        '41': 'Boleta Exenta Electrónica (41)',
        '52': 'Guía de Despacho Electrónica (52)',
        '56': 'Nota de Débito Electrónica (56)',
        '61': 'Nota de Crédito Electrónica (61)',
        # Tipos POS sin equivalente DTE
        'cotizacion': 'Cotización',
        'vale': 'Vale',
    }
    
    context = {
        'page_obj': page_obj,
        'estadisticas': estadisticas,
        'stats_por_tipo': stats_por_tipo,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'tipo_documento': tipo_documento,
        'cliente_id': cliente_id,
        'vendedor_id': vendedor_id,
        'forma_pago_id': forma_pago_id,
        'estado': estado,
        'search': search,
        'clientes': clientes,
        'vendedores': vendedores,
        'formas_pago': formas_pago,
        'tipos_documento': tipos_documento_dict,
    }
    
    return render(request, 'ventas/libro_ventas.html', context)


# ============================================
# CRUD PRECIOS ESPECIALES CLIENTES
# ============================================

@login_required
@requiere_empresa
@permission_required('ventas.view_precioclientearticulo', raise_exception=True)
def precio_cliente_list(request):
    """Lista de precios especiales por cliente"""
    from .models import PrecioClienteArticulo
    from clientes.models import Cliente
    from articulos.models import Articulo
    from datetime import date
    
    # Base queryset
    precios = PrecioClienteArticulo.objects.filter(empresa=request.empresa).select_related('cliente', 'articulo').order_by('-fecha_creacion')
    
    # Filtros GET
    q = request.GET.get('q', '').strip()
    cliente_id = request.GET.get('cliente', '').strip()
    articulo_id = request.GET.get('articulo', '').strip()
    estado = request.GET.get('estado', '').strip()  # 'activo' | 'inactivo'
    vigencia = request.GET.get('vigencia', '').strip()  # 'vigente' | 'futura' | 'vencida'
    
    if q:
        precios = precios.filter(
            Q(cliente__nombre__icontains=q) |
            Q(articulo__nombre__icontains=q) |
            Q(articulo__codigo__icontains=q)
        )
    if cliente_id:
        precios = precios.filter(cliente_id=cliente_id)
    if articulo_id:
        precios = precios.filter(articulo_id=articulo_id)
    if estado in ['activo', 'inactivo']:
        precios = precios.filter(activo=(estado == 'activo'))
    if vigencia:
        hoy = date.today()
        if vigencia == 'vigente':
            precios = precios.filter(
                Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=hoy),
                Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy)
            )
        elif vigencia == 'futura':
            precios = precios.filter(fecha_inicio__gt=hoy)
        elif vigencia == 'vencida':
            precios = precios.filter(fecha_fin__lt=hoy)
    
    # Paginación
    paginator = Paginator(precios, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para filtros (listas)
    clientes_list = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')
    articulos_list = Articulo.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')[:500]
    
    context = {
        'page_obj': page_obj,
        'precios': page_obj.object_list,
        'q': q,
        'cliente_id': cliente_id,
        'articulo_id': articulo_id,
        'estado': estado,
        'vigencia': vigencia,
        'clientes_list': clientes_list,
        'articulos_list': articulos_list,
    }
    
    return render(request, 'ventas/precio_cliente_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_precioclientearticulo', raise_exception=True)
def precio_cliente_create(request):
    """Crear precio especial"""
    from .models import PrecioClienteArticulo
    from .forms import PrecioClienteArticuloForm
    from clientes.models import Cliente
    from articulos.models import Articulo
    from django.http import JsonResponse
    
    if request.method == 'POST':
        form = PrecioClienteArticuloForm(request.POST)
        if form.is_valid():
            precio = form.save(commit=False)
            precio.empresa = request.empresa
            precio.creado_por = request.user
            precio.save()
            return JsonResponse({'success': True, 'message': 'Precio especial creado exitosamente'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    
    # GET: Retornar formulario
    form = PrecioClienteArticuloForm()
    form.fields['cliente'].queryset = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')
    
    # Preparar artículos con sus precios FINALES (con IVA e impuestos) para JavaScript
    articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    articulos_precios = {str(a.id): int(round(float(a.precio_final))) for a in articulos}
    
    form.fields['articulo'].queryset = articulos
    
    return render(request, 'ventas/precio_cliente_form.html', {
        'form': form,
        'articulos_precios': articulos_precios
    })


@login_required
@requiere_empresa
@permission_required('ventas.change_precioclientearticulo', raise_exception=True)
def precio_cliente_edit(request, pk):
    """Editar precio especial"""
    from .models import PrecioClienteArticulo
    from .forms import PrecioClienteArticuloForm
    from clientes.models import Cliente
    from articulos.models import Articulo
    from django.http import JsonResponse
    
    try:
        precio = PrecioClienteArticulo.objects.get(pk=pk, empresa=request.empresa)
        
        if request.method == 'POST':
            form = PrecioClienteArticuloForm(request.POST, instance=precio)
            if form.is_valid():
                form.save()
                return JsonResponse({'success': True, 'message': 'Precio especial actualizado exitosamente'})
            else:
                return JsonResponse({'success': False, 'errors': form.errors})
        
        # GET: Retornar formulario
        form = PrecioClienteArticuloForm(instance=precio)
        form.fields['cliente'].queryset = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')
        
        # Preparar artículos con sus precios FINALES (con IVA e impuestos) para JavaScript
        articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
        articulos_precios = {str(a.id): int(round(float(a.precio_final))) for a in articulos}
        
        form.fields['articulo'].queryset = articulos
        
        return render(request, 'ventas/precio_cliente_form.html', {
            'form': form, 
            'precio': precio,
            'articulos_precios': articulos_precios
        })
    
    except PrecioClienteArticulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Precio especial no encontrado'})


@login_required
@requiere_empresa
@permission_required('ventas.delete_precioclientearticulo', raise_exception=True)
def precio_cliente_delete(request, pk):
    """Eliminar precio especial"""
    from .models import PrecioClienteArticulo
    from django.http import JsonResponse
    
    try:
        precio = PrecioClienteArticulo.objects.get(pk=pk, empresa=request.empresa)
        precio.delete()
        return JsonResponse({'success': True, 'message': 'Precio especial eliminado exitosamente'})
    except PrecioClienteArticulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Precio especial no encontrado'})


@login_required
@requiere_empresa
def precio_cliente_articulo_api(request, cliente_id, articulo_id):
    """API para obtener precio especial de un artículo para un cliente"""
    from .models import PrecioClienteArticulo
    from django.http import JsonResponse
    from datetime import date
    
    try:
        # Buscar precio especial activo y vigente
        precio_especial = PrecioClienteArticulo.objects.filter(
            empresa=request.empresa,
            cliente_id=cliente_id,
            articulo_id=articulo_id,
            activo=True,
            fecha_inicio__lte=date.today(),
            fecha_fin__gte=date.today()
        ).first()
        
        if precio_especial:
            return JsonResponse({
                'success': True,
                'precio_especial': float(precio_especial.precio_especial)
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No hay precio especial para este cliente'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@requiere_empresa
def articulo_precio_api(request, pk):
    """API para obtener el precio de un artículo"""
    from articulos.models import Articulo
    from django.http import JsonResponse
    
    try:
        articulo = Articulo.objects.get(pk=pk, empresa=request.empresa)
        return JsonResponse({
            'success': True,
            'precio_venta': float(articulo.precio_venta),
            'nombre': articulo.nombre,
            'codigo': articulo.codigo
        })
    except Articulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Artículo no encontrado'})
