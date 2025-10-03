from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from decimal import Decimal
from .models import Articulo, CategoriaArticulo, UnidadMedida, StockArticulo, ImpuestoEspecifico
from inventario.models import Stock
from .forms import ArticuloForm, CategoriaArticuloForm, UnidadMedidaForm, ImpuestoEspecificoForm
from empresas.decorators import requiere_empresa


@requiere_empresa
@login_required
def articulo_list(request):
    """Lista de artículos"""
    # Filtrar por empresa activa (todos los usuarios, incluyendo superusuarios)
    articulos = Articulo.objects.filter(empresa=request.empresa).order_by('-fecha_creacion')
    
    # Filtros
    search = request.GET.get('search', '')
    categoria_id = request.GET.get('categoria', '')
    activo = request.GET.get('activo', '')
    
    if search:
        articulos = articulos.filter(
            Q(codigo__icontains=search) |
            Q(nombre__icontains=search) |
            Q(descripcion__icontains=search)
        )
    
    if categoria_id:
        articulos = articulos.filter(categoria_id=categoria_id)
    
    if activo != '':
        articulos = articulos.filter(activo=activo == 'true')
    
    # Paginación
    paginator = Paginator(articulos, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Agregar stock total a cada artículo
    for articulo in page_obj:
        if articulo.control_stock:
            stock_total = Stock.objects.filter(articulo=articulo).aggregate(
                total=Sum('cantidad')
            )['total']
            articulo.stock_total = stock_total or 0
        else:
            articulo.stock_total = None
    
    # Estadísticas reales (antes de aplicar filtros)
    articulos_totales = Articulo.objects.filter(empresa=request.empresa)
    total_articulos = articulos_totales.count()
    articulos_activos = articulos_totales.filter(activo=True).count()
    articulos_inactivos = articulos_totales.filter(activo=False).count()
    
    # Contar artículos con control de stock
    articulos_con_stock = articulos_totales.filter(control_stock=True).count()
    
    # Categorías para el filtro
    categorias = CategoriaArticulo.objects.filter(empresa=request.empresa, activa=True)
    
    context = {
        'page_obj': page_obj,
        'categorias': categorias,
        'search': search,
        'categoria_id': categoria_id,
        'activo': activo,
        'total_articulos': total_articulos,
        'articulos_activos': articulos_activos,
        'articulos_inactivos': articulos_inactivos,
        'articulos_con_stock': articulos_con_stock,
    }
    
    return render(request, 'articulos/articulo_list.html', context)


@requiere_empresa
@login_required
def articulo_detail(request, pk):
    """Detalle de un artículo"""
    # Para superusuarios, permitir ver cualquier artículo
    if request.user.is_superuser:
        articulo = get_object_or_404(Articulo, pk=pk)
    else:
        articulo = get_object_or_404(Articulo, pk=pk, empresa=request.empresa)
    
    # Stocks por sucursal
    stocks = StockArticulo.objects.filter(articulo=articulo)
    
    context = {
        'articulo': articulo,
        'stocks': stocks,
    }
    
    return render(request, 'articulos/articulo_detail.html', context)


@requiere_empresa
@login_required
def articulo_create(request):
    """Crear nuevo artículo"""
    if request.method == 'POST':
        form = ArticuloForm(request.POST, initial={'empresa': request.empresa})
        if form.is_valid():
            articulo = form.save(commit=False)
            articulo.empresa = request.empresa
            articulo.save()
            messages.success(request, f'Artículo "{articulo.nombre}" creado exitosamente.')
            return redirect('articulos:articulo_list')
        else:
            messages.error(request, 'Error en el formulario. Revise los datos.')
            # Debug: mostrar errores específicos
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ArticuloForm(initial={'empresa': request.empresa})
    
    context = {
        'form': form,
        'title': 'Crear Artículo',
        'submit_text': 'Crear Artículo',
    }
    
    return render(request, 'articulos/articulo_form.html', context)


@requiere_empresa
@login_required
def articulo_update(request, pk):
    """Editar artículo"""
    # Para superusuarios, permitir editar cualquier artículo
    if request.user.is_superuser:
        articulo = get_object_or_404(Articulo, pk=pk)
    else:
        articulo = get_object_or_404(Articulo, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = ArticuloForm(request.POST, instance=articulo, initial={'empresa': request.empresa})
        if form.is_valid():
            articulo = form.save(commit=False)
            articulo.save()
            messages.success(request, f'Artículo "{articulo.nombre}" actualizado exitosamente.')
            return redirect('articulos:articulo_list')
        else:
            messages.error(request, 'Error en el formulario. Revise los datos.')
            # Debug: mostrar errores específicos
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ArticuloForm(instance=articulo, initial={'empresa': request.empresa})
    
    context = {
        'form': form,
        'articulo': articulo,
        'title': 'Editar Artículo',
        'submit_text': 'Actualizar Artículo',
    }
    
    return render(request, 'articulos/articulo_form.html', context)


@requiere_empresa
@login_required
def articulo_delete(request, pk):
    """Eliminar artículo"""
    # Para superusuarios, permitir eliminar cualquier artículo
    if request.user.is_superuser:
        articulo = get_object_or_404(Articulo, pk=pk)
    else:
        articulo = get_object_or_404(Articulo, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nombre = articulo.nombre
        articulo.delete()
        messages.success(request, f'Artículo "{nombre}" eliminado exitosamente.')
        return redirect('articulos:articulo_list')
    
    context = {
        'articulo': articulo,
    }
    
    return render(request, 'articulos/articulo_confirm_delete.html', context)


# Vistas para Categorías
@requiere_empresa
@login_required
def categoria_list(request):
    """Lista de categorías"""
    # Filtrar por empresa activa (todos los usuarios, incluyendo superusuarios)
    categorias = CategoriaArticulo.objects.filter(empresa=request.empresa).order_by('nombre')
    
    # Calcular estadísticas
    total_categorias = categorias.count()
    categorias_activas = categorias.filter(activa=True).count()
    categorias_con_iva = categorias.filter(exenta_iva=False).count()
    categorias_exentas = categorias.filter(exenta_iva=True).count()
    
    # Obtener impuestos específicos para el modal
    impuestos_especificos = ImpuestoEspecifico.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    
    context = {
        'categorias': categorias,
        'total_categorias': total_categorias,
        'categorias_activas': categorias_activas,
        'categorias_con_iva': categorias_con_iva,
        'categorias_exentas': categorias_exentas,
        'impuestos_especificos': impuestos_especificos,
    }
    
    return render(request, 'articulos/categoria_list.html', context)


@requiere_empresa
@login_required
def categoria_create(request):
    """Crear nueva categoría"""
    if request.method == 'POST':
        form = CategoriaArticuloForm(request.POST, initial={'empresa': request.empresa})
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.empresa = request.empresa
            categoria.save()
            messages.success(request, f'Categoría "{categoria.nombre}" creada exitosamente.')
            return redirect('articulos:categoria_list')
    else:
        form = CategoriaArticuloForm(initial={'empresa': request.empresa})
    
    context = {
        'form': form,
        'title': 'Crear Categoría',
        'submit_text': 'Crear Categoría',
    }
    
    return render(request, 'articulos/categoria_form.html', context)


@requiere_empresa
@login_required
def categoria_update(request, pk):
    """Editar categoría"""
    # Para superusuarios, no filtrar por empresa
    if request.user.is_superuser:
        categoria = get_object_or_404(CategoriaArticulo, pk=pk)
    else:
        categoria = get_object_or_404(CategoriaArticulo, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = CategoriaArticuloForm(request.POST, instance=categoria, initial={'empresa': request.empresa})
        if form.is_valid():
            form.save()
            messages.success(request, f'Categoría "{categoria.nombre}" actualizada exitosamente.')
            return redirect('articulos:categoria_list')
    else:
        form = CategoriaArticuloForm(instance=categoria, initial={'empresa': request.empresa})
    
    context = {
        'form': form,
        'categoria': categoria,
        'title': 'Editar Categoría',
        'submit_text': 'Actualizar Categoría',
    }
    
    return render(request, 'articulos/categoria_form.html', context)


@requiere_empresa
@login_required
def categoria_delete(request, pk):
    """Eliminar categoría"""
    # Para superusuarios, no filtrar por empresa
    if request.user.is_superuser:
        categoria = get_object_or_404(CategoriaArticulo, pk=pk)
    else:
        categoria = get_object_or_404(CategoriaArticulo, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nombre = categoria.nombre
        categoria.delete()
        messages.success(request, f'Categoría "{nombre}" eliminada exitosamente.')
        return redirect('articulos:categoria_list')
    
    context = {
        'categoria': categoria,
        'title': 'Eliminar Categoría',
    }
    
    return render(request, 'articulos/categoria_confirm_delete.html', context)


# Vistas para Unidades de Medida
@requiere_empresa
@login_required
def unidad_medida_list(request):
    """Lista de unidades de medida"""
    # Filtrar por empresa activa (todos los usuarios, incluyendo superusuarios)
    unidades = UnidadMedida.objects.filter(empresa=request.empresa).order_by('nombre')
    
    context = {
        'unidades': unidades,
    }
    
    return render(request, 'articulos/unidad_list.html', context)


@requiere_empresa
@login_required
def unidad_medida_create(request):
    """Crear nueva unidad de medida"""
    if request.method == 'POST':
        form = UnidadMedidaForm(request.POST)
        if form.is_valid():
            unidad = form.save(commit=False)
            unidad.empresa = request.empresa
            unidad.save()
            messages.success(request, f'Unidad "{unidad.nombre}" creada exitosamente.')
            return redirect('articulos:unidad_medida_list')
    else:
        form = UnidadMedidaForm()
    
    context = {
        'form': form,
        'title': 'Crear Unidad de Medida',
        'submit_text': 'Crear Unidad',
    }
    
    return render(request, 'articulos/unidad_form.html', context)


@requiere_empresa
@login_required
def unidad_medida_update(request, pk):
    """Editar unidad de medida"""
    # Para superusuarios, no filtrar por empresa
    if request.user.is_superuser:
        unidad = get_object_or_404(UnidadMedida, pk=pk)
    else:
        unidad = get_object_or_404(UnidadMedida, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = UnidadMedidaForm(request.POST, instance=unidad)
        if form.is_valid():
            form.save()
            messages.success(request, f'Unidad "{unidad.nombre}" actualizada exitosamente.')
            return redirect('articulos:unidad_medida_list')
    else:
        form = UnidadMedidaForm(instance=unidad)
    
    context = {
        'form': form,
        'unidad': unidad,
        'title': 'Editar Unidad de Medida',
        'submit_text': 'Actualizar Unidad',
    }
    
    return render(request, 'articulos/unidad_form.html', context)


@requiere_empresa
@login_required
def unidad_medida_delete(request, pk):
    """Eliminar unidad de medida"""
    # Para superusuarios, no filtrar por empresa
    if request.user.is_superuser:
        unidad = get_object_or_404(UnidadMedida, pk=pk)
    else:
        unidad = get_object_or_404(UnidadMedida, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nombre = unidad.nombre
        unidad.delete()
        messages.success(request, f'Unidad "{nombre}" eliminada exitosamente.')
        return redirect('articulos:unidad_medida_list')
    
    context = {
        'unidad': unidad,
        'title': 'Eliminar Unidad de Medida',
    }
    
    return render(request, 'articulos/unidad_confirm_delete.html', context)


# Vistas para Impuestos Específicos
@requiere_empresa
@login_required
def impuesto_especifico_list(request):
    """Lista de impuestos específicos"""
    # Filtrar por empresa activa (todos los usuarios, incluyendo superusuarios)
    impuestos = ImpuestoEspecifico.objects.filter(empresa=request.empresa).order_by('nombre')
    
    context = {
        'impuestos': impuestos,
        'title': 'Impuestos Específicos',
    }
    
    return render(request, 'articulos/impuesto_especifico_list.html', context)


@requiere_empresa
@login_required
def impuesto_especifico_create(request):
    """Crear impuesto específico"""
    if request.method == 'POST':
        form = ImpuestoEspecificoForm(request.POST, initial={'empresa': request.empresa})
        if form.is_valid():
            impuesto = form.save(commit=False)
            impuesto.empresa = request.empresa
            impuesto.save()
            messages.success(request, f'Impuesto "{impuesto.nombre}" creado exitosamente.')
            return redirect('articulos:impuesto_especifico_list')
    else:
        form = ImpuestoEspecificoForm(initial={'empresa': request.empresa})
    
    context = {
        'form': form,
        'title': 'Crear Impuesto Específico',
        'submit_text': 'Crear Impuesto',
    }
    
    return render(request, 'articulos/impuesto_especifico_form.html', context)


@requiere_empresa
@login_required
def impuesto_especifico_update(request, pk):
    """Editar impuesto específico"""
    # Para superusuarios, no filtrar por empresa
    if request.user.is_superuser:
        impuesto = get_object_or_404(ImpuestoEspecifico, pk=pk)
    else:
        impuesto = get_object_or_404(ImpuestoEspecifico, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = ImpuestoEspecificoForm(request.POST, instance=impuesto, initial={'empresa': request.empresa})
        if form.is_valid():
            form.save()
            messages.success(request, f'Impuesto "{impuesto.nombre}" actualizado exitosamente.')
            return redirect('articulos:impuesto_especifico_list')
    else:
        form = ImpuestoEspecificoForm(instance=impuesto, initial={'empresa': request.empresa})
    
    context = {
        'form': form,
        'impuesto': impuesto,
        'title': 'Editar Impuesto Específico',
        'submit_text': 'Actualizar Impuesto',
    }
    
    return render(request, 'articulos/impuesto_especifico_form.html', context)


@requiere_empresa
@login_required
def impuesto_especifico_delete(request, pk):
    """Eliminar impuesto específico"""
    # Para superusuarios, no filtrar por empresa
    if request.user.is_superuser:
        impuesto = get_object_or_404(ImpuestoEspecifico, pk=pk)
    else:
        impuesto = get_object_or_404(ImpuestoEspecifico, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nombre = impuesto.nombre
        impuesto.delete()
        messages.success(request, f'Impuesto "{nombre}" eliminado exitosamente.')
        return redirect('articulos:impuesto_especifico_list')
    
    context = {
        'impuesto': impuesto,
        'title': 'Eliminar Impuesto Específico',
    }
    
    return render(request, 'articulos/impuesto_especifico_confirm_delete.html', context)


@csrf_exempt
@login_required
def calcular_precios_articulo(request):
    """Vista AJAX para cálculos bidireccionales de precios"""
    try:
        # Obtener datos del POST
        costo = Decimal(request.POST.get('costo', '0'))
        precio_venta = Decimal(request.POST.get('precio_venta', '0'))
        precio_final = Decimal(request.POST.get('precio_final', '0'))
        margen_porcentaje = Decimal(request.POST.get('margen_porcentaje', '0'))
        impuesto_especifico = Decimal(request.POST.get('impuesto_especifico', '0'))
        modo = request.POST.get('modo', 'margen')  # 'margen', 'precio_venta', 'precio_final'
        
        # Factores de impuestos
        factor_iva = Decimal('1.19')  # IVA 19%
        factor_especifico = (Decimal('1') + impuesto_especifico / Decimal('100')) if impuesto_especifico > 0 else Decimal('1')
        factor_total = factor_iva * factor_especifico
        
        if modo == 'margen' and costo and margen_porcentaje:
            # Calcular precio neto desde margen
            factor_utilidad = Decimal('1') + (margen_porcentaje / Decimal('100'))
            precio_neto = costo * factor_utilidad
            precio_venta = precio_neto
            precio_final = precio_neto * factor_total
            
        elif modo == 'precio_venta' and precio_venta:
            # Calcular desde precio neto
            precio_neto = precio_venta
            precio_final = precio_neto * factor_total
            if costo > 0:
                margen_porcentaje = ((precio_neto / costo) - Decimal('1')) * Decimal('100')
            
        elif modo == 'precio_final' and precio_final:
            # Calcular precio neto hacia atrás desde precio final
            precio_neto = precio_final / factor_total
            precio_venta = precio_neto
            if costo > 0:
                margen_porcentaje = ((precio_neto / costo) - Decimal('1')) * Decimal('100')
        else:
            return JsonResponse({'error': 'Datos insuficientes para el cálculo'}, status=400)
            
        # Redondear resultados
        precio_neto = round(precio_neto, 2)
        precio_venta = round(precio_venta, 2)
        precio_final = round(precio_final, 2)
        margen_porcentaje = round(margen_porcentaje, 2)
        
        # Calcular impuestos
        valor_iva = round(precio_neto * Decimal('0.19'), 2)
        valor_impuesto_especifico = round(precio_neto * (impuesto_especifico / Decimal('100')), 2)
        
        return JsonResponse({
            'precio_neto': str(precio_neto),
            'precio_venta': str(precio_venta),
            'precio_final': str(precio_final),
            'margen_porcentaje': str(margen_porcentaje),
            'valor_iva': str(valor_iva),
            'valor_impuesto_especifico': str(valor_impuesto_especifico)
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({
            'error': f'Error en el cálculo de precios: {str(e)}'
        }, status=400)


@login_required
@requiere_empresa
def categoria_impuesto_especifico(request, categoria_id):
    """Vista AJAX para obtener el impuesto específico de una categoría"""
    try:
        categoria = get_object_or_404(CategoriaArticulo, pk=categoria_id, empresa=request.empresa)
        
        if categoria.impuesto_especifico:
            impuesto_porcentaje = categoria.impuesto_especifico.get_porcentaje_decimal()
            return JsonResponse({
                'success': True,
                'impuesto_especifico_porcentaje': str(impuesto_porcentaje),
                'impuesto_especifico_valor': '0.00',  # Se calculará en el frontend
                'nombre_impuesto': categoria.impuesto_especifico.nombre
            })
        else:
            return JsonResponse({
                'success': True,
                'impuesto_especifico_porcentaje': '0.00',
                'impuesto_especifico_valor': '0.00',
                'nombre_impuesto': 'Ninguno'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_empresa
def buscar_por_codigo_barras(request):
    """Vista AJAX para buscar artículo por código de barras"""
    try:
        codigo = request.GET.get('codigo', '').strip()
        
        if not codigo:
            return JsonResponse({
                'success': False,
                'message': 'Código de barras requerido'
            })
        
        # Buscar artículo por código de barras en la empresa actual
        articulo = Articulo.objects.filter(
            codigo_barras=codigo,
            empresa=request.empresa,
            activo=True
        ).first()
        
        if articulo:
            return JsonResponse({
                'success': True,
                'articulo': {
                    'id': articulo.id,
                    'nombre': articulo.nombre,
                    'descripcion': articulo.descripcion,
                    'precio_costo': str(articulo.precio_costo),
                    'precio_venta': str(articulo.precio_venta),
                    'precio_final': str(articulo.precio_final),
                    'margen_porcentaje': str(articulo.margen_porcentaje),
                    'categoria_id': articulo.categoria.id if articulo.categoria else None,
                    'unidad_medida_id': articulo.unidad_medida.id if articulo.unidad_medida else None,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No se encontró artículo con ese código de barras'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })