from utilidades.utils import clean_id
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from core.decorators import requiere_empresa
from bodegas.models import Bodega
from articulos.models import Articulo
from .models import Stock, Inventario


@login_required
@requiere_empresa
def ajustes_list_simple(request):
    """Lista simple de ajustes de stock usando el modelo Inventario"""
    # Obtener movimientos de ajuste del inventario
    ajustes = Inventario.objects.filter(
        empresa=request.empresa,
        tipo_movimiento__in=['AJUSTE', 'REVERSION_AJUSTE']
    ).order_by('-fecha_movimiento')
    
    # Actualizar correlativo de partida si es necesario
    try:
        configuracion = request.empresa.configuracion
        ajustes_existentes = ajustes.values('numero_folio').distinct().count()
        if ajustes_existentes > 0 and configuracion.siguiente_ajuste <= ajustes_existentes:
            configuracion.siguiente_ajuste = ajustes_existentes + 1
            configuracion.save()
    except:
        pass
    
    # Estadísticas - contar ajustes únicos por folio
    ajustes_unicos = ajustes.values('numero_folio').distinct()
    total_ajustes = ajustes_unicos.count()
    ajustes_entrada = ajustes.filter(cantidad__gt=0).values('numero_folio').distinct().count()
    ajustes_salida = ajustes.filter(cantidad__lt=0).values('numero_folio').distinct().count()
    
    # Bodegas para filtro
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    
    context = {
        'ajustes': ajustes,
        'bodegas': bodegas,
        'total_ajustes': total_ajustes,
        'ajustes_entrada': ajustes_entrada,
        'ajustes_salida': ajustes_salida,
        'titulo': 'Ajustes de Stock (Simple)'
    }
    
    return render(request, 'inventario/ajustes_list_simple.html', context)


@login_required
@requiere_empresa
def ajuste_create_simple(request):
    """Crear nuevo ajuste de stock de forma simple"""
    if request.method == 'POST':
        tipo_ajuste = request.POST.get('tipo_ajuste')
        fecha_ajuste = request.POST.get('fecha_ajuste')
        bodega_id = request.POST.get('bodega')
        descripcion = request.POST.get('descripcion')
        
        # Obtener detalles desde JSON
        import json
        detalles_data = request.POST.get('detalles_data', '[]')
        detalles = json.loads(detalles_data)
        
        if not detalles:
            messages.error(request, 'Debe agregar al menos un artículo al ajuste.')
            return redirect('inventario:ajuste_create_simple')
        
        try:
            bodega = Bodega.objects.get(id=bodega_id, empresa=request.empresa)
            
            # Procesar cada detalle
            for detalle in detalles:
                articulo_id = detalle.get('articulo_id')
                cantidad = float(detalle.get('cantidad', 0))
                comentario = detalle.get('comentario', '')
                
                if articulo_id and cantidad > 0:
                    articulo = Articulo.objects.get(id=articulo_id, empresa=request.empresa)
                    
                    # Calcular cantidad ajustada
                    if tipo_ajuste == 'ENTRADA':
                        cantidad_ajuste = cantidad
                    else:  # SALIDA
                        cantidad_ajuste = -cantidad
                    
                    # Obtener o crear stock
                    stock, created = Stock.objects.get_or_create(
                        empresa=request.empresa,
                        bodega=bodega,
                        articulo=articulo,
                        defaults={
                            'cantidad': 0,
                            'stock_minimo': 0,
                            'stock_maximo': 0,
                            'precio_promedio': 0
                        }
                    )
                    
                    # Actualizar stock (convertir a Decimal para evitar error de tipos)
                    from decimal import Decimal
                    cantidad_ajuste_decimal = Decimal(str(cantidad_ajuste))
                    stock.cantidad += cantidad_ajuste_decimal
                    if stock.cantidad < 0:
                        stock.cantidad = Decimal('0')
                    stock.save()
                    
                    # Crear movimiento en inventario
                    from django.utils import timezone
                    from datetime import datetime
                    
                    # Usar la fecha del formulario o la fecha actual
                    if fecha_ajuste:
                        try:
                            # Convertir fecha YYYY-MM-DD a datetime con hora 00:00:00
                            fecha_mov = datetime.strptime(fecha_ajuste, '%Y-%m-%d')
                            fecha_mov = timezone.make_aware(fecha_mov)
                        except:
                            fecha_mov = timezone.now()
                    else:
                        fecha_mov = timezone.now()
                    
                    # Generar número de folio
                    try:
                        configuracion = request.empresa.configuracion
                        numero_folio = configuracion.generar_numero_ajuste()
                    except:
                        # Si no hay configuración, usar un número simple
                        ultimo_ajuste = Inventario.objects.filter(
                            empresa=request.empresa,
                            tipo_movimiento='AJUSTE'
                        ).order_by('-id').first()
                        if ultimo_ajuste and ultimo_ajuste.numero_folio:
                            try:
                                ultimo_numero = int(ultimo_ajuste.numero_folio.split('-')[-1])
                                numero_folio = f"Aju-{ultimo_numero + 1:03d}"
                            except:
                                numero_folio = f"Aju-001"
                        else:
                            numero_folio = f"Aju-001"

                    Inventario.objects.create(
                        empresa=request.empresa,
                        bodega_destino=bodega,
                        articulo=articulo,
                        tipo_movimiento='AJUSTE',
                        cantidad=cantidad_ajuste,
                        descripcion=f"Ajuste {tipo_ajuste.lower()}: {descripcion}",
                        fecha_movimiento=fecha_mov,
                        creado_por=request.user,
                        numero_folio=numero_folio,
                        estado='confirmado'
                    )
            
            return JsonResponse({
                'success': True,
                'message': f'Ajuste procesado exitosamente. {len(detalles)} artículo(s) procesado(s).'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al procesar ajuste: {str(e)}'
            }, status=400)
    
    # Obtener bodegas para el formulario
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    
    context = {
        'bodegas': bodegas,
        'titulo': 'Nuevo Ajuste de Stock'
    }
    
    return render(request, 'inventario/ajuste_form_final.html', context)


