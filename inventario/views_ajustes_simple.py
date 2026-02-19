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
    )
    
    # Aplicar filtros
    bodega_id = request.GET.get('bodega')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    tipo = request.GET.get('tipo')
    
    if bodega_id:
        ajustes = ajustes.filter(bodega_destino_id=bodega_id)
        
    if fecha_desde:
        ajustes = ajustes.filter(fecha_movimiento__date__gte=fecha_desde)
        
    if fecha_hasta:
        ajustes = ajustes.filter(fecha_movimiento__date__lte=fecha_hasta)
        
    if tipo:
        if tipo == 'entrada':
            ajustes = ajustes.filter(cantidad__gt=0)
        elif tipo == 'salida':
            ajustes = ajustes.filter(cantidad__lt=0)
            
    ajustes = ajustes.order_by('-fecha_movimiento')
    
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
    
    return render(request, 'inventario/ajuste_create_modal.html', context)


@login_required
@requiere_empresa
def api_articulos_ajuste_simple(request):
    """API para obtener artículos para ajustes"""
    try:
        bodega_id_str = request.GET.get('bodega_id', '')
        q = request.GET.get('q',('').strip())
        
        # Validación básica de bodega
        if not bodega_id_str:
             return JsonResponse({'error': 'Bodega no especificada'}, status=400)
             
        try:
            bodega_id = int(bodega_id_str)
            bodega = Bodega.objects.get(id=bodega_id, empresa=request.empresa)
        except (ValueError, TypeError, Bodega.DoesNotExist):
            return JsonResponse({'error': 'Bodega inválida o no encontrada'}, status=404)

        # Base QuerySet
        articulos_qs = Articulo.objects.filter(
            empresa=request.empresa,
            activo=True
        )
        
        # Búsqueda
        if q:
            from django.db.models import Q
            articulos_qs = articulos_qs.filter(
                Q(codigo__icontains=q) |
                Q(nombre__icontains=q) |
                Q(codigo_barras__icontains=q)
            ).distinct()
            
            # Limitar
            articulos_qs = articulos_qs.order_by('nombre')[:50]
        else:
            # Default
            articulos_qs = articulos_qs.order_by('nombre')[:20]
            
        articulos_data = []
        for articulo in articulos_qs:
            # Obtener stock
            stock_actual = 0
            precio_promedio = 0
            
            # Intentar obtener stock de forma eficiente
            stock_qs = Stock.objects.filter(
                empresa=request.empresa,
                bodega=bodega,
                articulo=articulo
            ).first()
            
            if stock_qs:
                stock_actual = float(stock_qs.cantidad)
                precio_promedio = float(stock_qs.precio_promedio or 0)
            
            articulos_data.append({
                'id': articulo.id,
                'codigo': articulo.codigo,
                'nombre': articulo.nombre,
                'unidad_medida': str(articulo.unidad_medida),
                'stock_actual': stock_actual,
                'precio_promedio': precio_promedio
            })
            
        return JsonResponse({'articulos': articulos_data})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


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
            import json
            from decimal import Decimal
            from django.utils import timezone
            from datetime import datetime
            
            tipo_ajuste = request.POST.get('tipo_ajuste')
            fecha_ajuste = request.POST.get('fecha_ajuste')
            bodega_id = request.POST.get('bodega')
            descripcion = request.POST.get('descripcion')
            
            # Obtener detalles desde JSON
            detalles_data = request.POST.get('detalles_data', '[]')
            detalles = json.loads(detalles_data)
            
            if not detalles:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe agregar al menos un artículo al ajuste.'
                })
            
            try:
                bodega = Bodega.objects.get(id=bodega_id, empresa=request.empresa)
                
                # Revertir stock de los ajustes anteriores
                # Como el modelo guarda cantidad positiva, necesitamos determinar el tipo original
                # Revisamos el descripcion o el tipo_movimiento para saber si era entrada o salida
                for ajuste_anterior in ajustes:
                    stock_anterior = Stock.objects.filter(
                        empresa=request.empresa,
                        bodega=ajuste_anterior.bodega_destino,
                        articulo=ajuste_anterior.articulo
                    ).first()
                    if stock_anterior:
                        cantidad_anterior = Decimal(str(ajuste_anterior.cantidad))
                        # Determinar si era entrada o salida basándonos en la descripción
                        desc_anterior = (ajuste_anterior.descripcion or '').lower()
                        es_salida = 'salida' in desc_anterior or ajuste_anterior.cantidad < 0
                        
                        if es_salida:
                            # Era salida (restó del stock), revertimos sumando
                            stock_anterior.cantidad += cantidad_anterior
                        else:
                            # Era entrada (sumó al stock), revertimos restando
                            stock_anterior.cantidad -= cantidad_anterior
                        
                        if stock_anterior.cantidad < 0:
                            stock_anterior.cantidad = Decimal('0')
                        stock_anterior.save()
                
                # Eliminar ajustes anteriores
                ajustes.delete()
                
                # Crear nuevos ajustes
                numero_folio = ajuste_principal.numero_folio  # Mantener el mismo folio
                
                for detalle in detalles:
                    articulo_id = detalle.get('articulo_id')
                    cantidad = float(detalle.get('cantidad', 0))
                    comentario = detalle.get('comentario', '')
                    
                    if articulo_id and cantidad != 0:
                        articulo = Articulo.objects.get(id=articulo_id, empresa=request.empresa)
                        
                        # La cantidad ya viene con el signo correcto desde el frontend
                        cantidad_ajuste = Decimal(str(cantidad))
                        
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
                        
                        # Actualizar stock
                        stock.cantidad += cantidad_ajuste
                        if stock.cantidad < 0:
                            stock.cantidad = Decimal('0')
                        stock.save()
                        
                        # Usar la fecha del formulario o la fecha actual
                        if fecha_ajuste:
                            try:
                                fecha_mov = datetime.strptime(fecha_ajuste, '%Y-%m-%d')
                                fecha_mov = timezone.make_aware(fecha_mov)
                            except:
                                fecha_mov = timezone.now()
                        else:
                            fecha_mov = timezone.now()
                        
                        # Crear nuevo movimiento en inventario
                        # El modelo Inventario guarda cantidad positiva, pero para ajustes
                        # guardamos el valor con signo para mantener consistencia con la creación
                        # Si cantidad_ajuste es negativo, lo guardamos como positivo pero el stock ya se actualizó correctamente
                        cantidad_para_guardar = abs(cantidad_ajuste)
                        
                        # Si es salida, guardamos como negativo en el campo cantidad (si el modelo lo permite)
                        # pero el stock ya se actualizó correctamente arriba
                        Inventario.objects.create(
                            empresa=request.empresa,
                            bodega_destino=bodega,
                            articulo=articulo,
                            tipo_movimiento='AJUSTE',
                            cantidad=cantidad_para_guardar,  # Guardar valor absoluto
                            precio_unitario=articulo.precio_venta or Decimal('0'),
                            descripcion=descripcion,
                            fecha_movimiento=fecha_mov,
                            numero_folio=numero_folio,
                            estado='confirmado',
                            creado_por=request.user
                        )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Ajuste actualizado exitosamente'
                })
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return JsonResponse({
                    'success': False,
                    'message': f'Error al actualizar el ajuste: {str(e)}'
                })
        
        # Obtener bodegas para el formulario
        bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
        
        # Calcular cantidad absoluta para mostrar en el formulario
        # Convertir Decimal a float y luego a string para asegurar compatibilidad
        cantidad_valor = float(ajuste_principal.cantidad) if ajuste_principal.cantidad else 0.0
        cantidad_absoluta = abs(cantidad_valor)
        # Formatear a 2 decimales como string para el input
        cantidad_absoluta_str = f"{cantidad_absoluta:.2f}"
        
        context = {
            'ajuste': ajuste_principal,
            'ajustes': ajustes,
            'bodegas': bodegas,
            'cantidad_absoluta': cantidad_absoluta,
            'cantidad_absoluta_str': cantidad_absoluta_str,
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
