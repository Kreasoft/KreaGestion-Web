"""
Vistas para generación y gestión de DTE
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from empresas.decorators import requiere_empresa
from .models import DocumentoTributarioElectronico
from .dte_service import DTEService
from ventas.models import Venta, NotaCredito


@login_required
@requiere_empresa
def generar_dte_venta(request, venta_id):
    """
    Genera un DTE a partir de una venta
    """
    venta = get_object_or_404(Venta, pk=venta_id, empresa=request.empresa)
    
    # Verificar que la venta no tenga ya un DTE
    if hasattr(venta, 'dte'):
        messages.warning(request, 'Esta venta ya tiene un DTE generado.')
        return redirect('ventas:detalle_venta', pk=venta_id)
    
    # Verificar que la empresa tenga FE activada
    if not request.empresa.facturacion_electronica:
        messages.error(request, 'La facturación electrónica no está activada para esta empresa.')
        return redirect('ventas:detalle_venta', pk=venta_id)
    
    if request.method == 'POST':
        tipo_dte = request.POST.get('tipo_dte', '39')  # Por defecto Boleta
        
        try:
            # Inicializar servicio de DTE
            dte_service = DTEService(request.empresa)
            
            # Generar el DTE
            dte = dte_service.generar_dte_desde_venta(venta, tipo_dte)
            
            messages.success(
                request,
                f'DTE generado exitosamente: {dte.get_tipo_dte_display()} N° {dte.folio}'
            )
            
            # Preguntar si desea enviar al SII
            if request.POST.get('enviar_sii') == 'true':
                return redirect('facturacion_electronica:enviar_dte', dte_id=dte.id)
            else:
                return redirect('facturacion_electronica:dte_detail', pk=dte.id)
            
        except ValueError as e:
            messages.error(request, f'Error al generar DTE: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error inesperado: {str(e)}')
            import traceback
            traceback.print_exc()
    
    # Mostrar formulario para seleccionar tipo de DTE
    context = {
        'venta': venta,
        'tipos_dte': [
            ('33', 'Factura Electrónica'),
            ('39', 'Boleta Electrónica'),
            ('52', 'Guía de Despacho Electrónica'),
        ]
    }
    
    return render(request, 'facturacion_electronica/generar_dte_form.html', context)


@login_required
@requiere_empresa
def enviar_dte_sii(request, dte_id):
    """
    Envía un DTE al SII
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    
    # Verificar que no haya sido enviado ya
    if dte.estado_sii in ['enviado', 'aceptado']:
        messages.warning(request, 'Este DTE ya fue enviado al SII.')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)
    
    if request.method == 'POST':
        try:
            # Inicializar servicio
            dte_service = DTEService(request.empresa)
            
            # Enviar al SII
            respuesta = dte_service.enviar_dte_al_sii(dte)
            
            if respuesta.get('track_id'):
                messages.success(
                    request,
                    f'DTE enviado exitosamente al SII. Track ID: {respuesta["track_id"]}'
                )
            else:
                messages.warning(
                    request,
                    'DTE enviado pero no se recibió Track ID. Revise la respuesta del SII.'
                )
            
            return redirect('facturacion_electronica:dte_detail', pk=dte_id)
            
        except Exception as e:
            messages.error(request, f'Error al enviar DTE: {str(e)}')
            import traceback
            traceback.print_exc()
    
    context = {
        'dte': dte,
    }
    
    return render(request, 'facturacion_electronica/enviar_dte_confirm.html', context)




@login_required
@requiere_empresa
def consultar_estado_dte(request, dte_id):
    """
    Consulta el estado de un DTE en el SII
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    
    if not dte.track_id:
        messages.error(request, 'Este DTE no tiene Track ID. Debe ser enviado al SII primero.')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)
    
    try:
        # Inicializar servicio
        dte_service = DTEService(request.empresa)
        
        # Consultar estado
        estado = dte_service.consultar_estado_dte(dte)
        
        messages.success(
            request,
            f'Estado consultado: {estado.get("estado")} - {estado.get("glosa", "")}'
        )
        
    except Exception as e:
        messages.error(request, f'Error al consultar estado: {str(e)}')
        import traceback
        traceback.print_exc()
    
    return redirect('facturacion_electronica:dte_detail', pk=dte_id)


@login_required
@requiere_empresa
def dte_detail(request, pk):
    """
    Detalle de un DTE
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=pk, empresa=request.empresa)
    
    context = {
        'dte': dte,
    }
    
    return render(request, 'facturacion_electronica/dte_detail.html', context)


@login_required
@requiere_empresa
def ver_factura_electronica(request, dte_id):
    """
    Muestra la factura electrónica con el timbre
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    
    # Obtener la venta asociada
    venta = dte.venta
    
    if not venta:
        messages.error(request, 'Este DTE no tiene una venta asociada.')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)
    
    # Obtener detalles de la venta (materializar lista y prefetch para template)
    detalles = list(
        venta.ventadetalle_set.all()
        .select_related('articulo', 'articulo__unidad_medida')
    )
    
    context = {
        'dte': dte,
        'venta': venta,
        'detalles': detalles,
        'empresa': request.empresa,
    }
    
    # Seleccionar template según tipo de DTE
    if dte.tipo_dte in ['33', '34']:  # Facturas
        template = 'ventas/factura_electronica_html.html'
    elif dte.tipo_dte in ['39', '41']:  # Boletas
        template = 'ventas/factura_electronica_html.html'  # Usar mismo template
    elif dte.tipo_dte == '52':  # Guía de Despacho
        template = 'inventario/guia_despacho_electronica_html.html'
    else:
        template = 'ventas/factura_electronica_html.html'
    
    return render(request, template, context)


@login_required
@requiere_empresa
def ver_notacredito_electronica(request, notacredito_id):
    """
    Muestra la Nota de Crédito electrónica con el timbre
    """
    nota = get_object_or_404(NotaCredito, pk=notacredito_id, empresa=request.empresa)
    
    # Obtener el DTE asociado directamente desde la nota de crédito
    dte = nota.dte

    # Obtener detalles de la nota de crédito
    detalles = nota.items.all()
    
    context = {
        'dte': dte,
        'nota': nota,
        'detalles': detalles,
    }
    
    return render(request, 'ventas/notacredito_electronica_html.html', context)


@login_required
@requiere_empresa
def dte_list(request):
    """
    Lista de DTEs de la empresa
    """
    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa
    ).select_related('venta', 'caf_utilizado').order_by('-fecha_emision', '-folio')
    
    # Filtros
    tipo_dte = request.GET.get('tipo_dte')
    estado_sii = request.GET.get('estado_sii')
    
    if tipo_dte:
        dtes = dtes.filter(tipo_dte=tipo_dte)
    
    if estado_sii:
        dtes = dtes.filter(estado_sii=estado_sii)
    
    # Estadísticas
    total_dtes = dtes.count()
    generados = dtes.filter(estado_sii='generado').count()
    enviados = dtes.filter(estado_sii='enviado').count()
    aceptados = dtes.filter(estado_sii='aceptado').count()
    rechazados = dtes.filter(estado_sii='rechazado').count()
    
    context = {
        'dtes': dtes,
        'total_dtes': total_dtes,
        'generados': generados,
        'enviados': enviados,
        'aceptados': aceptados,
        'rechazados': rechazados,
    }
    
    return render(request, 'facturacion_electronica/dte_list.html', context)