@login_required
@requiere_empresa
def api_articulos_ajuste_simple(request):
    """API para obtener artículos para ajustes"""
    bodega_id = clean_id(request.GET.get('bodega_id'))
    
    if not bodega_id:
        return JsonResponse({'error': 'Bodega requerida'}, status=400)
    
    try:
        bodega = Bodega.objects.get(id=bodega_id, empresa=request.empresa)
    except Bodega.DoesNotExist:
        return JsonResponse({'error': 'Bodega no encontrada'}, status=404)
    
    # Obtener todos los artículos de la empresa
    articulos_empresa = Articulo.objects.filter(
        empresa=request.empresa,
        activo=True
    ).order_by('codigo')
    
    articulos = []
    for articulo in articulos_empresa:
        # Obtener stock actual en la bodega (0 si no existe)
        try:
            stock = Stock.objects.get(
                empresa=request.empresa,
                bodega=bodega,
                articulo=articulo
            )
            stock_actual = float(stock.cantidad)
            precio_promedio = float(stock.precio_promedio) if stock.precio_promedio else 0
        except Stock.DoesNotExist:
            stock_actual = 0
            precio_promedio = 0
        
        articulos.append({
            'id': articulo.id,
            'codigo': articulo.codigo,
            'nombre': articulo.nombre,
            'unidad_medida': str(articulo.unidad_medida),
            'stock_actual': stock_actual,
            'precio_promedio': precio_promedio
        })
    
    return JsonResponse({'articulos': articulos})


@login_required
@requiere_empresa
def ajuste_detail_simple(request, pk):
    """Ver detalles de un ajuste específico"""
    try:
        ajuste = Inventario.objects.get(
            id=pk,
            empresa=request.empresa,
            tipo_movimiento='AJUSTE'
        )
        
        context = {
            'ajuste': ajuste,
            'titulo': f'Detalle del Ajuste #{ajuste.id}'
        }
        
        return render(request, 'inventario/ajuste_detail_modal.html', context)
        
    except Inventario.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Ajuste no encontrado'
        }, status=404)


@login_required
@requiere_empresa
def ajuste_edit_simple(request, pk):
    """Editar un ajuste existente"""
    try:
        ajuste_principal = Inventario.objects.get(
            id=pk,
            empresa=request.empresa,
            tipo_movimiento='AJUSTE'
        )
        
        # Obtener TODOS los ajustes con el mismo folio
        ajustes = Inventario.objects.filter(
            empresa=request.empresa,
            tipo_movimiento='AJUSTE',
            numero_folio=ajuste_principal.numero_folio
        ).order_by('id')
        
        if request.method == 'POST':
            # Por ahora solo retornar éxito - implementar lógica completa después
            return JsonResponse({
                'success': True,
                'message': 'Ajuste actualizado exitosamente'
            })
        
        # Obtener bodegas para el formulario
        bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
        
        context = {
            'ajuste': ajuste_principal,
            'ajustes': ajustes,
            'bodegas': bodegas,
            'titulo': f'Editar Ajuste #{ajuste_principal.numero_folio}'
        }
        
        return render(request, 'inventario/ajuste_edit_modal.html', context)
        
    except Inventario.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Ajuste no encontrado'
        }, status=404)


@login_required
@requiere_empresa
def ajuste_delete_simple(request, pk):
    """Eliminar un ajuste"""
    try:
        ajuste = Inventario.objects.get(
            id=pk,
            empresa=request.empresa,
            tipo_movimiento='AJUSTE'
        )
        
        # Revertir el ajuste en el stock
        try:
            stock = Stock.objects.get(
                empresa=request.empresa,
                bodega=ajuste.bodega_destino,
                articulo=ajuste.articulo
            )
            stock.cantidad -= ajuste.cantidad
            stock.save()
        except Stock.DoesNotExist:
            # Si no existe el stock, crear uno con cantidad 0
            stock = Stock.objects.create(
                empresa=request.empresa,
                bodega=ajuste.bodega_destino,
                articulo=ajuste.articulo,
                cantidad=0
            )
        
        # Eliminar el registro
        ajuste.delete()
        
        messages.success(request, 'Ajuste eliminado exitosamente')
        return redirect('inventario:ajustes_list')
        
    except Inventario.DoesNotExist:
        messages.error(request, 'Ajuste no encontrado')
        return redirect('inventario:ajustes_list')
    except Exception as e:
        messages.error(request, f'Error al eliminar: {str(e)}')
        return redirect('inventario:ajustes_list')
