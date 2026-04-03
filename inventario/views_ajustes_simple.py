from utilidades.utils import clean_id
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
import json

from core.decorators import requiere_empresa
from bodegas.models import Bodega
from articulos.models import Articulo
from .models import Stock, Inventario
from .models_ajustes import AjusteStock, DetalleAjuste


@login_required
@requiere_empresa
def ajustes_list_simple(request):
    """Lista agrupada de ajustes de stock usando el modelo AjusteStock (Maestro)"""
    ajustes = AjusteStock.objects.filter(empresa=request.empresa).select_related(
        'bodega', 'creado_por'
    ).prefetch_related('detalles')
    
    # Aplicar filtros
    bodega_id = request.GET.get('bodega')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    tipo = request.GET.get('tipo')
    
    if bodega_id:
        ajustes = ajustes.filter(bodega_id=bodega_id)
        
    if fecha_desde:
        ajustes = ajustes.filter(fecha_ajuste__date__gte=fecha_desde)
        
    if fecha_hasta:
        ajustes = ajustes.filter(fecha_ajuste__date__lte=fecha_hasta)
        
    if tipo:
        ajustes = ajustes.filter(tipo_ajuste=tipo)
            
    ajustes = ajustes.order_by('-fecha_ajuste', '-fecha_creacion')
    
    # Estadísticas
    total_ajustes = ajustes.count()
    ajustes_entrada = ajustes.filter(tipo_ajuste='entrada').count()
    ajustes_salida = ajustes.filter(tipo_ajuste='salida').count()
    
    # Bodegas para filtro
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    
    context = {
        'ajustes': ajustes,
        'bodegas': bodegas,
        'total_ajustes': total_ajustes,
        'ajustes_entrada': ajustes_entrada,
        'ajustes_salida': ajustes_salida,
        'titulo': 'Gestión de Ajustes de Inventario'
    }
    
    return render(request, 'inventario/ajustes_list_simple.html', context)


