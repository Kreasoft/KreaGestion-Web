"""
Vistas para generación y gestión de DTE
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime
from core.decorators import requiere_empresa
from .models import DocumentoTributarioElectronico
from .dte_service import DTEService
from ventas.models import Venta, NotaCredito
from clientes.models import Cliente


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
    
    # Obtener la venta o la orden de despacho asociada
    venta = dte.venta
    orden_despacho = dte.orden_despacho.first()
    documento_origen = venta or orden_despacho

    if not documento_origen:
        messages.error(request, 'Este DTE no tiene un documento de origen asociado (Venta u Orden de Despacho).')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)

    # Si no hay venta pero hay orden de despacho, crear un objeto wrapper para compatibilidad
    if not venta and orden_despacho:
        # Crear un objeto simple que tenga los atributos necesarios para el template
        class VentaWrapper:
            def __init__(self, orden_despacho, dte):
                # Número de venta: usar folio del DTE o número de despacho
                self.numero_venta = dte.folio or getattr(orden_despacho, 'numero_despacho', 'N/A')
                # Empresa
                self.empresa = orden_despacho.empresa if hasattr(orden_despacho, 'empresa') else dte.empresa
                # Cliente desde orden_pedido
                self.cliente = orden_despacho.orden_pedido.cliente if hasattr(orden_despacho, 'orden_pedido') and orden_despacho.orden_pedido else None
                # Vendedor desde orden_pedido si existe
                self.vendedor = getattr(orden_despacho.orden_pedido, 'vendedor', None) if hasattr(orden_despacho, 'orden_pedido') and orden_despacho.orden_pedido else None
                # Fecha: usar fecha_despacho o fecha_emision del DTE
                self.fecha = orden_despacho.fecha_despacho if hasattr(orden_despacho, 'fecha_despacho') else dte.fecha_emision
                # Totales desde DTE
                self.total = dte.monto_total
                self.subtotal = dte.monto_neto
                self.iva = dte.monto_iva
                self.descuento = 0
                self.neto = dte.monto_neto
                self.impuesto_especifico = 0
                # Forma de pago: None (no aplica para órdenes de despacho)
                self.forma_pago = None
                self.saldo_pendiente = 0
                # Referencias: objeto vacío que retorna False en .exists()
                class ReferenciasWrapper:
                    def exists(self):
                        return False
                    def all(self):
                        return []
                self.referencias = ReferenciasWrapper()
                # Observaciones
                self.observaciones = getattr(orden_despacho, 'observaciones', '')
        
        venta = VentaWrapper(orden_despacho, dte)

    # Obtener detalles del documento
    detalles = []
    if isinstance(documento_origen, Venta):
        detalles = list(documento_origen.ventadetalle_set.all().select_related('articulo', 'articulo__unidad_medida'))
    elif isinstance(documento_origen, OrdenDespacho):
        detalles = list(documento_origen.detalleordendespacho_set.all().select_related('item_pedido__articulo', 'item_pedido__articulo__unidad_medida'))
    
    # Obtener configuración de impresora
    empresa = request.empresa
    nombre_impresora = None
    
    # Seleccionar template según tipo de DTE Y configuración de impresora
    if dte.tipo_dte in ['33', '34']:  # Facturas
        tipo_impresora = getattr(empresa, 'impresora_factura', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_factura_nombre', None)
        
        if tipo_impresora == 'termica':
            template = 'ventas/factura_electronica_termica.html'
        else:
            template = 'ventas/factura_electronica_html.html'
    
    elif dte.tipo_dte in ['39', '41']:  # Boletas
        tipo_impresora = getattr(empresa, 'impresora_boleta', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_boleta_nombre', None)
        
        if tipo_impresora == 'termica':
            template = 'ventas/boleta_electronica_termica.html'
        else:
            template = 'ventas/factura_electronica_html.html' # Reutiliza el formato A4 de factura
    
    elif dte.tipo_dte == '52':  # Guía de Despacho
        tipo_impresora = getattr(empresa, 'impresora_guia', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_guia_nombre', None)
        
        if tipo_impresora == 'termica':
            from django.template.loader import select_template
            try:
                select_template(['inventario/guia_despacho_termica.html'])
                template = 'inventario/guia_despacho_termica.html'
            except:
                template = 'inventario/guia_despacho_electronica_html.html' # Fallback a A4
        else:
            template = 'inventario/guia_despacho_electronica_html.html'
    
    else:
        # Fallback para otros tipos de DTE
        template = 'ventas/factura_electronica_html.html'
    
    # Log de impresora física
    if nombre_impresora:
        print(f"[PRINT] Impresora fisica configurada: {nombre_impresora}")
    
    # Obtener formas de pago múltiples (desde MovimientoCaja)
    formas_pago_list = []
    try:
        from caja.models import VentaProcesada, MovimientoCaja
        
        # Solo buscar formas de pago si venta es una instancia real de Venta (no wrapper)
        if venta and hasattr(venta, 'id') and isinstance(venta, Venta):
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
        'dte': dte,
        'venta': venta,
        'detalles': detalles,
        'empresa': empresa,
        'nombre_impresora': nombre_impresora,  # Nombre de impresora física
        'formas_pago_list': formas_pago_list,  # Lista de formas de pago múltiples
    }
    
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
    
    # Obtener configuración de impresora
    empresa = request.empresa
    tipo_impresora = getattr(empresa, 'impresora_nota_credito', 'laser')
    nombre_impresora = getattr(empresa, 'impresora_nota_credito_nombre', None)
    
    # Seleccionar template según configuración
    if tipo_impresora == 'termica':
        template = 'ventas/notacredito_electronica_termica.html'
        print(f"[PRINT] Nota Credito -> Formato TERMICO 80mm")
    else:
        template = 'ventas/notacredito_electronica_html.html'
        print(f"[PRINT] Nota Credito -> Formato LASER A4")
    
    if nombre_impresora:
        print(f"[PRINT] Impresora fisica configurada: {nombre_impresora}")
    
    context = {
        'dte': dte,
        'nota': nota,
        'detalles': detalles,
        'empresa': empresa,
        'nombre_impresora': nombre_impresora,
    }
    
    return render(request, template, context)


@login_required
@requiere_empresa
def dte_list(request):
    """
    Lista de DTEs de la empresa (Libro de Ventas Electrónico)
    """
    # Fecha por defecto: primer día del año hasta hoy
    hoy = timezone.now().date()
    primer_dia_ano = hoy.replace(month=1, day=1)
    
    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa
    ).select_related('venta__cliente', 'venta__vendedor', 'caf_utilizado').order_by('-fecha_emision', '-folio')

    # Obtener parámetros de filtros
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    cliente_id = request.GET.get('cliente', '')
    tipo_dte = request.GET.get('tipo_dte', '')
    fecha_desde = request.GET.get('fecha_desde', primer_dia_ano.strftime('%Y-%m-%d'))
    fecha_hasta = request.GET.get('fecha_hasta', hoy.strftime('%Y-%m-%d'))

    # Aplicar filtros
    if search:
        dtes = dtes.filter(
            Q(folio__icontains=search) |
            Q(razon_social_receptor__icontains=search) |
            Q(rut_receptor__icontains=search)
        )
    
    if estado:
        dtes = dtes.filter(estado_sii=estado)
    
    if cliente_id:
        dtes = dtes.filter(venta__cliente_id=cliente_id)
    
    if tipo_dte:
        dtes = dtes.filter(tipo_dte=tipo_dte)
    
    # Aplicar filtros de fecha
    try:
        fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
        dtes = dtes.filter(fecha_emision__gte=fecha_desde_obj, fecha_emision__lte=fecha_hasta_obj)
    except (ValueError, TypeError):
        pass

    # Estadísticas
    stats = dtes.aggregate(
        total_documentos=Count('id'),
        total_neto=Sum('monto_neto'),
        total_iva=Sum('monto_iva'),
        total_general=Sum('monto_total')
    )
    
    # Estadísticas por tipo de documento
    stats_por_tipo = dtes.values('tipo_dte').annotate(
        cantidad=Count('id'),
        total=Sum('monto_total')
    ).order_by('tipo_dte')

    # Opciones para filtros
    clientes = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')
    
    # Tipos de documento DTE
    tipos_dte_dict = {
        '33': 'Factura Electrónica (33)',
        '34': 'Factura Exenta Electrónica (34)',
        '39': 'Boleta Electrónica (39)',
        '41': 'Boleta Exenta Electrónica (41)',
        '52': 'Guía de Despacho Electrónica (52)',
        '56': 'Nota de Débito Electrónica (56)',
        '61': 'Nota de Crédito Electrónica (61)',
    }
    
    # Estados SII
    estados_sii = [
        ('', 'Todos los estados'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
        ('pendiente', 'Pendiente'),
        ('anulado', 'Anulado'),
    ]

    context = {
        'dtes': dtes,
        'stats': stats,
        'stats_por_tipo': stats_por_tipo,
        'search': search,
        'estado': estado,
        'cliente_id': cliente_id,
        'tipo_dte': tipo_dte,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'clientes': clientes,
        'tipos_dte': tipos_dte_dict,
        'estados_sii': estados_sii,
    }

    return render(request, 'facturacion_electronica/dte_list.html', context)
