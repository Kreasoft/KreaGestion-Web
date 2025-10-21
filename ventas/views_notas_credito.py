"""
Vistas para el CRUD de Notas de Crédito
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from decimal import Decimal
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from empresas.decorators import requiere_empresa
from .models import NotaCredito, NotaCreditoDetalle, Venta, VentaDetalle
from .forms import NotaCreditoForm, NotaCreditoDetalleFormSet
from clientes.models import Cliente
from bodegas.models import Bodega
from articulos.models import Articulo
from facturacion_electronica.models import DocumentoTributarioElectronico


@login_required
@requiere_empresa
def notacredito_list(request):
    """Lista de todas las notas de crédito"""
    notas = NotaCredito.objects.filter(
        empresa=request.empresa
    ).select_related(
        'cliente', 'vendedor', 'bodega', 'usuario_creacion'
    ).order_by('-fecha', '-numero')
    
    # Calcular estadísticas antes de filtrar
    stats = {
        'total': notas.count(),
        'borradores': notas.filter(estado='borrador').count(),
        'emitidas': notas.filter(estado='emitida').count(),
        'aceptadas_sii': notas.filter(estado='aceptada_sii').count(),
    }
    
    # Filtros opcionales
    estado = request.GET.get('estado')
    if estado:
        notas = notas.filter(estado=estado)
    
    tipo_nc = request.GET.get('tipo_nc')
    if tipo_nc:
        notas = notas.filter(tipo_nc=tipo_nc)
    
    context = {
        'notas': notas,
        'stats': stats,
        'titulo': 'Notas de Crédito',
        'estado_filtro': estado,
        'tipo_nc_filtro': tipo_nc,
    }
    return render(request, 'ventas/notacredito_list.html', context)


@login_required
@requiere_empresa
def notacredito_create(request):
    """Crear nueva nota de crédito"""
    # Procesar datos del formulario incluyendo campos ocultos del AJAX
    post_data = request.POST.copy() if request.method == 'POST' else {}

    if request.method == 'POST':
        print(f"DEBUG: POST data keys: {list(post_data.keys())}")
        print(f"DEBUG: fecha_doc_afectado_hidden: {post_data.get('fecha_doc_afectado_hidden')}")
        print(f"DEBUG: cliente_hidden: {post_data.get('cliente_hidden')}")
        print(f"DEBUG: numero_doc_afectado: {post_data.get('numero_doc_afectado')}")

        # Si vienen datos del documento afectado desde AJAX, actualizar los campos correspondientes
        fecha_doc_hidden = post_data.get('fecha_doc_afectado_hidden')
        cliente_hidden = post_data.get('cliente_hidden')
        rut_cliente_hidden = post_data.get('rut_cliente_hidden')

        print(f"DEBUG: Datos del documento afectado - fecha: {fecha_doc_hidden}, cliente: {cliente_hidden}, rut: {rut_cliente_hidden}")

        if fecha_doc_hidden and cliente_hidden:
            # Actualizar campos que vienen del AJAX
            post_data['fecha_doc_afectado'] = fecha_doc_hidden

            # Intentar encontrar el cliente por nombre o RUT
            from django.db.models import Q
            cliente_query = Q(nombre__icontains=cliente_hidden) | Q(rut=cliente_hidden)
            cliente = Cliente.objects.filter(cliente_query, empresa=request.empresa).first()

            print(f"DEBUG: Cliente encontrado: {cliente}")
            if cliente:
                post_data['cliente'] = str(cliente.id)
                print(f"DEBUG: Cliente ID asignado: {cliente.id}")

        form = NotaCreditoForm(post_data)
        formset = NotaCreditoDetalleFormSet(post_data)

        print(f"DEBUG: Form data: {dict(post_data)}")
        print(f"DEBUG: Form is valid: {form.is_valid()}")
        print(f"DEBUG: Formset is valid: {formset.is_valid()}")

        if not form.is_valid():
            print(f"DEBUG: Form errors: {form.errors}")
        if not formset.is_valid():
            print(f"DEBUG: Formset errors: {formset.errors}")
            print(f"DEBUG: Formset non_form_errors: {formset.non_form_errors()}")

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardar nota de crédito
                    nota = form.save(commit=False)
                    nota.empresa = request.empresa
                    # Derivar la sucursal desde la bodega seleccionada en el formulario
                    if nota.bodega and nota.bodega.sucursal:
                        nota.sucursal = nota.bodega.sucursal
                    else:
                        # Fallback: primera sucursal de la empresa si no hay bodega o la bodega no tiene sucursal
                        nota.sucursal = request.empresa.sucursales.first()
                    nota.usuario_creacion = request.user

                    print(f"DEBUG: Datos del formulario - cliente: {post_data.get('cliente')}, tipo_doc_afectado: {post_data.get('tipo_doc_afectado')}")
                    print(f"DEBUG: Nota antes de save - cliente: {nota.cliente}, tipo_doc_afectado: {nota.tipo_doc_afectado}")

                    # Verificar que todos los campos requeridos estén presentes
                    if not nota.cliente:
                        print(f"ERROR: Cliente no encontrado - cliente field: {nota.cliente}")
                        messages.error(request, 'Cliente no encontrado. Selecciona un cliente válido.')
                        return render(request, 'ventas/notacredito_form.html', context)

                    if not nota.tipo_doc_afectado:
                        print(f"ERROR: Tipo de documento afectado no especificado - tipo_doc_afectado field: {nota.tipo_doc_afectado}")
                        messages.error(request, 'Tipo de documento afectado es requerido.')
                        return render(request, 'ventas/notacredito_form.html', context)

                    if not nota.fecha_doc_afectado:
                        print(f"ERROR: Fecha del documento afectado no especificada - fecha_doc_afectado field: {nota.fecha_doc_afectado}")
                        messages.error(request, 'Fecha del documento afectado es requerida.')
                        return render(request, 'ventas/notacredito_form.html', context)

                    nota.save()

                    # Guardar detalles
                    formset.instance = nota
                    items = formset.save(commit=False)

                    for item in items:
                        # Completar datos del artículo si no están
                        if not item.codigo:
                            item.codigo = item.articulo.codigo
                        if not item.descripcion:
                            item.descripcion = item.articulo.nombre
                        item.save()

                    # Calcular totales
                    nota.calcular_totales()

                    messages.success(request, f'Nota de Crédito N° {nota.numero} creada exitosamente.')
                    return redirect('ventas:notacredito_detail', pk=nota.pk)

            except Exception as e:
                messages.error(request, f'Error al crear la nota de crédito: {str(e)}')
        else:
            # Formulario o formset inválido
            if not form.is_valid():
                error_msg = 'El formulario principal tiene errores. Por favor, revise los campos marcados.'
                for field, errors in form.errors.items():
                    error_msg += f" {field}: {', '.join(errors)}"
                messages.error(request, error_msg)
            
            if not formset.is_valid():
                error_msg = 'Hay errores en los items. Por favor, revise los detalles.'
                for form_errors in formset.errors:
                    for field, errors in form_errors.items():
                        error_msg += f" {field}: {', '.join(errors)}"
                messages.error(request, error_msg)

    else:
        # GET request - crear formulario básico
        form = NotaCreditoForm()
        formset = NotaCreditoDetalleFormSet()

        # Prellenar campos si vienen parámetros
        venta_id = request.GET.get('venta_id')
        if venta_id:
            try:
                venta = Venta.objects.get(pk=venta_id, empresa=request.empresa)
                form.initial = {
                    'cliente': venta.cliente,
                    'vendedor': venta.vendedor,
                    'bodega': venta.bodega,
                }
            except Venta.DoesNotExist:
                pass

    # Obtener listas para los selects (tanto para GET como POST)
    clientes = Cliente.objects.filter(empresa=request.empresa)
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True)
    articulos_empresa = Articulo.objects.filter(empresa=request.empresa, activo=True)

    context = {
        'form': form,
        'formset': formset,
        'titulo': 'Nueva Nota de Crédito',
        'clientes': clientes,
        'bodegas': bodegas,
        'articulos_empresa': articulos_empresa,
        'today': timezone.now().date(),
    }
    return render(request, 'ventas/notacredito_form.html', context)


@login_required
@requiere_empresa
@csrf_exempt
@require_POST
def ajax_buscar_documento_afectado(request):
    """
    Busca un documento afectado por tipo y número
    Retorna: fecha, cliente, items del documento
    """
    tipo_doc = request.POST.get('tipo_doc_afectado')
    numero_doc = request.POST.get('numero_doc_afectado')

    if not tipo_doc or not numero_doc:
        return JsonResponse({
            'success': False,
            'message': 'Tipo de documento y número son requeridos'
        })

    try:
        # Valores base
        fecha = None
        cliente = ''
        rut_cliente = ''
        cliente_id = None
        bodega_id = None
        bodega_nombre = ''
        vendedor_id = None
        vendedor_nombre = ''
        venta_id = None
        monto_total = Decimal('0')
        documento_encontrado = False      
        items_data = []  # <-- AGREGAR ESTA LÍNEA
 
        # Mapeo de códigos SII a nombres de tipo_documento
        TIPO_DOC_MAP = {
            '33': 'factura',
            '39': 'boleta',
            '52': 'guia',
            '61': 'nota_credito'
        }

        # Buscar documento según el tipo
        if tipo_doc in ['33', '39', '52']:  # Documentos electrónicos
            try:
                documento = DocumentoTributarioElectronico.objects.get(
                    empresa=request.empresa,
                    tipo_dte=tipo_doc,
                    folio=numero_doc
                )
                documento_encontrado = True
            except DocumentoTributarioElectronico.DoesNotExist:
                # Si no existe DTE, buscar en Venta
                try:
                    tipo_doc_nombre = TIPO_DOC_MAP.get(tipo_doc, tipo_doc)
                    documento = Venta.objects.get(
                        empresa=request.empresa,
                        numero_venta=numero_doc,
                        tipo_documento=tipo_doc_nombre
                    )
                    documento_encontrado = True
                    # Procesar como venta
                    fecha = documento.fecha
                    venta_id = documento.id
                    cliente_obj = documento.cliente
                    cliente = cliente_obj.nombre if cliente_obj else ''
                    rut_cliente = cliente_obj.rut if cliente_obj else ''
                    cliente_id = cliente_obj.id if cliente_obj else None
                    monto_total = Decimal(documento.total or 0)

                    if documento.vendedor:
                        vendedor_id = documento.vendedor.id
                        vendedor_nombre = documento.vendedor.nombre

                    # Obtener bodega
                    bodega_obj = None
                    if hasattr(documento, 'bodega') and documento.bodega:
                        bodega_obj = documento.bodega
                    elif documento.sucursal:
                        bodega_obj = Bodega.objects.filter(empresa=request.empresa, sucursal=documento.sucursal, activa=True).first()

                    if bodega_obj:
                        bodega_id = bodega_obj.id
                        bodega_nombre = str(bodega_obj)
                    else:
                        # Fallback a la primera bodega activa de la empresa
                        bodega_fallback = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('id').first()
                        if bodega_fallback:
                            bodega_id = bodega_fallback.id
                            bodega_nombre = str(bodega_fallback)

                    # Items desde la venta (fallback)
                    items = VentaDetalle.objects.filter(venta=documento).select_related('articulo')
                    items_data = [{
                        'articulo_id': it.articulo.id,
                        'codigo': it.articulo.codigo,
                        'nombre': it.articulo.nombre,
                        'cantidad': float(it.cantidad),
                        'precio_unitario': float(it.precio_unitario),
                        'descuento': 0,
                    } for it in items]
                except Venta.DoesNotExist:
                    pass

            if documento_encontrado and isinstance(documento, DocumentoTributarioElectronico):

               fecha = documento.fecha_emision
               cliente = documento.razon_social_receptor
               rut_cliente = documento.rut_receptor
               monto_total = Decimal(documento.monto_total or 0)

               venta_relacionada = documento.venta
               if venta_relacionada:
                   venta_id = venta_relacionada.id
                   if venta_relacionada.cliente:
                       cliente_id = venta_relacionada.cliente.id
                   # Obtener bodega desde la venta relacionada
                   bodega_obj = None
                   if hasattr(venta_relacionada, 'bodega') and venta_relacionada.bodega:
                       bodega_obj = venta_relacionada.bodega
                   elif venta_relacionada.sucursal:
                       bodega_obj = Bodega.objects.filter(empresa=request.empresa, sucursal=venta_relacionada.sucursal, activa=True).first()

                   if bodega_obj:
                       bodega_id = bodega_obj.id
                       bodega_nombre = str(bodega_obj)
                   else:
                       # Fallback a la primera bodega activa de la empresa
                       bodega_fallback = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('id').first()
                       if bodega_fallback:
                               bodega_id = bodega_fallback.id
                               bodega_nombre = str(bodega_fallback)
                   if venta_relacionada.vendedor:
                       vendedor_id = venta_relacionada.vendedor.id
                       vendedor_nombre = venta_relacionada.vendedor.nombre

               items_data = cargar_items_documento_afectado(tipo_doc, numero_doc, request.empresa)

        elif tipo_doc == '46':  # Factura de compra electrónica
            from compras.models import DocumentoCompra
            documento = DocumentoCompra.objects.get(
                empresa=request.empresa,
                numero_documento=numero_doc
            )

            fecha = documento.fecha_emision
            cliente = documento.proveedor.nombre if documento.proveedor else ''
            rut_cliente = documento.proveedor.rut if documento.proveedor else ''
            monto_total = Decimal(documento.total or 0)

            items_data = []

        else:
            documento = Venta.objects.get(
                empresa=request.empresa,
                numero_venta=numero_doc,
                tipo_documento=tipo_doc
            )

            fecha = documento.fecha
            venta_id = documento.id
            cliente_obj = documento.cliente
            cliente = cliente_obj.nombre if cliente_obj else ''
            rut_cliente = cliente_obj.rut if cliente_obj else ''
            cliente_id = cliente_obj.id if cliente_obj else None
            monto_total = Decimal(documento.total or 0)

            # Derivar bodega desde la sucursal de la venta
            if documento.sucursal:
                bodega_obj = Bodega.objects.filter(
                    empresa=request.empresa,
                    sucursal=documento.sucursal,
                    activa=True
                ).order_by('id').first()
                if bodega_obj:
                    bodega_id = bodega_obj.id
                    bodega_nombre = str(bodega_obj)
                else:
                    bodega_fallback = Bodega.objects.filter(
                        empresa=request.empresa,
                        activa=True
                    ).order_by('id').first()
                    if bodega_fallback:
                        bodega_id = bodega_fallback.id
                        bodega_nombre = str(bodega_fallback)
            if documento.vendedor:
                vendedor_id = documento.vendedor.id
                vendedor_nombre = documento.vendedor.nombre

            items_data = cargar_items_documento_afectado(tipo_doc, numero_doc, request.empresa)

        return JsonResponse({
            'success': True,
            'fecha': fecha.strftime('%Y-%m-%d') if fecha else '',
            'cliente': cliente,
            'cliente_id': cliente_id,
            'rut_cliente': rut_cliente,
            'venta_id': venta_id,
            'bodega_id': bodega_id,
            'bodega_nombre': bodega_nombre,
            'vendedor_id': vendedor_id,
            'vendedor_nombre': vendedor_nombre,
            'monto_total': float(monto_total) if monto_total is not None else 0,
            'items': items_data
        })

    except DocumentoTributarioElectronico.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Documento electrónico no encontrado'
        })
    except Venta.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Venta no encontrada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al buscar documento: {str(e)}'
        })


def cargar_items_documento_afectado(tipo_doc, numero_doc, empresa):
    """
    Función auxiliar para cargar items de un documento afectado
    """
    try:
        if tipo_doc in ['33', '39', '52']:  # Documentos electrónicos
            # Buscar en DTEs
            documento = DocumentoTributarioElectronico.objects.get(
                empresa=empresa,
                tipo_dte=tipo_doc,
                folio=numero_doc
            )

            # Obtener items de la venta relacionada
            venta = documento.venta
            if venta:
                items = VentaDetalle.objects.filter(venta=venta).select_related('articulo')
                items_data = []
                for item in items:
                    items_data.append({
                        'articulo_id': item.articulo.id,
                        'codigo': item.articulo.codigo,
                        'nombre': item.articulo.nombre,
                        'cantidad': float(item.cantidad),
                        'precio_unitario': float(item.precio_unitario),
                        'descuento': 0,
                    })
                return items_data

        elif tipo_doc == '46':  # Factura de compra electrónica
            # Buscar en documentos de compra (si existe modelo)
            from compras.models import DocumentoCompra
            documento = DocumentoCompra.objects.get(
                empresa=empresa,
                numero_documento=numero_doc
            )

            # Items de compra - implementar cuando exista el modelo
            return []

        else:
            # Buscar en ventas regulares del POS
            documento = Venta.objects.get(
                empresa=empresa,
                numero_venta=numero_doc,
                tipo_documento=tipo_doc
            )

            # Items de la venta
            items = VentaDetalle.objects.filter(venta=documento).select_related('articulo')
            items_data = []
            for item in items:
                items_data.append({
                    'articulo_id': item.articulo.id,
                    'codigo': item.articulo.codigo,
                    'nombre': item.articulo.nombre,
                    'cantidad': float(item.cantidad),
                    'precio_unitario': float(item.precio_unitario),
                    'descuento': 0,
                })
            return items_data

    except DocumentoTributarioElectronico.DoesNotExist:
        # Fallback a Venta si no existe DTE
        TIPO_DOC_MAP = {'33': 'factura', '39': 'boleta', '52': 'guia'}
        try:
            tipo_nombre = TIPO_DOC_MAP.get(tipo_doc, tipo_doc)
            venta = Venta.objects.get(
                empresa=empresa,
                numero_venta=numero_doc,
                tipo_documento=tipo_nombre
            )
            items = VentaDetalle.objects.filter(venta=venta).select_related('articulo')
            return [{
                'articulo_id': it.articulo.id,
                'codigo': it.articulo.codigo,
                'nombre': it.articulo.nombre,
                'cantidad': float(it.cantidad),
                'precio_unitario': float(it.precio_unitario),
                'descuento': 0,
            } for it in items]
        except Venta.DoesNotExist:
            return []
        except Exception:
            return []
    except Exception:
        return []


@login_required
@requiere_empresa
def notacredito_update(request, pk):
    """Editar nota de crédito existente"""
    nota = get_object_or_404(NotaCredito, pk=pk, empresa=request.empresa)
    
    # Solo se puede editar si está en borrador
    if nota.estado != 'borrador':
        messages.warning(request, 'Solo se pueden editar notas de crédito en estado borrador.')
        return redirect('ventas:notacredito_detail', pk=nota.pk)
    
    if request.method == 'POST':
        form = NotaCreditoForm(request.POST, instance=nota)
        formset = NotaCreditoDetalleFormSet(request.POST, instance=nota)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardar nota de crédito
                    nota = form.save()
                    
                    # Guardar detalles
                    items = formset.save(commit=False)
                    
                    for item in items:
                        # Completar datos del artículo si no están
                        if not item.codigo:
                            item.codigo = item.articulo.codigo
                        if not item.descripcion:
                            item.descripcion = item.articulo.nombre
                        item.save()
                    
                    # Eliminar items marcados para borrar
                    for item in formset.deleted_objects:
                        item.delete()
                    
                    # Calcular totales
                    nota.calcular_totales()
                    
                    messages.success(request, f'Nota de Crédito N° {nota.numero} actualizada exitosamente.')
                    return redirect('ventas:notacredito_detail', pk=nota.pk)
                    
            except Exception as e:
                messages.error(request, f'Error al actualizar la nota de crédito: {str(e)}')
    else:
        form = NotaCreditoForm(instance=nota)
        formset = NotaCreditoDetalleFormSet(instance=nota)
    
    # Obtener listas para los selects
    clientes = Cliente.objects.filter(empresa=request.empresa)
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True)
    articulos_empresa = Articulo.objects.filter(empresa=request.empresa, activo=True)

    context = {
        'form': form,
        'formset': formset,
        'nota': nota,
        'titulo': f'Editar NC {nota.numero}',
        'clientes': clientes,
        'bodegas': bodegas,
        'articulos_empresa': articulos_empresa,
    }
    return render(request, 'ventas/notacredito_form.html', context)


@login_required
@requiere_empresa
def notacredito_detail(request, pk):
    """Ver detalle de nota de crédito"""
    nota = get_object_or_404(
        NotaCredito.objects.select_related(
            'cliente', 'vendedor', 'bodega', 'usuario_creacion', 'dte'
        ).prefetch_related('items__articulo'),
        pk=pk,
        empresa=request.empresa
    )
    
    context = {
        'nota': nota,
        'titulo': f'Nota de Crédito N° {nota.numero}',
    }
    return render(request, 'ventas/notacredito_detail.html', context)


@login_required
@requiere_empresa
def notacredito_delete(request, pk):
    """Eliminar nota de crédito"""
    nota = get_object_or_404(NotaCredito, pk=pk, empresa=request.empresa)
    
    # Solo se puede eliminar si está en borrador
    if nota.estado != 'borrador':
        messages.warning(request, 'Solo se pueden eliminar notas de crédito en estado borrador.')
        return redirect('ventas:notacredito_detail', pk=nota.pk)
    
    if request.method == 'POST':
        numero = nota.numero
        nota.delete()
        messages.success(request, f'Nota de Crédito N° {numero} eliminada exitosamente.')
        return redirect('ventas:notacredito_list')
    
    context = {
        'nota': nota,
        'titulo': f'Eliminar NC {nota.numero}',
    }
    return render(request, 'ventas/notacredito_confirm_delete.html', context)


@login_required
@requiere_empresa
def notacredito_emitir(request, pk):
    """Emitir nota de crédito (cambiar estado de borrador a emitida)"""
    nota = get_object_or_404(NotaCredito, pk=pk, empresa=request.empresa)
    
    if nota.estado != 'borrador':
        messages.warning(request, 'Esta nota de crédito ya ha sido emitida.')
        return redirect('ventas:notacredito_detail', pk=nota.pk)
    
    if request.method == 'POST':
        nota.estado = 'emitida'
        nota.save()
        messages.success(request, f'Nota de Crédito N° {nota.numero} emitida exitosamente.')
        return redirect('ventas:notacredito_detail', pk=nota.pk)
    
    context = {
        'nota': nota,
        'titulo': f'Emitir NC {nota.numero}',
    }
    return render(request, 'ventas/notacredito_confirm_emitir.html', context)


@login_required
@requiere_empresa
def ajax_cargar_items_venta(request):
    """
    Vista AJAX para cargar los items de una venta
    Se usa cuando tipo_nc = 'ANULA'
    """
    venta_id = request.GET.get('venta_id')
    tipo_doc = request.GET.get('tipo_doc')
    numero_doc = request.GET.get('numero_doc')
    
    try:
        # Buscar la venta
        venta = Venta.objects.get(
            empresa=request.empresa,
            numero_venta=numero_doc,
            tipo_documento=tipo_doc
        )
        
        # Obtener los items
        items = []
        for detalle in venta.ventadetalle_set.all():
            items.append({
                'articulo_id': detalle.articulo.id,
                'codigo': detalle.articulo.codigo,
                'descripcion': detalle.articulo.nombre,
                'cantidad': str(detalle.cantidad),
                'precio_unitario': str(detalle.precio_unitario),
                'descuento': str(detalle.descuento) if hasattr(detalle, 'descuento') else '0.00',
                'total': str(detalle.precio_total),
            })
        
        return JsonResponse({
            'success': True,
            'items': items,
            'cliente_id': venta.cliente.id,
            'cliente_nombre': venta.cliente.nombre,
        })
        
    except Venta.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'No se encontró un documento con esos datos'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@requiere_empresa
def notacredito_delete(request, pk):
    """Eliminar nota de crédito"""
    nota = get_object_or_404(NotaCredito, pk=pk, empresa=request.empresa)
    
    if nota.estado != 'borrador':
        messages.warning(request, 'Solo se pueden eliminar notas de crédito en estado borrador.')
        return redirect('ventas:notacredito_detail', pk=nota.pk)
    
    if request.method == 'POST':
        numero = nota.numero
        nota.delete()
        messages.success(request, f'Nota de Crédito N° {numero} eliminada exitosamente.')
        return redirect('ventas:notacredito_list')
    
    context = {
        'nota': nota,
        'titulo': f'Eliminar NC {nota.numero}',
    }
    return render(request, 'ventas/notacredito_confirm_delete.html', context)


@login_required
@requiere_empresa
def notacredito_emitir(request, pk):
    """Emitir nota de crédito (cambiar estado de borrador a emitida)"""
    nota = get_object_or_404(NotaCredito, pk=pk, empresa=request.empresa)
    
    if nota.estado != 'borrador':
        messages.warning(request, 'Esta nota de crédito ya ha sido emitida.')
        return redirect('ventas:notacredito_detail', pk=nota.pk)
    
    if request.method == 'POST':
        nota.estado = 'emitida'
        nota.save()
        messages.success(request, f'Nota de Crédito N° {nota.numero} emitida exitosamente.')
        return redirect('ventas:notacredito_detail', pk=nota.pk)
    
    context = {
        'nota': nota,
        'titulo': f'Emitir NC {nota.numero}',
    }
    return render(request, 'ventas/notacredito_confirm_emitir.html', context)


from django.http import HttpResponse
from django.template import Template, Context

@login_required
@requiere_empresa
def notacredito_print(request, pk):
    """Vista para imprimir una Nota de Crédito"""
    nota = get_object_or_404(NotaCredito, pk=pk, empresa=request.empresa)
    detalles = nota.detalles.all()

    # HTML incrustado como workaround
    html_template_string = """ 
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Nota de Crédito {{ nota.numero }}</title>
        <style>
            @page { size: A4; margin: 1cm; }
            body { font-family: 'Arial', sans-serif; font-size: 8pt; line-height: 1.1; color: #000; }
            .factura-container { max-width: 800px; margin: 0 auto; }
            .header-section { display: table; width: 100%; margin-bottom: 8px; }
            .header-left { display: table-cell; width: 55%; vertical-align: top; }
            .header-right { display: table-cell; width: 45%; vertical-align: top; }
            .document-box { border: 3px solid #c00; border-radius: 8px; padding: 8px 6px; text-align: center; }
            .document-rut { font-size: 10pt; font-weight: bold; color: #c00; }
            .document-type { font-size: 11pt; font-weight: bold; color: #c00; }
            .document-folio { font-size: 12pt; font-weight: bold; color: #c00; }
            .document-sii { font-size: 8pt; font-weight: bold; color: #c00; }
            .company-name { font-size: 9pt; font-weight: bold; }
            .company-info { font-size: 7pt; }
            .fecha-emision { text-align: right; font-size: 7pt; margin-bottom: 6px; }
            .receptor-section, .referencia-section { border: 1px solid #ddd; border-radius: 6px; padding: 6px; margin-bottom: 8px; background: #f9f9f9; }
            .receptor-grid, .referencia-grid { display: table; width: 100%; font-size: 7pt; }
            .receptor-row, .referencia-row { display: table-row; }
            .receptor-cell, .referencia-cell { display: table-cell; padding: 1px 3px; width: 25%; }
            .receptor-label, .referencia-label { font-weight: bold; background: #e0e0e0; padding: 1px 3px; border-radius: 2px; }
            .detalle-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 7pt; border: 1px solid #ddd; }
            .detalle-table thead { background: #d0d0d0; }
            .detalle-table th { border-right: 1px solid #ddd; padding: 3px 2px; text-align: center; font-size: 6pt; }
            .detalle-table td { border-right: 1px solid #eee; padding: 2px; vertical-align: top; }
            .footer-section { display: table; width: 100%; }
            .footer-left { display: table-cell; width: 45%; vertical-align: top; padding-right: 6px; }
            .footer-right { display: table-cell; width: 55%; vertical-align: top; }
            .timbre-box { border: 1px solid #ddd; border-radius: 6px; padding: 6px; text-align: center; margin-bottom: 6px; }
            .totales-box { border: 1px solid #ddd; border-radius: 6px; background: #f9f9f9; }
            .totales-header { background: #d0d0d0; padding: 4px; text-align: center; font-weight: bold; font-size: 8pt; border-bottom: 1px solid #ddd; }
            .totales-content { padding: 4px 6px; }
            .total-row { display: flex; justify-content: space-between; padding: 1px 0; font-size: 7pt; border-bottom: 1px solid #e0e0e0; }
            .total-row:last-child { font-weight: bold; font-size: 8pt; }
            .total-label { font-weight: bold; }
            .no-print { display: none; }
        </style>
    </head>
    <body>
        <div class="factura-container">
            <div class="header-section">
                <div class="header-left">
                    <div class="company-name">{{ nota.empresa.nombre }}</div>
                    <div class="company-info">
                        <strong>Casa Matriz:</strong> {{ nota.empresa.get_direccion_dte|default:'' }}<br>
                        Fono: {{ nota.empresa.telefono|default:"" }}
                    </div>
                </div>
                <div class="header-right">
                    <div class="document-box">
                        <div class="document-rut">RUT: {{ nota.empresa.rut }}</div>
                        <div class="document-type">NOTA DE CRÉDITO<br>ELECTRÓNICA</div>
                        <div class="document-folio">N° {{ nota.numero }}</div>
                        <div class="document-sii">SII - {{ nota.empresa.oficina_sii|default:""|upper }}</div>
                    </div>
                </div>
            </div>
            <div class="fecha-emision"><strong>Fecha:</strong> {{ nota.fecha|date:"d/m/Y" }}</div>
            <div class="receptor-section">
                <div class="receptor-grid">
                    <div class="receptor-row">
                        <div class="receptor-cell"><span class="receptor-label">Señor(es):</span></div>
                        <div class="receptor-cell" colspan="3"><strong>{{ nota.cliente.nombre }}</strong></div>
                    </div>
                    <div class="receptor-row">
                        <div class="receptor-cell"><span class="receptor-label">Dirección:</span></div>
                        <div class="receptor-cell">{{ nota.cliente.direccion|default:"-" }}</div>
                        <div class="receptor-cell"><span class="receptor-label">RUT:</span></div>
                        <div class="receptor-cell">{{ nota.cliente.rut|default:"-" }}</div>
                    </div>
                </div>
            </div>
            <div class="referencia-section">
                <div class="referencia-grid">
                    <div class="referencia-row">
                        <div class="referencia-cell"><span class="referencia-label">Referencia:</span></div>
                        <div class="referencia-cell" colspan="3">Anula Doc. {{ nota.get_tipo_doc_afectado_display }} N° {{ nota.numero_doc_afectado }}</div>
                    </div>
                    <div class="referencia-row">
                        <div class="referencia-cell"><span class="referencia-label">Fecha Doc:</span></div>
                        <div class="referencia-cell">{{ nota.fecha_doc_afectado|date:"d/m/Y" }}</div>
                        <div class="referencia-cell"><span class="referencia-label">Motivo:</span></div>
                        <div class="referencia-cell">{{ nota.motivo|default:"Anulación de documento." }}</div>
                    </div>
                </div>
            </div>
            <table class="detalle-table">
                <thead><tr><th>Código</th><th>Detalle</th><th>Cant.</th><th>Precio</th><th>Total</th></tr></thead>
                <tbody>
                    {% for detalle in detalles %}
                    <tr>
                        <td>{{ detalle.codigo }}</td>
                        <td>{{ detalle.descripcion }}</td>
                        <td>{{ detalle.cantidad|floatformat:0 }}</td>
                        <td>${{ detalle.precio_unitario|floatformat:0 }}</td>
                        <td>${{ detalle.total_linea|floatformat:0 }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <div class="footer-section">
                <div class="footer-left">
                    <div class="timbre-box">Timbre Electrónico SII (simulado)</div>
                </div>
                <div class="footer-right">
                    <div class="totales-box">
                        <div class="totales-header">TOTALES</div>
                        <div class="totales-content">
                            <div class="total-row"><span class="total-label">Neto</span><span>${{ nota.neto|floatformat:0 }}</span></div>
                            <div class="total-row"><span class="total-label">IVA (19%)</span><span>${{ nota.iva|floatformat:0 }}</span></div>
                            <div class="total-row"><span class="total-label">TOTAL</span><span>${{ nota.total|floatformat:0 }}</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    template = Template(html_template_string)
    context = Context({
        'nota': nota,
        'detalles': detalles,
    })
    html_content = template.render(context)

    return HttpResponse(html_content)