@login_required
@requiere_empresa
@transaction.atomic
def ajuste_create_simple(request):
    """Crear nuevo ajuste de stock masivo (Carga de varios artículos)"""
    if request.method == 'POST':
        tipo_ajuste = request.POST.get('tipo_ajuste', '').lower() # 'entrada' o 'salida'
        fecha_ajuste_str = request.POST.get('fecha_ajuste')
        bodega_id = request.POST.get('bodega')
        descripcion = request.POST.get('descripcion')
        
        # Obtener detalles desde JSON
        detalles_data = request.POST.get('detalles_data', '[]')
        detalles_list = json.loads(detalles_data)
        
        if not detalles_list:
            return JsonResponse({'success': False, 'message': 'Debe agregar al menos un artículo.'}, status=400)
        
        try:
            bodega = get_object_or_404(Bodega, id=bodega_id, empresa=request.empresa)
            
            # 1. Generar Número de Folio
            # Intentar obtener correlativo configurado
            try:
                config = request.empresa.configuracion
                numero_folio = config.generar_numero_ajuste()
            except:
                ultimo = AjusteStock.objects.filter(empresa=request.empresa).order_by('-id').first()
                secuencia = (ultimo.id + 1) if ultimo else 1
                numero_folio = f"AJU-{secuencia:05d}"

            # 2. Procesar fecha
            if fecha_ajuste_str:
                fecha_ajuste = timezone.make_aware(datetime.strptime(fecha_ajuste_str, '%Y-%m-%d'))
            else:
                fecha_ajuste = timezone.now()

            # 3. Crear Cabecera (Maestro)
            ajuste_master = AjusteStock.objects.create(
                empresa=request.empresa,
                numero_folio=numero_folio,
                tipo_ajuste=tipo_ajuste,
                fecha_ajuste=fecha_ajuste,
                bodega=bodega,
                descripcion=descripcion,
                creado_por=request.user
            )
            
            # 4. Procesar Detalles y Movimientos
            for items in detalles_list:
                articulo = get_object_or_404(Articulo, id=items['articulo_id'], empresa=request.empresa)
                cantidad = Decimal(str(items['cantidad']))
                comentario = items.get('comentario', '')
                
                # Crear Movimiento de Inventario vinculado
                # Si es salida, la cantidad en Inventario debe ser negativa para el stock?
                # Revisando actualizar_stock: si es 'salida' usa bodega_origen y resta cantidad.
                mov = Inventario.objects.create(
                    empresa=request.empresa,
                    bodega_destino=bodega if tipo_ajuste == 'entrada' else None,
                    bodega_origen=bodega if tipo_ajuste == 'salida' else None,
                    articulo=articulo,
                    tipo_movimiento='ajuste',
                    cantidad=cantidad,
                    descripcion=f"Ajuste {numero_folio}: {descripcion}",
                    fecha_movimiento=fecha_ajuste,
                    creado_por=request.user,
                    numero_folio=numero_folio,
                    estado='confirmado'
                )

                # Crear Detalle del Ajuste vinculado
                DetalleAjuste.objects.create(
                    ajuste=ajuste_master,
                    articulo=articulo,
                    cantidad=cantidad,
                    comentario=comentario,
                    movimiento=mov
                )

                # 5. Actualizar el Stock actual
                from .views import actualizar_stock
                actualizar_stock(mov)
            
            return JsonResponse({
                'success': True,
                'ajuste_id': ajuste_master.id,
                'message': f'Ajuste {numero_folio} procesado con éxito ({len(detalles_list)} artículos).'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

    # Si es GET, renderizar el modal de creación
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    return render(request, 'inventario/ajuste_create_modal.html', {'bodegas': bodegas})


@login_required
@requiere_empresa
@transaction.atomic
def ajuste_edit_simple(request, pk):
    """Editar un ajuste de stock maestro"""
    ajuste = get_object_or_404(AjusteStock, id=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        tipo_ajuste = request.POST.get('tipo_ajuste', '').lower()
        fecha_ajuste_str = request.POST.get('fecha_ajuste')
        descripcion = request.POST.get('descripcion')
        
        # Obtener detalles desde JSON
        detalles_data = request.POST.get('detalles_data', '[]')
        detalles_list = json.loads(detalles_data)
        
        try:
            # 1. Actualizar Cabecera
            ajuste.tipo_ajuste = tipo_ajuste
            if fecha_ajuste_str:
                ajuste.fecha_ajuste = timezone.make_aware(datetime.strptime(fecha_ajuste_str, '%Y-%m-%d'))
            ajuste.descripcion = descripcion
            ajuste.save()
            
            # 2. Revertir y Eliminar Detalles/Movimientos anteriores
            from .views import revertir_stock, actualizar_stock
            for detalle in ajuste.detalles.all():
                if detalle.movimiento:
                    revertir_stock(detalle.movimiento)
                    detalle.movimiento.delete()
                detalle.delete()
            
            # 3. Crear Nuevos Detalles y Movimientos
            for items in detalles_list:
                articulo = get_object_or_404(Articulo, id=items['articulo_id'], empresa=request.empresa)
                cantidad = Decimal(str(items['cantidad']))
                comentario = items.get('comentario', '')
                
                mov = Inventario.objects.create(
                    empresa=request.empresa,
                    bodega_destino=ajuste.bodega if tipo_ajuste == 'entrada' else None,
                    bodega_origen=ajuste.bodega if tipo_ajuste == 'salida' else None,
                    articulo=articulo,
                    tipo_movimiento='ajuste',
                    cantidad=cantidad,
                    descripcion=f"Ajuste {ajuste.numero_folio} (Edited): {descripcion}",
                    fecha_movimiento=ajuste.fecha_ajuste,
                    creado_por=request.user,
                    numero_folio=ajuste.numero_folio,
                    estado='confirmado'
                )

                DetalleAjuste.objects.create(
                    ajuste=ajuste,
                    articulo=articulo,
                    cantidad=cantidad,
                    comentario=comentario,
                    movimiento=mov
                )

                actualizar_stock(mov)
            
            return JsonResponse({
                'success': True,
                'message': f'Ajuste {ajuste.numero_folio} actualizado con éxito.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

    # Si es GET, renderizar el modal de edición
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    
    # Preparar datos para que el template (si es que soporta mas de 1) pueda iterar
    # El template actual es limitado, pero pasamos lo necesario
    primer_detalle = ajuste.detalles.first()
    cantidad_absoluta = primer_detalle.cantidad if primer_detalle else 0
    
    context = {
        'ajuste': ajuste,
        'bodegas': bodegas,
        'primer_detalle': primer_detalle,
        'cantidad_absoluta': cantidad_absoluta,
        'cantidad_absoluta_str': str(cantidad_absoluta).replace(',', '.'),
        'titulo': f'Editar Ajuste {ajuste.numero_folio}'
    }
    return render(request, 'inventario/ajuste_edit_modal.html', context)


@login_required
@requiere_empresa
def api_articulos_ajuste_simple(request):
    """API para obtener artículos para ajustes con stock actual"""
    try:
        bodega_id_str = request.GET.get('bodega_id', '')
        q = request.GET.get('q', '').strip()
        
        if not bodega_id_str:
             return JsonResponse({'error': 'Bodega no especificada'}, status=400)
             
        bodega = get_object_or_404(Bodega, id=bodega_id_str, empresa=request.empresa)

        articulos_qs = Articulo.objects.filter(empresa=request.empresa, activo=True)
        if q:
            articulos_qs = articulos_qs.filter(
                Q(codigo__icontains=q) | Q(nombre__icontains=q) | Q(codigo_barras__icontains=q)
            ).distinct()
            
        articulos_qs = articulos_qs.order_by('nombre')[:50]
            
        articulos_data = []
        for articulo in articulos_qs:
            stock_qs = Stock.objects.filter(empresa=request.empresa, bodega=bodega, articulo=articulo).first()
            articulos_data.append({
                'id': articulo.id,
                'codigo': articulo.codigo,
                'nombre': articulo.nombre,
                'unidad_medida': str(articulo.unidad_medida),
                'stock_actual': float(stock_qs.cantidad) if stock_qs else 0,
                'precio_promedio': float(stock_qs.precio_promedio or 0) if stock_qs else 0
            })
            
        return JsonResponse({'articulos': articulos_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@requiere_empresa
def ajuste_imprimir(request, pk):
    """Genera la vista imprimible del ajuste de inventario."""
    ajuste = get_object_or_404(AjusteStock, id=pk, empresa=request.empresa)
    
    detalles = ajuste.detalles.select_related('articulo', 'movimiento').all()
    detalles_con_subtotal = []
    
    neto = Decimal('0.00')
    
    # Calcular subtotals
    for d in detalles:
        # El costo lo sacamos directamente del precio_promedio original del artículo, o del propio inventario.
        # `movimiento.precio_unitario` podría estar a 0 si no se calculó ahí, pero intentamos extraer info real.
        # Si el input front-end lo pasó se supone que se actualizó, pero Ajuste no guarda precio. Así que inferimos del mov
        # o en dado caso del precio del articulo. Al guardar el ajuste modificamos Stock, pero el costo base lo traíamos.
        # El Ajuste no graba precio histórico todavía, tomaremos el costo actual del stock o movimiento
        try:
            costo_unitario = Decimal(str(d.articulo.precio_costo or 0))
        except:
            costo_unitario = Decimal('0')
            
        if d.movimiento and d.movimiento.precio_unitario:
            try:
                precio_mov = Decimal(str(d.movimiento.precio_unitario))
                if precio_mov > 0:
                    costo_unitario = precio_mov
            except:
                pass
                
        try:
            cantidad_dec = Decimal(str(d.cantidad or 0))
        except:
            cantidad_dec = Decimal('0')
            
        subtotal = cantidad_dec * costo_unitario
        neto += subtotal
        detalles_con_subtotal.append({
            'articulo': d.articulo,
            'cantidad': d.cantidad,
            'costo_unitario': costo_unitario,
            'subtotal': subtotal,
            'comentario': d.comentario,
            'unidad': d.articulo.unidad_medida
        })
        
    iva = neto * Decimal('0.19') # IVA chile 19%
    total = neto + iva
    
    context = {
        'ajuste': ajuste,
        'detalles': detalles_con_subtotal,
        'neto': neto,
        'iva': iva,
        'total': total,
        'empresa': request.empresa,
        'titulo': f'Comprobante Ajuste {ajuste.numero_folio}'
    }
    
    return render(request, 'inventario/ajuste_imprimir.html', context)


@login_required
@requiere_empresa
def ajuste_detail_simple(request, pk):
    """Ver detalles de un ajuste maestro"""
    ajuste = get_object_or_404(AjusteStock, id=pk, empresa=request.empresa)
    detalles = ajuste.detalles.all().select_related('articulo')
    
    context = {
        'ajuste': ajuste,
        'detalles': detalles,
        'titulo': f'Detalle del Ajuste {ajuste.numero_folio}'
    }
    return render(request, 'inventario/ajuste_detail_modal.html', context)


@login_required
@requiere_empresa
def ajuste_delete_simple(request, pk):
    """Eliminar un ajuste y revertir stock"""
    ajuste = get_object_or_404(AjusteStock, id=pk, empresa=request.empresa)
    
    with transaction.atomic():
        from .views import revertir_stock
        for detalle in ajuste.detalles.all():
            if detalle.movimiento:
                revertir_stock(detalle.movimiento)
                detalle.movimiento.delete()
        
        ajuste.delete()
    
    messages.success(request, 'Ajuste eliminado y stock revertido exitosamente.')
    return redirect('inventario:ajustes_list')


# Import Q for the API search
from django.db.models import Q
