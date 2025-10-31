from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime
from decimal import Decimal

from .models import OrdenPedido, ItemOrdenPedido #, DespachoPedido
from .forms import OrdenPedidoForm, ItemOrdenPedidoFormSet, BusquedaPedidoForm #, DespachoPedidoForm, DespachoEstadoForm, BusquedaDespachoForm, ItemDespachoPedidoFormSet
from empresas.models import Empresa
from articulos.models import Articulo
from core.decorators import requiere_empresa


@login_required
@requiere_empresa
def orden_pedido_list(request):
    """Lista de órdenes de pedido"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')
    
    # Obtener pedidos
    pedidos = OrdenPedido.objects.filter(empresa=empresa).select_related(
        'cliente', 'bodega', 'creado_por'
    ).order_by('-fecha_pedido', '-numero_pedido')
    
    # Aplicar filtros
    search_form = BusquedaPedidoForm(request.GET)
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        estado = search_form.cleaned_data.get('estado')
        cliente = search_form.cleaned_data.get('cliente')
        fecha_desde = search_form.cleaned_data.get('fecha_desde')
        fecha_hasta = search_form.cleaned_data.get('fecha_hasta')
        
        if search:
            pedidos = pedidos.filter(
                Q(numero_pedido__icontains=search) |
                Q(cliente__nombre__icontains=search) |
                Q(numero_oc_cliente__icontains=search)
            )
        if estado:
            pedidos = pedidos.filter(estado=estado)
        if cliente:
            pedidos = pedidos.filter(cliente=cliente)
        if fecha_desde:
            pedidos = pedidos.filter(fecha_pedido__gte=fecha_desde)
        if fecha_hasta:
            pedidos = pedidos.filter(fecha_pedido__lte=fecha_hasta)
    
    # Estadísticas
    stats = {
        'total_pedidos': pedidos.count(),
        'pedidos_borrador': pedidos.filter(estado='borrador').count(),
        'pedidos_confirmados': pedidos.filter(estado='confirmada').count(),
        'pedidos_en_proceso': pedidos.filter(estado='en_proceso').count(),
        'pedidos_completados': pedidos.filter(estado='completada').count(),
        'monto_total': pedidos.aggregate(total=Sum('total_pedido'))['total'] or 0,
    }
    
    # Paginación
    paginator = Paginator(pedidos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'stats': stats,
        'empresa': empresa,
    }
    
    return render(request, 'pedidos/orden_pedido_list.html', context)


@login_required
@requiere_empresa
def orden_pedido_create(request):
    """Crear nueva orden de pedido"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')
    
    if request.method == 'POST':
        print("=== DEBUG PEDIDO POST ===")
        print(f"POST data: {request.POST}")
        
        form = OrdenPedidoForm(request.POST)
        formset = ItemOrdenPedidoFormSet(request.POST, empresa=empresa)
        
        print(f"Form valid: {form.is_valid()}")
        print(f"Formset valid: {formset.is_valid()}")
        
        if not form.is_valid():
            print(f"Form errors: {form.errors}")
        
        if not formset.is_valid():
            print(f"Formset errors: {formset.errors}")
            print(f"Formset non_form_errors: {formset.non_form_errors()}")
        
        if form.is_valid() and formset.is_valid():
            try:
                pedido = form.save(commit=False)
                pedido.empresa = empresa
                pedido.creado_por = request.user
                
                # Generar número de pedido
                pedido.generar_numero_pedido()
                print(f"Numero de pedido generado: {pedido.numero_pedido}")
                pedido.save()
                print(f"Pedido guardado con ID: {pedido.id}")
                
                # Guardar items
                formset.instance = pedido
                items = formset.save()
                print(f"Items guardados: {len(items)}")
                
                # Calcular totales
                pedido.calcular_totales()
                print(f"Totales calculados - Total: {pedido.total_pedido}")
                
                messages.success(request, f'Orden de pedido {pedido.numero_pedido} creada exitosamente.')
                return redirect('pedidos:orden_pedido_detail', pk=pedido.pk)
            except Exception as e:
                import traceback
                print(f"Error al guardar: {str(e)}")
                print(traceback.format_exc())
                messages.error(request, f'Error al guardar el pedido: {str(e)}')
        else:
            # Mostrar errores del formulario
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'Campo {field}: {error}')
            if formset.errors:
                for i, form_errors in enumerate(formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            for error in errors:
                                messages.error(request, f'Item {i+1} - {field}: {error}')
                if formset.non_form_errors():
                    for error in formset.non_form_errors():
                        messages.error(request, f'Error general: {error}')
    else:
        form = OrdenPedidoForm()
        formset = ItemOrdenPedidoFormSet(empresa=empresa)
    
    # Obtener artículos de la empresa
    articulos_empresa = Articulo.objects.filter(empresa=empresa).order_by('nombre')
    
    context = {
        'form': form,
        'formset': formset,
        'articulos_empresa': articulos_empresa,
        'empresa': empresa,
    }
    
    return render(request, 'pedidos/orden_pedido_form.html', context)


@login_required
@requiere_empresa
def orden_pedido_detail(request, pk):
    """Ver detalle de orden de pedido"""
    pedido = get_object_or_404(OrdenPedido, pk=pk)
    
    # Verificar que el pedido pertenece a la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and pedido.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para ver este pedido.')
            return redirect('pedidos:orden_pedido_list')
    else:
        try:
            if pedido.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para ver este pedido.')
                return redirect('pedidos:orden_pedido_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')
    
    items = pedido.items.select_related('articulo').all()
    
    # Obtener despachos asociados
    despachos = pedido.despachos.select_related('creado_por').prefetch_related('items').all()
    
    context = {
        'pedido': pedido,
        'items': items,
        'despachos': despachos,
    }
    
    return render(request, 'pedidos/orden_pedido_detail.html', context)


@login_required
@requiere_empresa
def orden_pedido_update(request, pk):
    """Editar orden de pedido"""
    pedido = get_object_or_404(OrdenPedido, pk=pk)
    
    # Verificar permisos
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and pedido.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para editar este pedido.')
            return redirect('pedidos:orden_pedido_list')
    else:
        try:
            if pedido.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para editar este pedido.')
                return redirect('pedidos:orden_pedido_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')
    
    if request.method == 'POST':
        form = OrdenPedidoForm(request.POST, instance=pedido)
        formset = ItemOrdenPedidoFormSet(request.POST, instance=pedido, empresa=pedido.empresa)
        
        if form.is_valid() and formset.is_valid():
            pedido = form.save()
            formset.save()
            
            # Recalcular totales
            pedido.calcular_totales()
            
            messages.success(request, f'Orden de pedido {pedido.numero_pedido} actualizada exitosamente.')
            return redirect('pedidos:orden_pedido_detail', pk=pedido.pk)
    else:
        form = OrdenPedidoForm(instance=pedido)
        formset = ItemOrdenPedidoFormSet(instance=pedido, empresa=pedido.empresa)
    
    # Obtener artículos de la empresa
    articulos_empresa = Articulo.objects.filter(empresa=pedido.empresa).order_by('nombre')
    
    context = {
        'form': form,
        'formset': formset,
        'pedido': pedido,
        'articulos_empresa': articulos_empresa,
        'empresa': pedido.empresa,
    }
    
    return render(request, 'pedidos/orden_pedido_form.html', context)


@login_required
@requiere_empresa
def orden_pedido_delete(request, pk):
    """Eliminar orden de pedido"""
    pedido = get_object_or_404(OrdenPedido, pk=pk)
    
    # Verificar permisos
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and pedido.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para eliminar este pedido.')
            return redirect('pedidos:orden_pedido_list')
    else:
        try:
            if pedido.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para eliminar este pedido.')
                return redirect('pedidos:orden_pedido_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')
    
    if request.method == 'POST':
        numero_pedido = pedido.numero_pedido
        pedido.delete()
        messages.success(request, f'Orden de pedido {numero_pedido} eliminada exitosamente.')
        return redirect('pedidos:orden_pedido_list')
    
    context = {
        'pedido': pedido,
    }
    
    return render(request, 'pedidos/orden_pedido_confirm_delete.html', context)


@login_required
@requiere_empresa
def orden_pedido_cambiar_estado(request, pk):
    """Cambiar estado de orden de pedido"""
    pedido = get_object_or_404(OrdenPedido, pk=pk)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in dict(OrdenPedido.ESTADO_CHOICES):
            pedido.estado = nuevo_estado
            pedido.save()
            messages.success(request, f'Estado del pedido {pedido.numero_pedido} actualizado a {pedido.get_estado_display()}.')
        else:
            messages.error(request, 'Estado inválido.')
    
    return redirect('pedidos:orden_pedido_detail', pk=pk)


# === VISTAS PARA DESPACHOS DE PEDIDOS ===

'''
@login_required
@requiere_empresa
def despacho_list(request):
    """Lista de despachos de pedidos"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')

    # Obtener despachos
    despachos = DespachoPedido.objects.filter(
        empresa=empresa
    ).select_related(
        'pedido__cliente', 'pedido__bodega', 'creado_por',
        'guia_despacho', 'factura_directa', 'transferencia_inventario'
    ).order_by('-fecha_despacho')

    # Aplicar filtros
    search_form = BusquedaDespachoForm(request.GET, empresa=empresa)
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        estado = search_form.cleaned_data.get('estado')
        tipo_despacho = search_form.cleaned_data.get('tipo_despacho')
        cliente = search_form.cleaned_data.get('cliente')
        fecha_desde = search_form.cleaned_data.get('fecha_desde')
        fecha_hasta = search_form.cleaned_data.get('fecha_hasta')

        if search:
            despachos = despachos.filter(
                Q(pedido__numero_pedido__icontains=search) |
                Q(pedido__cliente__nombre__icontains=search) |
                Q(transportista__icontains=search) |
                Q(contacto_entrega__icontains=search)
            )
        if estado:
            despachos = despachos.filter(estado=estado)
        if tipo_despacho:
            despachos = despachos.filter(tipo_despacho=tipo_despacho)
        if cliente:
            despachos = despachos.filter(pedido__cliente=cliente)
        if fecha_desde:
            despachos = despachos.filter(fecha_despacho__date__gte=fecha_desde)
        if fecha_hasta:
            despachos = despachos.filter(fecha_despacho__date__lte=fecha_hasta)

    # Estadísticas
    stats = {
        'total_despachos': despachos.count(),
        'despachos_pendientes': despachos.filter(estado='pendiente').count(),
        'despachos_preparando': despachos.filter(estado='preparando').count(),
        'despachos_despachados': despachos.filter(estado='despachado').count(),
        'despachos_entregados': despachos.filter(estado='entregado').count(),
        'guias_pendientes': despachos.filter(estado__in=['pendiente', 'preparando'], tipo_despacho='guia', guia_despacho__isnull=True).count(),
        'facturas_pendientes': despachos.filter(estado__in=['pendiente', 'preparando'], tipo_despacho__in=['factura_directa', 'boleta_directa'], factura_directa__isnull=True).count(),
    }

    # Paginación
    paginator = Paginator(despachos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'stats': stats,
        'empresa': empresa,
    }

    return render(request, 'pedidos/despacho_list.html', context)


@login_required
@requiere_empresa
def despacho_create(request):
    """Crear nuevo despacho de pedido"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')

    # Debug: verificar empresa y pedidos disponibles
    debug_info = {
        'empresa_id': empresa.id if empresa else None,
        'empresa_nombre': empresa.nombre if empresa else None,
        'user_is_superuser': request.user.is_superuser,
        'session_empresa_activa': request.session.get('empresa_activa')
    }

    # Verificar pedidos disponibles para despachar
    pedidos_totales = OrdenPedido.objects.filter(empresa=empresa).count()
    pedidos_disponibles = OrdenPedido.objects.filter(
        empresa=empresa,
        estado__in=['confirmada', 'en_proceso', 'preparando_despacho']
    ).count()
    estados_pedidos = OrdenPedido.objects.filter(empresa=empresa).values_list('estado', flat=True).distinct()

    debug_info.update({
        'pedidos_totales': pedidos_totales,
        'pedidos_disponibles': pedidos_disponibles,
        'estados_pedidos': list(estados_pedidos)
    })

    if request.method == 'POST':
        # Crear formulario
        form = DespachoPedidoForm(request.POST, empresa=empresa)

        submit_despacho = request.POST.get('submit_despacho') == '1'

        if form.is_valid() or submit_despacho:
            try:
                # Log de entrada al procesamiento
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"🚀 Iniciando creación de despacho - Usuario: {request.user}, Empresa: {empresa}")
                logger.info(f"📦 Creando despacho para pedido: {despacho.pedido.numero_pedido}")
                despacho = form.save(commit=False)
                despacho.empresa = empresa
                despacho.creado_por = request.user

                # Copiar información de entrega del pedido si no se especificó
                pedido = despacho.pedido
                if not despacho.direccion_entrega and pedido.direccion_entrega:
                    despacho.direccion_entrega = pedido.direccion_entrega
                if not despacho.contacto_entrega and pedido.contacto_entrega:
                    despacho.contacto_entrega = pedido.contacto_entrega
                if not despacho.telefono_entrega and pedido.telefono_entrega:
                    despacho.telefono_entrega = pedido.telefono_entrega
                if not despacho.fecha_entrega_estimada and pedido.fecha_entrega_requerida:
                    despacho.fecha_entrega_estimada = pedido.fecha_entrega_requerida

                logger.info(f"💾 Guardando despacho...")
                # Crear transferencia de inventario ANTES de guardar el despacho
                from .utils import crear_transferencia_inventario
                try:
                    # Usar datos del POST para crear items si es submit directo
                    if submit_despacho:
                        items_data = {k: v for k, v in request.POST.items() if k.startswith(('despachar_', 'item_'))}
                        transferencia = crear_transferencia_inventario(despacho, items_data)
                    else:
                        transferencia = crear_transferencia_inventario(despacho, None)

                    despacho.transferencia_inventario = transferencia
                    logger.info(f"✅ Transferencia creada: {transferencia.numero_folio}")
                except Exception as e:
                    logger.error(f"❌ Error creando transferencia: {e}")
                    # Crear transferencia básica como fallback
                    from inventario.models import TransferenciaInventario
                    transferencia = TransferenciaInventario.objects.create(
                        empresa=empresa,
                        bodega_origen=pedido.bodega,
                        bodega_destino=None,
                        numero_folio=f"TRF-FALLBACK-{pedido.numero_pedido}",
                        fecha_transferencia=timezone.now(),
                        observaciones=f"Transferencia fallback para despacho {pedido.numero_pedido}",
                        estado='confirmado',
                        creado_por=request.user
                    )
                    despacho.transferencia_inventario = transferencia
                    logger.info(f"✅ Transferencia fallback creada: {transferencia.numero_folio}")

                logger.info(f"💾 Guardando despacho en base de datos...")
                despacho.save()
                logger.info(f"✅ Despacho guardado exitosamente - ID: {despacho.pk}")

                # Procesar items seleccionados usando la lógica del modelo
                logger.info(f"📦 Procesando {items_pedido.count()} items del pedido")
                items_procesados = 0
                items_pedido = pedido.items.all()

                for item_pedido in items_pedido:
                    item_id = str(item_pedido.id)
                    checkbox_name = f'despachar_{item_id}'

                    # Verificar si el item fue seleccionado
                    if checkbox_name in request.POST and request.POST[checkbox_name] == 'on':
                        cantidad = request.POST.get(f'item_{item_id}', 0)
                        try:
                            cantidad = float(cantidad)
                            if cantidad > 0 and cantidad <= item_pedido.cantidad:
                                # Crear el item de despacho usando el modelo
                                ItemDespachoPedido.objects.create(
                                    despacho=despacho,
                                    item_pedido=item_pedido,
                                    cantidad_despachar=cantidad,
                                    observaciones=request.POST.get(f'obs_{item_id}', '')
                                )
                                items_procesados += 1
                                logger.info(f"✅ Item procesado: {item_pedido.articulo.nombre} - {cantidad} unidades")
                            else:
                                logger.warning(f"❌ Cantidad inválida para {item_pedido.articulo.nombre}: {cantidad}")
                                messages.warning(request, f'Cantidad inválida para {item_pedido.articulo.nombre}')
                        except (ValueError, TypeError) as e:
                            logger.error(f"❌ Error procesando cantidad para {item_pedido.articulo.nombre}: {e}")
                            messages.error(request, f'Cantidad inválida para {item_pedido.articulo.nombre}')

                logger.info(f"📊 Items procesados: {items_procesados}/{items_pedido.count()}")

                # Verificar que se procesaron al menos algunos items
                if items_procesados == 0:
                    logger.error("❌ No se procesaron items - eliminando despacho")
                    messages.error(request, 'Debe seleccionar al menos un artículo para despachar.')
                    despacho.delete()
                    return redirect('pedidos:despacho_create')

                # Actualizar estado del pedido solo si hay items
                if despacho.tiene_items_despachados():
                    logger.info(f"📈 Actualizando estado del pedido a 'preparando_despacho'")
                    pedido.estado = 'preparando_despacho'
                    pedido.save()

                logger.info(f"🎉 Despacho creado exitosamente - ID: {despacho.pk}, Items: {items_procesados}")
                messages.success(request, f'Despacho para pedido {pedido.numero_pedido} creado exitosamente con {items_procesados} items.')
                return redirect('pedidos:despacho_detail', pk=despacho.pk)

            except Exception as e:
                logger.error(f"❌ Error crítico al crear despacho: {e}")
                messages.error(request, f'Error al crear el despacho: {str(e)}')
        else:
            # Mostrar errores del formulario
            logger.warning(f"❌ Formulario no válido: {form.errors}")
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')

    else:
        form = DespachoPedidoForm(empresa=empresa)

    # Obtener pedidos disponibles para despachar
    pedidos_disponibles = OrdenPedido.objects.filter(
        empresa=empresa,
        estado__in=['confirmada', 'en_proceso', 'preparando_despacho']
    ).select_related('cliente', 'bodega').order_by('-fecha_pedido')

    context = {
        'form': form,
        'pedidos_disponibles': pedidos_disponibles,
        'empresa': empresa,
        'debug_info': debug_info,
        'debug': True,  # Mostrar información de debug
    }

    return render(request, 'pedidos/despacho_form.html', context)


@login_required
@requiere_empresa
def despacho_detail(request, pk):
    """Ver detalle de despacho"""
    despacho = get_object_or_404(DespachoPedido, pk=pk)

    # Verificar que el despacho pertenece a la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and despacho.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para ver este despacho.')
            return redirect('pedidos:despacho_list')
    else:
        try:
            if despacho.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para ver este despacho.')
                return redirect('pedidos:despacho_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')

    # Items del pedido y del despacho
    items_pedido = despacho.pedido.items.select_related('articulo').all()
    items_despachados = despacho.get_items_despachados()

    context = {
        'despacho': despacho,
        'items_pedido': items_pedido,
        'items_despachados': items_despachados,
        'pedido': despacho.pedido,
        'totales_despacho': despacho.calcular_totales_despacho() if items_despachados else None,
        'items_pendientes': despacho.get_pendiente_por_despachar() if despacho.tiene_items_despachados() else [],
    }

    return render(request, 'pedidos/despacho_detail.html', context)


@login_required
@requiere_empresa
def despacho_update(request, pk):
    """Editar despacho"""
    despacho = get_object_or_404(DespachoPedido, pk=pk)

    # Verificar permisos
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and despacho.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para editar este despacho.')
            return redirect('pedidos:despacho_list')
    else:
        try:
            if despacho.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para editar este despacho.')
                return redirect('pedidos:despacho_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')

    if request.method == 'POST':
        form = DespachoPedidoForm(request.POST, instance=despacho, empresa=despacho.empresa)

        if form.is_valid():
            despacho = form.save()
            messages.success(request, f'Despacho {despacho.pedido.numero_pedido} actualizado exitosamente.')
            return redirect('pedidos:despacho_detail', pk=despacho.pk)
    else:
        form = DespachoPedidoForm(instance=despacho, empresa=despacho.empresa)

    # Items del pedido
    items = despacho.pedido.items.select_related('articulo').all()

    context = {
        'form': form,
        'despacho': despacho,
        'items': items,
        'pedido': despacho.pedido,
    }

    return render(request, 'pedidos/despacho_form.html', context)


@login_required
@requiere_empresa
def despacho_cambiar_estado(request, pk):
    """Cambiar estado de despacho"""
    despacho = get_object_or_404(DespachoPedido, pk=pk)

    # Verificar permisos
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and despacho.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para modificar este despacho.')
            return redirect('pedidos:despacho_list')
    else:
        try:
            if despacho.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para modificar este despacho.')
                return redirect('pedidos:despacho_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')

    if request.method == 'POST':
        form = DespachoEstadoForm(request.POST, instance=despacho)

        if form.is_valid():
            despacho_anterior = despacho.estado
            despacho = form.save()

            # Si se está despachando, generar documentos DTE
            if despacho.estado == 'despachado' and despacho_anterior != 'despachado':
                try:
                    from .utils import generar_documento_despacho
                    generar_documento_despacho(despacho)
                    messages.success(request, 'Documento DTE generado exitosamente.')
                except Exception as e:
                    messages.warning(request, f'Documento DTE no pudo generarse: {str(e)}')

            # Actualizar estado del pedido
            despacho.pedido.actualizar_estado_despacho()

            messages.success(request, f'Estado del despacho {despacho.pedido.numero_pedido} actualizado a {despacho.get_estado_display()}.')
        else:
            messages.error(request, 'Error al actualizar el estado.')

    return redirect('pedidos:despacho_detail', pk=pk)


@login_required
@requiere_empresa
def despacho_delete(request, pk):
    """Eliminar despacho"""
    despacho = get_object_or_404(DespachoPedido, pk=pk)

    # Verificar permisos
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and despacho.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para eliminar este despacho.')
            return redirect('pedidos:despacho_list')
    else:
        try:
            if despacho.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para eliminar este despacho.')
                return redirect('pedidos:despacho_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')

    if request.method == 'POST':
        numero_pedido = despacho.pedido.numero_pedido
        despacho.delete()

        # Actualizar estado del pedido
        numero_pedido.actualizar_estado_despacho()

        messages.success(request, f'Despacho del pedido {numero_pedido} eliminado exitosamente.')
        return redirect('pedidos:despacho_list')

    context = {
        'despacho': despacho,
    }

    return render(request, 'pedidos/despacho_confirm_delete.html', context)


@login_required
@requiere_empresa
def despacho_imprimir_guia(request, pk):
    """Imprimir guía de despacho electrónica para pedidos"""
    despacho = get_object_or_404(DespachoPedido, pk=pk)

    # Verificar que el despacho pertenece a la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and despacho.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para ver este despacho.')
            return redirect('pedidos:despacho_list')
    else:
        try:
            if despacho.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para ver este despacho.')
                return redirect('pedidos:despacho_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('/')

    # Verificar que el despacho tenga documento DTE
    if not despacho.get_documento_asociado():
        messages.error(request, 'Este despacho no tiene documento DTE asociado')
        return redirect('pedidos:despacho_detail', pk=pk)

    dte = despacho.get_documento_asociado()

    # Redirigir a la vista de facturación electrónica que ya maneja la impresión
    # con timbre electrónico y formato correcto
    return redirect('facturacion_electronica:ver_factura_electronica', dte_id=dte.id)
'''
