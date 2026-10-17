from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime

from decimal import Decimal
from .models import OrdenPedido, ItemOrdenPedido #, DespachoPedido
from .forms import OrdenPedidoForm, ItemOrdenPedidoFormSet, BusquedaPedidoForm #, DespachoPedidoForm, DespachoEstadoForm, BusquedaDespachoForm, ItemDespachoPedidoFormSet
from empresas.models import Empresa
from articulos.models import Articulo
from ventas.models import Venta, VentaDetalle
from core.decorators import requiere_empresa


def articulos_con_stock(empresa):
    """Artículos de la empresa con stock total anotado."""
    return Articulo.objects.filter(empresa=empresa).annotate(
        stock_total=Coalesce(
            Sum('stocks__cantidad', filter=Q(stocks__empresa=empresa)),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).order_by('nombre')


def total_saldo_por_despachar(qs):
    """Suma el monto de unidades aún no despachadas (no el total del pedido)."""
    return OrdenPedido.total_saldo_por_despachar(qs)


def _crear_cotizacion_desde_pedido(empresa, user, form, formset):
    """Crea una cotización en el módulo de Ventas con el contenido del formulario de pedido."""
    with transaction.atomic():
        Empresa.objects.select_for_update().get(pk=empresa.pk)
        
        import re
        cots_empresa = Venta.objects.filter(
            empresa=empresa,
            tipo_documento='cotizacion'
        ).values_list('numero_venta', flat=True)
        
        max_num = 0
        for num_str in cots_empresa:
            if not num_str:
                continue
            match = re.search(r'(\d+)$', str(num_str))
            if match:
                try:
                    val = int(match.group(1))
                    if val < 100000000 and val > max_num:
                        max_num = val
                except ValueError:
                    pass
                    
        nuevo_numero = max_num + 1
        numero_cot = f"{nuevo_numero:06d}"
        while Venta.objects.filter(empresa=empresa, tipo_documento='cotizacion', numero_venta=numero_cot).exists():
            nuevo_numero += 1
            numero_cot = f"{nuevo_numero:06d}"

        cliente = form.cleaned_data.get('cliente')
        vendedor = form.cleaned_data.get('vendedor')
        fecha_pedido = form.cleaned_data.get('fecha_pedido') or timezone.localdate()
        
        obs_list = []
        if form.cleaned_data.get('observaciones'):
            obs_list.append(form.cleaned_data.get('observaciones'))
        if form.cleaned_data.get('condiciones_pago'):
            obs_list.append(f"Condiciones de pago: {form.cleaned_data.get('condiciones_pago')}")
        if form.cleaned_data.get('numero_oc_cliente'):
            obs_list.append(f"OC Cliente: {form.cleaned_data.get('numero_oc_cliente')}")
        obs_texto = "\n".join(obs_list)

        cotizacion = Venta.objects.create(
            empresa=empresa,
            numero_venta=numero_cot,
            fecha=fecha_pedido,
            cliente=cliente,
            vendedor=vendedor,
            tipo_documento='cotizacion',
            tipo_documento_planeado='factura',
            direccion_despacho=form.cleaned_data.get('direccion_despacho') or getattr(cliente, 'direccion', '') or '',
            comuna_despacho=form.cleaned_data.get('comuna_despacho') or getattr(cliente, 'comuna', '') or '',
            ciudad_despacho=form.cleaned_data.get('ciudad_despacho') or getattr(cliente, 'ciudad', '') or '',
            direccion_cliente=form.cleaned_data.get('direccion_cliente'),
            estado='confirmada',
            estado_cotizacion='pendiente',
            facturado=False,
            observaciones=obs_texto,
            usuario_creacion=user
        )

        subtotal_acum = Decimal('0.00')
        descuento_acum = Decimal('0.00')
        neto_acum = Decimal('0.00')
        iva_acum = Decimal('0.00')

        for item_form in formset:
            if not item_form.cleaned_data or item_form.cleaned_data.get('DELETE'):
                continue
            articulo = item_form.cleaned_data.get('articulo')
            if not articulo:
                continue
            
            cantidad = Decimal(str(item_form.cleaned_data.get('cantidad') or 1))
            precio_unitario = Decimal(str(item_form.cleaned_data.get('precio_unitario') or 0))
            desc_porc = Decimal(str(item_form.cleaned_data.get('descuento_porcentaje') or 0))
            imp_porc = Decimal(str(item_form.cleaned_data.get('impuesto_porcentaje') or 19))
            
            subtotal_linea = cantidad * precio_unitario
            desc_monto = subtotal_linea * (desc_porc / Decimal('100'))
            base_linea = subtotal_linea - desc_monto
            iva_linea = base_linea * (imp_porc / Decimal('100'))
            
            subtotal_acum += subtotal_linea
            descuento_acum += desc_monto
            neto_acum += base_linea
            iva_acum += iva_linea

            precio_unit_efectivo = precio_unitario * (Decimal('1') - (desc_porc / Decimal('100')))
            
            VentaDetalle.objects.create(
                venta=cotizacion,
                articulo=articulo,
                cantidad=cantidad,
                precio_unitario=precio_unit_efectivo,
                precio_total=base_linea,
                impuesto_especifico=Decimal('0.00')
            )

        cotizacion.subtotal = round(subtotal_acum)
        cotizacion.descuento = round(descuento_acum)
        cotizacion.neto = round(neto_acum)
        cotizacion.iva = round(iva_acum)
        cotizacion.total = round(neto_acum + iva_acum)
        cotizacion.save()

        return cotizacion


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
    
    # Alinear estado con despacho real (completo / en proceso) antes de listar.
    OrdenPedido.sincronizar_estados_por_despacho(empresa=empresa)

    pedidos = OrdenPedido.objects.filter(empresa=empresa).select_related(
        'cliente', 'bodega', 'creado_por'
    )

    pedidos = pedidos.order_by('-fecha_pedido', '-numero_pedido')
    
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
        if estado == 'confirmada':
            pedidos = pedidos.exclude(estado__in=['completada', 'cancelada'])
        elif estado:
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
        'pedidos_pendientes': pedidos.exclude(estado__in=['completada', 'cancelada']).count(),
        'pedidos_completados': pedidos.filter(estado='completada').count(),
        'monto_total': total_saldo_por_despachar(
            pedidos.exclude(estado__in=['completada', 'cancelada'])
        ),
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
        form = OrdenPedidoForm(request.POST, empresa=empresa)
        formset = ItemOrdenPedidoFormSet(request.POST, empresa=empresa)
        
        if not form.is_valid() or not formset.is_valid():
            with open(r'C:\PROYECTOS-WEB-SII\GestionCloud-SII\debug_errors.log', 'w') as f:
                f.write(f"Form errors: {form.errors}\n")
                f.write(f"Formset errors: {formset.errors}\n")
                f.write(f"Formset non_form_errors: {formset.non_form_errors()}\n")
                f.write(f"POST: {request.POST}\n")
        
        if form.is_valid() and formset.is_valid():
            items_validos = [
                f for f in formset 
                if f.cleaned_data and not f.cleaned_data.get('DELETE') and f.cleaned_data.get('articulo')
            ]
            if not items_validos:
                messages.error(request, 'Debe ingresar al menos un producto en la orden de pedido.')
                articulos_empresa = articulos_con_stock(empresa)
                return render(request, 'pedidos/orden_pedido_form.html', {
                    'form': form,
                    'formset': formset,
                    'articulos_empresa': articulos_empresa,
                    'empresa': empresa,
                })

            accion = request.POST.get('accion')
            if accion == 'guardar_cotizacion':
                try:
                    cotizacion = _crear_cotizacion_desde_pedido(empresa, request.user, form, formset)
                    messages.success(request, f'Cotización #{cotizacion.numero_venta} creada exitosamente desde orden de pedido.')
                    return redirect('ventas:cotizacion_list')
                except Exception as e:
                    import traceback
                    print(f"Error al guardar cotización: {str(e)}")
                    print(traceback.format_exc())
                    messages.error(request, f'Error al guardar la cotización: {str(e)}')
            else:
                try:
                    with transaction.atomic():
                        # El bloqueo es por empresa: cada tenant conserva su propio correlativo.
                        Empresa.objects.select_for_update().get(pk=empresa.pk)
                        pedido = form.save(commit=False)
                        pedido.empresa = empresa
                        pedido.creado_por = request.user
                        pedido.estado = 'confirmada'

                        pedido.generar_numero_pedido()
                        pedido.save()

                        formset.instance = pedido
                        formset.save()

                        pedido.calcular_totales()
                    
                    messages.success(request, f'Orden de pedido {pedido.numero_pedido} creada exitosamente.')
                    from django.urls import reverse
                    return redirect(f"{reverse('pedidos:orden_pedido_detail', kwargs={'pk': pedido.pk})}?nuevo=1")
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
        form = OrdenPedidoForm(empresa=empresa)
        formset = ItemOrdenPedidoFormSet(empresa=empresa)
    
    articulos_empresa = articulos_con_stock(empresa)
    
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


from django.views.decorators.clickjacking import xframe_options_exempt


@xframe_options_exempt
@login_required
@requiere_empresa
def orden_pedido_pdf(request, pk):
    """Genera comprobante PDF profesional de una orden de pedido con logo de la empresa."""
    from io import BytesIO
    import os
    from django.http import HttpResponse
    from django.utils import timezone
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportLabImage
    )

    pedido = get_object_or_404(
        OrdenPedido.objects.select_related('cliente', 'bodega', 'creado_por', 'empresa'),
        pk=pk,
        empresa=request.empresa
    )

    # Si no se solicita el binario directo (raw=1) o descarga (dl=1), mostrar visor interactivo con botones Volver / Cerrar / Imprimir
    if request.GET.get('raw') != '1' and request.GET.get('dl') != '1':
        resp = render(request, 'pedidos/orden_pedido_pdf_visor.html', {
            'pedido': pedido,
            'empresa': pedido.empresa,
        })
        resp.xframe_options_exempt = True
        return resp

    items = pedido.items.select_related('articulo').all()
    empresa = pedido.empresa
    cliente = pedido.cliente

    # Paleta de colores corporativa profesional
    color_primario = colors.HexColor('#2c3e50')   # Azul pizarra corporativo
    color_acento = colors.HexColor('#8B7355')     # Marrón piedra distintivo
    color_borde = colors.HexColor('#d4c4a8')      # Beige cálido para bordes
    color_fondo = colors.HexColor('#fafaf8')      # Fondo suave crema
    color_fondo_th = colors.HexColor('#f5f1e8')   # Encabezado tabla
    color_texto = colors.HexColor('#2c3e50')
    color_gris = colors.HexColor('#6b7280')

    # Estilos de texto
    st_emp_nombre = ParagraphStyle('EmpNombre', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=color_primario)
    st_emp_sub = ParagraphStyle('EmpSub', fontName='Helvetica', fontSize=7.5, leading=10, textColor=color_gris)

    st_box_rut = ParagraphStyle('BoxRut', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=color_acento, alignment=TA_CENTER)
    st_box_titulo = ParagraphStyle('BoxTit', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=color_primario, alignment=TA_CENTER)
    st_box_num = ParagraphStyle('BoxNum', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=color_acento, alignment=TA_CENTER)
    st_box_meta = ParagraphStyle('BoxMeta', fontName='Helvetica', fontSize=8, leading=10.5, textColor=color_gris, alignment=TA_CENTER)

    st_label = ParagraphStyle('Lbl', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=color_acento)
    st_val = ParagraphStyle('Val', fontName='Helvetica', fontSize=8, leading=10.5, textColor=color_texto)
    st_val_b = ParagraphStyle('ValB', fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=color_texto)

    st_th = ParagraphStyle('Th', fontName='Helvetica-Bold', fontSize=7.2, leading=9, textColor=color_acento, alignment=TA_CENTER)
    st_th_l = ParagraphStyle('ThL', fontName='Helvetica-Bold', fontSize=7.2, leading=9, textColor=color_acento, alignment=TA_LEFT)
    st_th_r = ParagraphStyle('ThR', fontName='Helvetica-Bold', fontSize=7.2, leading=9, textColor=color_acento, alignment=TA_RIGHT)
    st_td = ParagraphStyle('Td', fontName='Helvetica', fontSize=7.2, leading=9, textColor=color_texto)
    st_td_code = ParagraphStyle('TdCode', fontName='Helvetica-Bold', fontSize=7, leading=8.5, textColor=color_texto, alignment=TA_CENTER)
    st_td_c = ParagraphStyle('TdC', fontName='Helvetica', fontSize=7.2, leading=9, textColor=color_texto, alignment=TA_CENTER)
    st_td_r = ParagraphStyle('TdR', fontName='Helvetica', fontSize=7.2, leading=9, textColor=color_texto, alignment=TA_RIGHT)

    def _fmt(val):
        if val is None:
            return "$ 0"
        try:
            return f"$ {int(round(float(val))):,}".replace(",", ".")
        except Exception:
            return str(val)

    # 1. Cabecera con Logo y Datos de la Empresa
    logo_flowable = None
    if empresa.logo and hasattr(empresa.logo, 'path') and os.path.exists(empresa.logo.path):
        try:
            from PIL import Image as PILImage
            with PILImage.open(empresa.logo.path) as img:
                orig_w, orig_h = img.size
            max_w = 46 * mm
            max_h = 24 * mm
            ratio = min(max_w / orig_w, max_h / orig_h)
            logo_flowable = ReportLabImage(empresa.logo.path, width=orig_w * ratio, height=orig_h * ratio)
            logo_flowable.hAlign = 'LEFT'
        except Exception as e:
            print(f"[PDF] Error al cargar logo empresa: {e}")
            logo_flowable = None

    emisor_lineas = []
    if logo_flowable:
        emisor_lineas.append(logo_flowable)
        emisor_lineas.append(Spacer(1, 2 * mm))
    emisor_lineas.append(Paragraph(empresa.nombre.upper(), st_emp_nombre))
    if empresa.rut:
        emisor_lineas.append(Paragraph(f"<b>RUT:</b> {empresa.rut}", st_emp_sub))
    if empresa.giro:
        emisor_lineas.append(Paragraph(f"<b>Giro:</b> {empresa.giro}", st_emp_sub))
    dir_completa = f"{empresa.direccion or ''}"
    if empresa.comuna or empresa.ciudad:
        dir_completa += f" - {empresa.comuna or ''}, {empresa.ciudad or ''}".strip(" -,")
    if dir_completa.strip():
        emisor_lineas.append(Paragraph(f"<b>Dirección:</b> {dir_completa.strip()}", st_emp_sub))
    contactos = []
    if empresa.telefono:
        contactos.append(f"Tel: {empresa.telefono}")
    if empresa.email:
        contactos.append(f"Email: {empresa.email}")
    if contactos:
        emisor_lineas.append(Paragraph(" • ".join(contactos), st_emp_sub))

    # Recuadro oficial del Pedido
    estado_texto = pedido.get_estado_display().upper()
    caja_pedido_contenido = [
        [Paragraph(f"R.U.T.: {empresa.rut or 'SIN RUT'}", st_box_rut)],
        [Paragraph("ORDEN DE PEDIDO", st_box_titulo)],
        [Paragraph(f"N° {pedido.numero_pedido}", st_box_num)],
        [Paragraph(f"<b>Emisión:</b> {pedido.fecha_pedido.strftime('%d-%m-%Y')}", st_box_meta)],
        [Paragraph(f"<b>Estado:</b> {estado_texto}", st_box_meta)],
    ]
    caja_pedido = Table(caja_pedido_contenido, colWidths=[68 * mm])
    caja_pedido.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, color_acento),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (-1, 1), 0.8, color_borde),
    ]))

    cabecera = Table([[emisor_lineas, caja_pedido]], colWidths=[112 * mm, 70 * mm])
    cabecera.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))

    # 2. Bloque de Datos del Cliente y Condiciones Comerciales
    dir_cli = cliente.direccion or '—'
    comuna_cli = f"{cliente.comuna or ''} {cliente.ciudad or ''}".strip() or '—'
    fono_email_cli = f"{cliente.telefono or ''} {('/ ' + cliente.email) if cliente.email else ''}".strip() or '—'

    fecha_ent = pedido.fecha_entrega_estimada.strftime('%d-%m-%Y') if pedido.fecha_entrega_estimada else 'No definida'
    oc_txt = pedido.numero_oc_cliente or '—'
    if pedido.fecha_oc_cliente:
        oc_txt += f" ({pedido.fecha_oc_cliente.strftime('%d-%m-%Y')})"

    vendedor_txt = pedido.vendedor.nombre if pedido.vendedor else (pedido.creado_por.get_full_name() or pedido.creado_por.username if pedido.creado_por else '—')
    datos_cliente = [
        [
            Paragraph("SEÑOR(ES):", st_label), Paragraph(cliente.nombre.upper(), st_val_b),
            Paragraph("R.U.T.:", st_label), Paragraph(cliente.rut or '—', st_val_b)
        ],
        [
            Paragraph("DIRECCIÓN:", st_label), Paragraph(dir_cli, st_val),
            Paragraph("COMUNA/CIUDAD:", st_label), Paragraph(comuna_cli, st_val)
        ],
        [
            Paragraph("TELÉFONO / EMAIL:", st_label), Paragraph(fono_email_cli, st_val),
            Paragraph("BODEGA DESPACHO:", st_label), Paragraph(pedido.bodega.nombre if pedido.bodega else '—', st_val)
        ],
        [
            Paragraph("COND. PAGO:", st_label), Paragraph(pedido.condiciones_pago or 'Contado', st_val),
            Paragraph("ENTREGA ESTIMADA:", st_label), Paragraph(fecha_ent, st_val)
        ],
        [
            Paragraph("N° OC CLIENTE:", st_label), Paragraph(oc_txt, st_val),
            Paragraph("VENDEDOR:", st_label), Paragraph(vendedor_txt, st_val)
        ]
    ]
    tabla_cliente = Table(datos_cliente, colWidths=[27 * mm, 73 * mm, 27 * mm, 55 * mm])
    tabla_cliente.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, color_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, color_borde),
        ('BACKGROUND', (0, 0), (0, -1), color_fondo_th),
        ('BACKGROUND', (2, 0), (2, -1), color_fondo_th),
        ('BACKGROUND', (1, 0), (1, -1), color_fondo),
        ('BACKGROUND', (3, 0), (3, -1), color_fondo),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # 3. Tabla Detalle de Ítems
    filas_items = [[
        Paragraph("#", st_th),
        Paragraph("CÓDIGO", st_th),
        Paragraph("DESCRIPCIÓN DEL PRODUCTO", st_th_l),
        Paragraph("CANTIDAD", st_th),
        Paragraph("P. UNITARIO", st_th_r),
        Paragraph("DESC %", st_th_r),
        Paragraph("TOTAL", st_th_r),
    ]]

    for idx, it in enumerate(items, start=1):
        desc_linea = it.articulo.nombre
        if it.observaciones:
            desc_linea += f"<br/><font color='#6b7280' size='6.5'><i>{it.observaciones}</i></font>"

        cant_fmt = f"{it.cantidad:.2f}".rstrip('0').rstrip('.') if it.cantidad % 1 != 0 else f"{int(it.cantidad)}"
        subtotal_linea = it.get_subtotal() - it.get_descuento_monto()
        desc_pct = f"{it.descuento_porcentaje:.0f}%" if it.descuento_porcentaje > 0 else "-"

        filas_items.append([
            Paragraph(str(idx), st_td_c),
            Paragraph(it.articulo.codigo or '—', st_td_code),
            Paragraph(desc_linea, st_td),
            Paragraph(cant_fmt, st_td_c),
            Paragraph(_fmt(it.precio_unitario), st_td_r),
            Paragraph(desc_pct, st_td_r),
            Paragraph(_fmt(subtotal_linea), st_td_r),
        ])

    while len(filas_items) < 6:
        filas_items.append(['', '', '', '', '', '', ''])

    tabla_items = Table(
        filas_items,
        colWidths=[7 * mm, 36 * mm, 69 * mm, 14 * mm, 20 * mm, 13 * mm, 23 * mm]
    )
    tabla_items.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, color_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, color_borde),
        ('BACKGROUND', (0, 0), (-1, 0), color_fondo_th),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # 4. Observaciones y Totales
    obs_content = []
    obs_content.append(Paragraph("<b>OBSERVACIONES:</b>", st_label))
    if pedido.observaciones:
        obs_content.append(Paragraph(pedido.observaciones.replace('\n', '<br/>'), st_val))
    else:
        obs_content.append(Paragraph("Sin observaciones adicionales.", st_emp_sub))
    obs_content.append(Spacer(1, 3 * mm))
    obs_content.append(Paragraph(
        "<i>Nota: Este comprobante es un documento interno de control y respaldo de pedido. "
        "No constituye documento tributario electrónico (DTE).</i>",
        st_emp_sub
    ))

    caja_obs = Table([[obs_content]], colWidths=[106 * mm])
    caja_obs.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, color_borde),
        ('BACKGROUND', (0, 0), (-1, -1), color_fondo),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    st_tot_lbl = ParagraphStyle('TotLbl', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=color_primario)
    st_tot_val = ParagraphStyle('TotVal', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_RIGHT, textColor=color_primario)
    st_tot_big_lbl = ParagraphStyle('TotBigLbl', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=color_acento)
    st_tot_big_val = ParagraphStyle('TotBigVal', fontName='Helvetica-Bold', fontSize=10.5, leading=12, alignment=TA_RIGHT, textColor=color_acento)

    filas_tot = [
        [Paragraph("SUBTOTAL NETO", st_tot_lbl), Paragraph(_fmt(pedido.subtotal), st_tot_val)],
    ]
    if pedido.descuentos_totales > 0:
        filas_tot.append([
            Paragraph("DESCUENTOS", st_tot_lbl),
            Paragraph(f"- {_fmt(pedido.descuentos_totales)}", st_tot_val)
        ])
    filas_tot.append([
        Paragraph("IVA (19%)", st_tot_lbl),
        Paragraph(_fmt(pedido.impuestos_totales), st_tot_val)
    ])
    filas_tot.append([
        Paragraph("TOTAL PEDIDO", st_tot_big_lbl),
        Paragraph(_fmt(pedido.total_pedido), st_tot_big_val)
    ])

    tabla_tot = Table(filas_tot, colWidths=[40 * mm, 34 * mm])
    tabla_tot.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, color_acento),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, color_borde),
        ('BACKGROUND', (0, 0), (-1, -2), color_fondo),
        ('BACKGROUND', (0, -1), (-1, -1), color_fondo_th),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    bloque_pie = Table([[caja_obs, tabla_tot]], colWidths=[108 * mm, 74 * mm])
    bloque_pie.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))

    # 5. Firmas de Control
    st_sig = ParagraphStyle('Sig', fontName='Helvetica', fontSize=7, leading=9, alignment=TA_CENTER, textColor=color_gris)
    filas_firmas = [
        ['', '', ''],
        [
            Paragraph(f"<b>Emitido por:</b><br/>{pedido.creado_por.get_full_name() or pedido.creado_por.username}", st_sig),
            Paragraph("<b>Aprobado por:</b><br/>Firma y Timbre", st_sig),
            Paragraph("<b>Recepción Conforme:</b><br/>Firma, RUT y Fecha", st_sig),
        ]
    ]
    tabla_firmas = Table(filas_firmas, colWidths=[60 * mm, 60 * mm, 62 * mm], rowHeights=[14 * mm, 10 * mm])
    tabla_firmas.setStyle(TableStyle([
        ('LINEABOVE', (0, 1), (0, 1), 0.7, color_gris),
        ('LINEABOVE', (1, 1), (1, 1), 0.7, color_gris),
        ('LINEABOVE', (2, 1), (2, 1), 0.7, color_gris),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
    ]))

    historia = [
        cabecera,
        Spacer(1, 4 * mm),
        tabla_cliente,
        Spacer(1, 4 * mm),
        tabla_items,
        Spacer(1, 4 * mm),
        bloque_pie,
        Spacer(1, 7 * mm),
        tabla_firmas,
    ]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Orden de Pedido {pedido.numero_pedido}",
        author=empresa.nombre
    )
    doc.build(historia)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    disposition = 'attachment' if request.GET.get('dl') == '1' else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="orden_pedido_{pedido.numero_pedido}.pdf"'
    response.xframe_options_exempt = True
    return response


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
        form = OrdenPedidoForm(request.POST, instance=pedido, empresa=pedido.empresa)
        formset = ItemOrdenPedidoFormSet(request.POST, instance=pedido, empresa=pedido.empresa)
        
        if form.is_valid() and formset.is_valid():
            items_validos = [
                f for f in formset 
                if f.cleaned_data and not f.cleaned_data.get('DELETE') and f.cleaned_data.get('articulo')
            ]
            if not items_validos:
                messages.error(request, 'Debe ingresar al menos un producto en la orden de pedido.')
                articulos_empresa = articulos_con_stock(pedido.empresa)
                return render(request, 'pedidos/orden_pedido_form.html', {
                    'form': form,
                    'formset': formset,
                    'pedido': pedido,
                    'articulos_empresa': articulos_empresa,
                    'empresa': pedido.empresa,
                })

            pedido = form.save()
            formset.save()
            
            # Recalcular totales
            pedido.calcular_totales()
            
            messages.success(request, f'Orden de pedido {pedido.numero_pedido} actualizada exitosamente.')
            return redirect('pedidos:orden_pedido_detail', pk=pedido.pk)
        else:
            # Registrar errores para depuración
            with open(r'C:\PROYECTOS-WEB-SII\GestionCloud-SII\debug_errors.log', 'w') as f:
                f.write(f"UPDATE Form errors: {form.errors}\n")
                f.write(f"UPDATE Formset errors: {formset.errors}\n")
                f.write(f"UPDATE Formset non_form_errors: {formset.non_form_errors()}\n")
            
            # Avisar al usuario
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
    else:
        form = OrdenPedidoForm(instance=pedido, empresa=pedido.empresa)
        formset = ItemOrdenPedidoFormSet(instance=pedido, empresa=pedido.empresa)
    
    articulos_empresa = articulos_con_stock(pedido.empresa)
    
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
    pedido = get_object_or_404(OrdenPedido, pk=pk, empresa=request.empresa)
    return_url = request.POST.get('return_url') or request.GET.get('return_url') or reverse('pedidos:orden_pedido_list')
    
    # Verificar permisos
    if not (request.user.is_superuser or request.user.has_perm('pedidos.delete_ordenpedido')):
        messages.error(request, 'No tiene permisos para eliminar pedidos.')
        return redirect(return_url)
    
    # Validar si tiene despachos asociados
    if hasattr(pedido, 'despachos') and pedido.despachos.exists():
        messages.error(request, f'No se puede eliminar el pedido {pedido.numero_pedido} porque ya tiene órdenes de despacho asociadas.')
        return redirect(return_url)
    
    if request.method == 'POST':
        numero_pedido = pedido.numero_pedido
        try:
            pedido.delete()
            messages.success(request, f'Orden de pedido {numero_pedido} eliminada exitosamente.')
        except Exception as e:
            messages.error(request, f'No se pudo eliminar el pedido {numero_pedido}: {str(e)}')
        return redirect(return_url)
    
    context = {
        'pedido': pedido,
        'return_url': return_url,
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
