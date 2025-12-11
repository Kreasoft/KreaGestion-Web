from utilidades.utils import clean_id
"""
Vistas para el CRUD de Notas de Débito
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
from django.views.decorators.cache import never_cache

from core.decorators import requiere_empresa
from .models import NotaDebito, NotaDebitoDetalle, Venta, VentaDetalle
from .forms import NotaDebitoForm, NotaDebitoDetalleFormSet
from clientes.models import Cliente
from bodegas.models import Bodega
from articulos.models import Articulo
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_service import DTEService
from facturacion_electronica.services import FolioService

@login_required
@requiere_empresa
def notadebito_list(request):
    """Lista de todas las notas de débito"""
    notas = NotaDebito.objects.filter(
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
    
    tipo_nd = request.GET.get('tipo_nd')
    if tipo_nd:
        notas = notas.filter(tipo_nd=tipo_nd)
    
    context = {
        'notas': notas,
        'stats': stats,
        'titulo': 'Notas de Débito',
        'estado_filtro': estado,
        'tipo_nd_filtro': tipo_nd,
    }
    return render(request, 'ventas/notadebito_list.html', context)


@login_required
@requiere_empresa
@never_cache
def notadebito_create(request):
    # Procesar datos del formulario incluyendo campos ocultos del AJAX
    post_data = request.POST.copy() if request.method == 'POST' else {}

    if request.method == 'POST':
        print(f"DEBUG ND: POST data keys: {list(post_data.keys())}")
        print(f"DEBUG ND: fecha_doc_afectado_hidden: {post_data.get('fecha_doc_afectado_hidden')}")
        print(f"DEBUG ND: cliente_hidden: {post_data.get('cliente_hidden')}")
        print(f"DEBUG ND: numero_doc_afectado: {post_data.get('numero_doc_afectado')}")

        # Si vienen datos del documento afectado desde AJAX, actualizar los campos correspondientes
        fecha_doc_hidden = post_data.get('fecha_doc_afectado_hidden')
        cliente_hidden = post_data.get('cliente_hidden')
        rut_cliente_hidden = post_data.get('rut_cliente_hidden')

        print(f"DEBUG ND: Datos del documento afectado - fecha: {fecha_doc_hidden}, cliente: {cliente_hidden}, rut: {rut_cliente_hidden}")

        if fecha_doc_hidden and cliente_hidden:
            # Actualizar campos que vienen del AJAX
            post_data['fecha_doc_afectado'] = fecha_doc_hidden

            # Intentar encontrar el cliente por nombre o RUT
            from django.db.models import Q
            cliente_query = Q(nombre__icontains=cliente_hidden) | Q(rut=cliente_hidden)
            cliente = Cliente.objects.filter(cliente_query, empresa=request.empresa).first()

            print(f"DEBUG ND: Cliente encontrado: {cliente}")
            if cliente:
                post_data['cliente'] = str(cliente.id)
                print(f"DEBUG ND: Cliente ID asignado: {cliente.id}")

        form = NotaDebitoForm(post_data)
        formset = NotaDebitoDetalleFormSet(post_data)

        print(f"DEBUG ND: Form data: {dict(post_data)}")
        print(f"DEBUG ND: Form is valid: {form.is_valid()}")
        print(f"DEBUG ND: Formset is valid: {formset.is_valid()}")

        if not form.is_valid():
            print(f"DEBUG ND: Form errors: {form.errors}")
        if not formset.is_valid():
            print(f"DEBUG ND: Formset errors: {formset.errors}")
            print(f"DEBUG ND: Formset non_form_errors: {formset.non_form_errors()}")

        if form.is_valid() and formset.is_valid():
            try:
                # Crear la nota de débito en memoria (sin guardar aún)
                nota = form.save(commit=False)
                nota.empresa = request.empresa
                nota.usuario_creacion = request.user
                nota.estado = 'emitida'  # Estado final desde el inicio

                if nota.bodega and nota.bodega.sucursal:
                    nota.sucursal = nota.bodega.sucursal
                else:
                    nota.sucursal = request.empresa.sucursales.first()

                # Crear items en memoria
                items = formset.save(commit=False)

                # Instanciar el servicio de DTE
                dte_service = DTEService(request.empresa)

                # El servicio se encargará de la transacción, obtener folio, guardar y generar DTE
                dte = dte_service.generar_dte_desde_nota_debito(nota, items)

                messages.success(
                    request,
                    f'Nota de Débito Electrónica N° {dte.folio} generada exitosamente.'
                )
                # Redirigir a la vista de impresión del DTE
                return redirect('facturacion_electronica:ver_notadebito_electronica', notadebito_id=nota.id)

            except Exception as e:
                messages.error(request, f'Error al emitir la Nota de Débito: {str(e)}')

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
        form = NotaDebitoForm()
        formset = NotaDebitoDetalleFormSet()

        # Prellenar campos si vienen parámetros
        venta_id = clean_id(request.GET.get('venta_id'))
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
        'titulo': 'Nueva Nota de Débito',
        'clientes': clientes,
        'bodegas': bodegas,
        'articulos_empresa': articulos_empresa,
        'today': timezone.now().date(),
    }
    return render(request, 'ventas/notadebito_form.html', context)


@login_required
@requiere_empresa
def notadebito_detail(request, pk):
    """Detalle de una nota de débito"""
    nota = get_object_or_404(
        NotaDebito.objects.select_related('cliente', 'vendedor', 'bodega', 'dte'),
        pk=pk,
        empresa=request.empresa
    )
    items = nota.items.select_related('articulo').all()
    
    context = {
        'nota': nota,
        'items': items,
        'titulo': f'Nota de Débito #{nota.numero}',
    }
    return render(request, 'ventas/notadebito_detail.html', context)


@login_required
@requiere_empresa
def notadebito_print(request, pk):
    """Versión para impresión de una nota de débito"""
    nota = get_object_or_404(
        NotaDebito.objects.select_related('cliente', 'vendedor', 'bodega', 'dte', 'empresa'),
        pk=pk,
        empresa=request.empresa
    )
    items = nota.items.select_related('articulo').all()
    
    context = {
        'nota': nota,
        'items': items,
    }
    return render(request, 'ventas/notadebito_print.html', context)


@login_required
@requiere_empresa
def notadebito_delete(request, pk):
    """Eliminar una nota de débito (solo borradores)"""
    nota = get_object_or_404(NotaDebito, pk=pk, empresa=request.empresa)
    
    if nota.estado != 'borrador':
        messages.error(request, 'Solo se pueden eliminar notas de débito en estado borrador')
        return redirect('ventas:notadebito_list')
    
    if request.method == 'POST':
        numero = nota.numero or f'ID {nota.id}'
        nota.delete()
        messages.success(request, f'Nota de Débito {numero} eliminada exitosamente')
        return redirect('ventas:notadebito_list')
    
    context = {
        'nota': nota,
        'titulo': 'Confirmar Eliminación',
    }
    return render(request, 'ventas/notadebito_confirm_delete.html', context)


@login_required
@requiere_empresa
@csrf_exempt
@require_POST
def ajax_buscar_documento_afectado_nd(request):
    """
    Busca un documento afectado por tipo y número para Nota de Débito
    Retorna: fecha, cliente, items del documento
    """
    try:
        tipo_doc = request.POST.get('tipo_doc')
        numero_doc = request.POST.get('numero_doc')
        
        print(f"DEBUG ND: Buscando documento tipo {tipo_doc}, número {numero_doc}")
        
        # Buscar primero en DTEs
        dte = DocumentoTributarioElectronico.objects.filter(
            empresa=request.empresa,
            tipo_dte=tipo_doc,
            folio=numero_doc
        ).select_related('venta').first()
        
        if dte:
            # Si el DTE tiene venta asociada, obtener items de ahí
            if dte.venta:
                venta = dte.venta
                items_data = []
                for detalle in venta.detalles.select_related('articulo').all():
                    items_data.append({
                        'articulo_id': detalle.articulo.id,
                        'codigo': detalle.articulo.codigo or str(detalle.articulo.id),
                        'descripcion': detalle.articulo.nombre,
                        'cantidad': float(detalle.cantidad),
                        'precio_unitario': float(detalle.precio_unitario),
                        'descuento': float(detalle.descuento) if detalle.descuento else 0.0,
                    })
                
                return JsonResponse({
                    'success': True,
                    'fecha': dte.fecha_emision.strftime('%Y-%m-%d'),
                    'cliente': dte.razon_social_receptor,
                    'rut_cliente': dte.rut_receptor,
                    'items': items_data,
                })
            else:
                # DTE sin venta, devolver datos básicos del DTE
                return JsonResponse({
                    'success': True,
                    'fecha': dte.fecha_emision.strftime('%Y-%m-%d'),
                    'cliente': dte.razon_social_receptor,
                    'rut_cliente': dte.rut_receptor,
                    'items': [],
                })
        
        # Si no se encuentra DTE, buscar en ventas normales
        venta = Venta.objects.filter(
            empresa=request.empresa,
            numero_venta=numero_doc,
            estado='confirmada'
        ).select_related('cliente').first()
        
        if venta:
            items_data = []
            for detalle in venta.detalles.select_related('articulo').all():
                items_data.append({
                    'articulo_id': detalle.articulo.id,
                    'codigo': detalle.articulo.codigo or str(detalle.articulo.id),
                    'descripcion': detalle.articulo.nombre,
                    'cantidad': float(detalle.cantidad),
                    'precio_unitario': float(detalle.precio_unitario),
                    'descuento': float(detalle.descuento) if detalle.descuento else 0.0,
                })
            
            return JsonResponse({
                'success': True,
                'fecha': venta.fecha.strftime('%Y-%m-%d'),
                'cliente': venta.cliente.nombre if venta.cliente else '',
                'rut_cliente': venta.cliente.rut if venta.cliente else '',
                'items': items_data,
            })
        
        return JsonResponse({
            'success': False,
            'message': 'Documento no encontrado'
        })
        
    except Exception as e:
        print(f"ERROR ND en ajax_buscar_documento_afectado: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error al buscar documento: {str(e)}'
        })


@login_required
@requiere_empresa
def notadebito_enviar_sii(request, pk):
    """Envía una Nota de Débito ya emitida al SII"""
    nota = get_object_or_404(NotaDebito, pk=pk, empresa=request.empresa)
    
    # Verificar que tenga DTE generado
    if not nota.dte:
        messages.error(request, 'Esta Nota de Débito no tiene DTE generado')
        return redirect('ventas:notadebito_detail', pk=nota.pk)
    
    # Verificar estado
    if nota.estado not in ['emitida', 'enviada_sii']:
        messages.error(request, 'La Nota de Débito debe estar emitida para enviarla al SII')
        return redirect('ventas:notadebito_detail', pk=nota.pk)
    
    try:
        # Inicializar servicio DTE
        dte_service = DTEService(request.empresa)
        
        # Enviar al SII
        resultado = dte_service.enviar_dte_al_sii(nota.dte)
        
        if resultado and resultado.get('track_id'):
            nota.estado = 'enviada_sii'
            nota.save(update_fields=['estado'])
            messages.success(
                request,
                f'Nota de Débito enviada al SII. Track ID: {resultado.get("track_id")}'
            )
        else:
            messages.warning(request, 'Nota de Débito enviada pero sin Track ID en respuesta')
        
    except Exception as e:
        messages.error(request, f'Error al enviar Nota de Débito al SII: {str(e)}')
    
    return redirect('ventas:notadebito_detail', pk=nota.pk)












