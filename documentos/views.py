from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import DocumentoCompra, ItemDocumentoCompra, HistorialPagoDocumento
from .forms import (
    DocumentoCompraForm, ItemDocumentoCompraFormSet, HistorialPagoDocumentoForm, 
    BusquedaDocumentoForm
)

from empresas.models import Empresa
from articulos.models import Articulo
from usuarios.decorators import requiere_empresa


@login_required
@requiere_empresa
def documento_compra_list(request):
    """Lista de documentos de compra"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa = Empresa.objects.first()
        if not empresa:
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('dashboard')
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Formulario de búsqueda
    search_form = BusquedaDocumentoForm(request.GET, empresa=empresa)
    
    # Obtener documentos de compra
    documentos = DocumentoCompra.objects.filter(empresa=empresa)
    
    # Aplicar filtros
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        tipo_documento = search_form.cleaned_data.get('tipo_documento')
        estado_documento = search_form.cleaned_data.get('estado_documento')
        estado_pago = search_form.cleaned_data.get('estado_pago')
        fecha_desde = search_form.cleaned_data.get('fecha_desde')
        fecha_hasta = search_form.cleaned_data.get('fecha_hasta')
        proveedor = search_form.cleaned_data.get('proveedor')
        
        if search:
            documentos = documentos.filter(
                Q(numero_documento__icontains=search) |
                Q(proveedor__nombre__icontains=search) |
                Q(rut_proveedor__icontains=search) |
                Q(observaciones__icontains=search)
            ).distinct()
        
        if tipo_documento:
            documentos = documentos.filter(tipo_documento=tipo_documento)
        
        if estado_documento:
            documentos = documentos.filter(estado_documento=estado_documento)
        
        if estado_pago:
            documentos = documentos.filter(estado_pago=estado_pago)
        
        if fecha_desde:
            documentos = documentos.filter(fecha_emision__gte=fecha_desde)
        
        if fecha_hasta:
            documentos = documentos.filter(fecha_emision__lte=fecha_hasta)
        
        if proveedor:
            documentos = documentos.filter(proveedor=proveedor)
    
    # Estadísticas
    stats = {
        'total_documentos': documentos.count(),
        'total_monto': documentos.aggregate(total=Sum('total_documento'))['total'] or 0,
        'documentos_pendientes': documentos.filter(estado_documento='pendiente').count(),
        'documentos_aprobados': documentos.filter(estado_documento='aprobado').count(),
        'documentos_credito': documentos.filter(estado_pago='credito').count(),
        'documentos_pagados': documentos.filter(estado_pago='pagada').count(),
        'monto_pendiente': documentos.filter(estado_pago__in=['credito', 'parcial']).aggregate(total=Sum('saldo_pendiente'))['total'] or 0,
    }
    
    # Paginación
    paginator = Paginator(documentos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'stats': stats,
        'empresa': empresa,
    }
    
    return render(request, 'documentos/documento_compra_list.html', context)


@login_required
@requiere_empresa
def documento_compra_create(request):
    """Crear nuevo documento de compra"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa = Empresa.objects.first()
        if not empresa:
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('dashboard')
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    if request.method == 'POST':
        form = DocumentoCompraForm(request.POST, request.FILES, empresa=empresa)
        formset = ItemDocumentoCompraFormSet(request.POST)
        
        # Debug: verificar errores
        if not form.is_valid():
            print("ERRORES EN FORM:")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
            messages.error(request, f'Errores en el formulario: {form.errors}')
        
        if not formset.is_valid():
            print("ERRORES EN FORMSET:")
            for i, form_errors in enumerate(formset.errors):
                if form_errors:
                    print(f"  Form {i}: {form_errors}")
            messages.error(request, f'Errores en los items: {formset.errors}')
        
        if form.is_valid() and formset.is_valid():
            try:
                documento = form.save(commit=False)
                documento.empresa = empresa
                documento.creado_por = request.user
                documento.save()
                
                # Guardar items
                formset.instance = documento
                formset.save()
                
                # Calcular totales
                documento.calcular_totales()
                
                messages.success(request, f'Documento {documento.get_tipo_documento_display()} {documento.numero_documento} creado exitosamente.')
                return redirect('documentos:documento_compra_detail', pk=documento.pk)
            except Exception as e:
                print(f"ERROR AL GUARDAR: {e}")
                messages.error(request, f'Error al guardar el documento: {str(e)}')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = DocumentoCompraForm(empresa=empresa)
        formset = ItemDocumentoCompraFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'empresa': empresa,
        'titulo': 'Crear Documento de Compra',
        'articulos_empresa': Articulo.objects.filter(empresa=empresa) if empresa else Articulo.objects.none(),
    }
    
    return render(request, 'documentos/documento_compra_form.html', context)


@login_required
@requiere_empresa
def documento_compra_detail(request, pk):
    """Detalle de documento de compra"""
    documento = get_object_or_404(DocumentoCompra, pk=pk)
    
    # Verificar que el usuario tenga acceso a la empresa del documento
    if not request.user.is_superuser:
        try:
            if request.user.perfil.empresa != documento.empresa:
                messages.error(request, 'No tienes permisos para ver este documento.')
                return redirect('documentos:documento_compra_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Historial de pagos
    historial_pagos = documento.historial_pagos.all()
    
    context = {
        'documento': documento,
        'historial_pagos': historial_pagos,
    }
    
    return render(request, 'documentos/documento_compra_detail.html', context)


@login_required
@requiere_empresa
def documento_compra_update(request, pk):
    """Editar documento de compra"""
    documento = get_object_or_404(DocumentoCompra, pk=pk)
    
    # Verificar que el usuario tenga acceso a la empresa del documento
    if not request.user.is_superuser:
        try:
            if request.user.perfil.empresa != documento.empresa:
                messages.error(request, 'No tienes permisos para editar este documento.')
                return redirect('documentos:documento_compra_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Verificar que se puede editar
    if not documento.puede_editar():
        messages.error(request, 'No se puede editar un documento que ya fue aprobado o procesado.')
        return redirect('documentos:documento_compra_detail', pk=documento.pk)
    
    if request.method == 'POST':
        form = DocumentoCompraForm(request.POST, request.FILES, instance=documento, empresa=documento.empresa)
        formset = ItemDocumentoCompraFormSet(request.POST, instance=documento)
        
        if form.is_valid() and formset.is_valid():
            documento = form.save()
            
            # Guardar items
            formset.save()
            
            # Calcular totales
            documento.calcular_totales()
            
            messages.success(request, f'Documento {documento.get_tipo_documento_display()} {documento.numero_documento} actualizado exitosamente.')
            return redirect('documentos:documento_compra_detail', pk=documento.pk)
    else:
        form = DocumentoCompraForm(instance=documento, empresa=documento.empresa)
        formset = ItemDocumentoCompraFormSet(instance=documento)
    
    context = {
        'form': form,
        'formset': formset,
        'documento': documento,
        'empresa': documento.empresa,
        'titulo': 'Editar Documento de Compra',
        'articulos_empresa': Articulo.objects.filter(empresa=documento.empresa),
    }
    
    return render(request, 'documentos/documento_compra_form.html', context)


@login_required
@requiere_empresa
def documento_compra_delete(request, pk):
    """Eliminar documento de compra"""
    documento = get_object_or_404(DocumentoCompra, pk=pk)
    
    # Verificar que el usuario tenga acceso a la empresa del documento
    if not request.user.is_superuser:
        try:
            if request.user.perfil.empresa != documento.empresa:
                messages.error(request, 'No tienes permisos para eliminar este documento.')
                return redirect('documentos:documento_compra_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Verificar que se puede eliminar
    if not documento.puede_editar():
        messages.error(request, 'No se puede eliminar un documento que ya fue aprobado o procesado.')
        return redirect('documentos:documento_compra_detail', pk=documento.pk)
    
    if request.method == 'POST':
        tipo_doc = documento.get_tipo_documento_display()
        numero_doc = documento.numero_documento
        documento.delete()
        messages.success(request, f'Documento {tipo_doc} {numero_doc} eliminado exitosamente.')
        return redirect('documentos:documento_compra_list')
    
    context = {
        'documento': documento,
    }
    
    return render(request, 'documentos/documento_compra_confirm_delete.html', context)


@login_required
@requiere_empresa
def documento_compra_aprobar(request, pk):
    """Aprobar documento de compra"""
    documento = get_object_or_404(DocumentoCompra, pk=pk)
    
    # Verificar que el usuario tenga acceso a la empresa del documento
    if not request.user.is_superuser:
        try:
            if request.user.perfil.empresa != documento.empresa:
                messages.error(request, 'No tienes permisos para aprobar este documento.')
                return redirect('documentos:documento_compra_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    if not documento.puede_aprobar():
        messages.error(request, 'Este documento no puede ser aprobado.')
        return redirect('documentos:documento_compra_detail', pk=documento.pk)
    
    documento.estado_documento = 'aprobado'
    documento.save()
    
    # Registrar en cuenta corriente si corresponde
    if documento.debe_ir_a_cuenta_corriente():
        documento.registrar_en_cuenta_corriente()
        messages.success(request, f'Documento {documento.get_tipo_documento_display()} {documento.numero_documento} aprobado y registrado en cuenta corriente.')
    else:
        messages.success(request, f'Documento {documento.get_tipo_documento_display()} {documento.numero_documento} aprobado exitosamente.')
    
    return redirect('documentos:documento_compra_detail', pk=documento.pk)


@login_required
def dashboard_documentos(request):
    """Dashboard de documentos de compra"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa = Empresa.objects.first()
        if not empresa:
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('dashboard')
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Estadísticas generales
    documentos = DocumentoCompra.objects.filter(empresa=empresa)
    
    stats = {
        'total_documentos': documentos.count(),
        'total_monto': documentos.aggregate(total=Sum('total_documento'))['total'] or 0,
        'documentos_pendientes': documentos.filter(estado_documento='pendiente').count(),
        'documentos_aprobados': documentos.filter(estado_documento='aprobado').count(),
        'documentos_credito': documentos.filter(estado_pago='credito').count(),
        'documentos_pagados': documentos.filter(estado_pago='pagada').count(),
        'monto_pendiente': documentos.filter(estado_pago__in=['credito', 'parcial']).aggregate(total=Sum('saldo_pendiente'))['total'] or 0,
        'documentos_vencidos': documentos.filter(
            estado_pago__in=['credito', 'parcial'],
            fecha_vencimiento__lt=timezone.now().date()
        ).count(),
    }
    
    # Documentos recientes
    documentos_recientes = documentos.order_by('-fecha_creacion')[:10]
    
    # Documentos próximos a vencer (próximos 30 días)
    fecha_limite = timezone.now().date() + timedelta(days=30)
    documentos_por_vencer = documentos.filter(
        estado_pago__in=['credito', 'parcial'],
        fecha_vencimiento__lte=fecha_limite,
        fecha_vencimiento__gt=timezone.now().date()
    ).order_by('fecha_vencimiento')[:10]
    
    context = {
        'stats': stats,
        'documentos_recientes': documentos_recientes,
        'documentos_por_vencer': documentos_por_vencer,
        'empresa': empresa,
    }
    
    return render(request, 'documentos/dashboard_documentos.html', context)


@login_required
def get_articulo_info(request, articulo_id):
    """Obtener información de un artículo via AJAX"""
    try:
        articulo = Articulo.objects.get(pk=articulo_id)
        return JsonResponse({
            'success': True,
            'codigo': articulo.codigo,
            'nombre': articulo.nombre,
            'precio': float(articulo.precio_venta) if articulo.precio_venta else 0,
            'stock': float(articulo.stock_actual) if articulo.stock_actual else 0,
        })
    except Articulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Artículo no encontrado'})