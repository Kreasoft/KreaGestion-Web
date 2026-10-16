from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum, Count, Prefetch
from django.db import transaction
from django.http import JsonResponse, HttpResponse, Http404
from django.utils import timezone
from django.urls import reverse
from django.template.loader import get_template
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from decimal import Decimal
from datetime import datetime, time, timedelta
from core.decorators import requiere_empresa, requiere_permiso, requiere_empresa_json
from core.fechas import fecha_documento_caja, resolver_fecha_vencimiento
from facturacion_electronica.ind_traslado import TIPO_DESPACHO_SII_CHOICES
from .models import (
    Vendedor, FormaPago, Venta, VentaDetalle, EstacionTrabajo, TerminalPOS, TIPO_DOCUMENTO_CHOICES,
    DispositivoMovil, SolicitudAccesoMovil, ensure_terminalpos_table, ensure_estacion_caja_impresion
)
from .telefono_app import (
    AUTH_OFFLINE_HOURS,
    emitir_token_app,
    formatear_telefono_cl,
    normalizar_telefono_cl,
    verificar_token_app,
)
from .forms import VendedorForm, FormaPagoForm, EstacionTrabajoForm
from articulos.models import Articulo, KitOferta
from clientes.models import Cliente
from empresas.models import Empresa
from inventario.models import TransferenciaInventario
import io
import re
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def print(*args, **kwargs):
    """Evita que mensajes de depuracion rompan vistas si stdout falla en Windows."""
    return None


def _sincronizar_config_estacion(request, estacion):
    """Siempre usa los parámetros actuales de la estación (no deja sesión vieja)."""
    request.session['pos_estacion_id'] = estacion.id
    request.session['pos_cierre_directo'] = bool(estacion.cierre_directo)
    request.session['pos_flujo_directo'] = str(estacion.flujo_cierre_directo or 'rut_final')
    request.session['pos_enviar_sii_directo'] = bool(estacion.enviar_sii_directo)
    request.session.modified = True


COOKIE_TERMINAL_POS = 'gc_pos_terminal'
COOKIE_TERMINAL_MAX_AGE = 60 * 60 * 24 * 400


def _token_terminal_request(request):
    return (request.COOKIES.get(COOKIE_TERMINAL_POS) or '').strip()


def _aplicar_sesion_pos(request, estacion, vendedor, bodega=None, nombre_estacion=None):
    request.session['pos_estacion_id'] = int(estacion.id)
    request.session['pos_estacion_nombre'] = str(estacion.nombre)
    request.session['pos_vendedor_id'] = int(vendedor.id)
    request.session['pos_vendedor_nombre'] = str(vendedor.nombre)
    if nombre_estacion:
        request.session['pos_nombre_estacion'] = str(nombre_estacion).strip()
    if bodega:
        request.session['pos_bodega_id'] = int(bodega.id)
        request.session['dashboard_bodega_id'] = int(bodega.id)
    _sincronizar_config_estacion(request, estacion)
    request.session.modified = True


def _buscar_terminal_pos(request):
    ensure_terminalpos_table()
    ensure_estacion_caja_impresion()
    token = _token_terminal_request(request)
    if not token:
        return None
    return TerminalPOS.objects.filter(
        empresa=request.empresa, token=token, activo=True
    ).select_related('estacion', 'vendedor', 'bodega', 'sucursal').first()


def _siguiente_codigo_terminal(empresa):
    n = TerminalPOS.objects.filter(empresa=empresa).count() + 1
    codigo = f'TER-{n:03d}'
    while TerminalPOS.objects.filter(empresa=empresa, codigo=codigo).exists():
        n += 1
        codigo = f'TER-{n:03d}'
    return codigo


def _guardar_cookie_terminal(response, token):
    response.set_cookie(
        COOKIE_TERMINAL_POS,
        token,
        max_age=COOKIE_TERMINAL_MAX_AGE,
        httponly=True,
        samesite='Lax',
        path='/',
    )
    return response


def _registrar_o_actualizar_terminal(request, estacion, vendedor, bodega=None, nombre=''):
    import secrets

    ensure_terminalpos_table()
    token = _token_terminal_request(request)
    terminal = None
    if token:
        terminal = TerminalPOS.objects.filter(empresa=request.empresa, token=token).first()
        if not terminal and TerminalPOS.objects.filter(token=token).exists():
            token = None
    if not token:
        token = secrets.token_urlsafe(32)
    sucursal = getattr(estacion, 'sucursal', None) or getattr(request, 'sucursal_activa', None)
    if terminal:
        terminal.estacion = estacion
        terminal.vendedor = vendedor
        terminal.bodega = bodega
        terminal.sucursal = sucursal
        if nombre:
            terminal.nombre = nombre[:120]
        terminal.activo = True
        terminal.ultimo_acceso = timezone.now()
        terminal.save()
    else:
        terminal = TerminalPOS.objects.create(
            empresa=request.empresa,
            sucursal=sucursal,
            estacion=estacion,
            bodega=bodega,
            vendedor=vendedor,
            codigo=_siguiente_codigo_terminal(request.empresa),
            nombre=(nombre or f'Equipo {estacion.nombre}')[:120],
            token=token,
            activo=True,
            ultimo_acceso=timezone.now(),
        )
    return terminal


def _bodega_para_venta(request, sucursal=None, estacion=None):
    """Bodega elegida en el equipo/POS, o la de la caja/sucursal."""
    from gestioncloud.views import bodegas_para_rebaja
    from caja.models import Caja

    caja = None
    if estacion is not None:
        caja = Caja.objects.filter(
            empresa=request.empresa, estacion_trabajo=estacion, activo=True
        ).first()
    if caja is None and sucursal is not None:
        caja = Caja.objects.filter(
            empresa=request.empresa, sucursal=sucursal, estacion_trabajo__isnull=True, activo=True
        ).first()
    bodega_id = request.session.get('pos_bodega_id') or request.session.get('dashboard_bodega_id')
    if not bodega_id:
        terminal = _buscar_terminal_pos(request)
        if terminal and terminal.bodega_id:
            bodega_id = terminal.bodega_id
    _, bodega = bodegas_para_rebaja(request, sucursal=sucursal, caja=caja, bodega_id=bodega_id)
    return bodega


def _apertura_caja_estacion(empresa, estacion, sucursal=None):
    """Apertura activa de la estación y sucursal; no toma cajas de otra sucursal ni de otra estación."""
    from caja.models import AperturaCaja, Caja

    qs = AperturaCaja.objects.filter(caja__empresa=empresa, estado='abierta').select_related('caja')
    if sucursal is not None:
        qs = qs.filter(caja__sucursal=sucursal)

    if estacion is not None:
        ap = qs.filter(caja__estacion_trabajo=estacion).first()
        if ap:
            return ap
        caja_qs = Caja.objects.filter(empresa=empresa, estacion_trabajo=estacion, activo=True)
        if sucursal is not None:
            caja_qs = caja_qs.filter(sucursal=sucursal)
        caja = caja_qs.first()
        if caja:
            ap = caja.get_apertura_activa()
            if ap:
                return ap
        # Caja compartida de la sucursal (sin estación asignada). Nunca una caja de otro TPV.
        return qs.filter(caja__estacion_trabajo__isnull=True).order_by('-fecha_apertura').first()

    return qs.order_by('-fecha_apertura').first()


def _estaciones_operativas(request, sucursal=None):
    ensure_estacion_caja_impresion()
    qs = EstacionTrabajo.objects.filter(empresa=request.empresa, activo=True)
    if sucursal is not None and getattr(sucursal, 'empresa_id', None) != getattr(request.empresa, 'id', None):
        sucursal = None
    if sucursal is not None:
        qs = qs.filter(Q(sucursal=sucursal) | Q(sucursal__isnull=True))
    return qs.order_by('numero')


def _sucursal_de_venta(request, estacion=None):
    if estacion is not None and getattr(estacion, 'sucursal_id', None):
        return estacion.sucursal
    from empresas.middleware import resolver_sucursal_operativa
    return resolver_sucursal_operativa(request)


def _finalizar_dte_cierre_directo(dte, venta_final, forma_pago=None, apertura=None):
    """Deja la boleta/factura oficial ligada al DTE para que salga en el libro de ventas."""
    if not dte or not venta_final:
        return

    fecha_doc = fecha_documento_caja(apertura)
    campos_venta = []
    if not venta_final.facturado:
        venta_final.facturado = True
        campos_venta.append('facturado')
    if venta_final.estado != 'confirmada':
        venta_final.estado = 'confirmada'
        campos_venta.append('estado')
    if forma_pago and not venta_final.forma_pago_id:
        venta_final.forma_pago = forma_pago
        campos_venta.append('forma_pago')
    if venta_final.fecha != fecha_doc:
        venta_final.fecha = fecha_doc
        campos_venta.append('fecha')
    if campos_venta:
        venta_final.save(update_fields=campos_venta)

    campos_dte = []
    if dte.venta_id != venta_final.id:
        dte.venta = venta_final
        campos_dte.append('venta')
    if dte.fecha_emision != fecha_doc:
        dte.fecha_emision = fecha_doc
        campos_dte.append('fecha_emision')
    if campos_dte:
        dte.save(update_fields=campos_dte)


def _es_forma_pago_efectivo(forma_pago):
    codigo = (getattr(forma_pago, 'codigo', '') or '').upper().strip()
    nombre = (getattr(forma_pago, 'nombre', '') or '').lower()
    return codigo in ('EF', 'EFE', 'EFECTIVO') or 'efectivo' in nombre


def _documento_requiere_pago(tipo_documento):
    return (tipo_documento or '').lower() in ('boleta', 'factura')


def _resolver_pagos_documento(empresa, tipo_documento, total, pagos_raw):
    """Valida cobro de boleta/factura. Guía, NC y ND no llevan pago."""
    tipo = (tipo_documento or '').lower()
    total = Decimal(str(total or 0))

    if not _documento_requiere_pago(tipo):
        return [], None

    if not pagos_raw:
        return None, 'Debe registrar el pago antes de emitir e imprimir.'

    pagos = []
    total_pagado = Decimal('0.00')
    total_no_efectivo = Decimal('0.00')

    for item in pagos_raw:
        if not isinstance(item, dict):
            continue
        fp_id = item.get('forma_pago_id') or item.get('id')
        try:
            fp_id = int(str(fp_id).strip())
        except (TypeError, ValueError):
            continue
        try:
            monto = Decimal(str(item.get('monto') or 0))
        except Exception:
            continue
        if monto <= 0:
            continue

        forma = FormaPago.objects.filter(pk=fp_id, empresa=empresa, activo=True).first()
        if not forma:
            return None, 'Hay una forma de pago inválida o inactiva.'
        if forma.es_cuenta_corriente and tipo != 'factura':
            return None, 'El crédito / cuenta corriente solo se permite en facturas. La boleta se cobra al contado.'

        pagos.append({'forma_pago': forma, 'monto': monto})
        total_pagado += monto
        if not _es_forma_pago_efectivo(forma):
            total_no_efectivo += monto

    if not pagos:
        return None, 'Debe ingresar al menos una forma de pago con monto.'

    if total_pagado + Decimal('0.50') < total:
        return None, (
            f'El pago (${total_pagado:,.0f}) es menor al total del documento (${total:,.0f}).'
        )

    if total_no_efectivo > total + Decimal('0.50'):
        return None, 'Los pagos que no son efectivo no pueden superar el total del documento.'

    return pagos, None


def _aplicar_pagos_cierre_directo(venta, apertura, pagos, tipo_doc, numero, usuario, dte=None):
    """Registra movimientos de caja y, solo en factura, el tramo a crédito en cuenta corriente."""
    from caja.models import MovimientoCaja

    tipo = (tipo_doc or '').lower()
    if not pagos or not _documento_requiere_pago(tipo):
        venta.monto_pagado = Decimal('0.00') if tipo == 'guia' else (venta.total or Decimal('0.00'))
        venta.saldo_pendiente = Decimal('0.00')
        venta.save(update_fields=['monto_pagado', 'saldo_pendiente'])
        return Decimal('0.00'), Decimal('0.00'), None

    primera = pagos[0]['forma_pago']
    forma_credito = None
    monto_credito = Decimal('0.00')
    total_pagado = Decimal('0.00')
    primer_movimiento = None

    for indice, pago in enumerate(pagos, start=1):
        descripcion = f"{tipo.title()} #{numero}"
        if len(pagos) > 1:
            descripcion += f" (Pago {indice}/{len(pagos)})"
        movimiento = MovimientoCaja.objects.create(
            apertura_caja=apertura,
            venta=venta,
            tipo='venta',
            forma_pago=pago['forma_pago'],
            monto=pago['monto'],
            descripcion=descripcion,
            usuario=usuario,
        )
        if primer_movimiento is None:
            primer_movimiento = movimiento
        total_pagado += pago['monto']
        if pago['forma_pago'].es_cuenta_corriente:
            forma_credito = pago['forma_pago']
            monto_credito += pago['monto']

    venta.forma_pago = forma_credito or primera
    if tipo == 'factura' and monto_credito > 0:
        venta.monto_pagado = max(Decimal('0.00'), (venta.total or Decimal('0.00')) - monto_credito)
        venta.saldo_pendiente = monto_credito
        venta.save(update_fields=['forma_pago', 'monto_pagado', 'saldo_pendiente'])
        from tesoreria.services import sincronizar_venta_credito_en_tesoreria
        sincronizar_venta_credito_en_tesoreria(
            venta,
            dte=dte,
            usuario=usuario,
            descripcion=f"Factura a crédito #{numero}",
        )
    else:
        venta.monto_pagado = venta.total or Decimal('0.00')
        venta.saldo_pendiente = Decimal('0.00')
        venta.save(update_fields=['forma_pago', 'monto_pagado', 'saldo_pendiente'])

    if apertura:
        apertura.calcular_totales()

    monto_cambio = max(Decimal('0.00'), total_pagado - (venta.total or Decimal('0.00')))
    return total_pagado, monto_cambio, primer_movimiento


# ========== VENDEDORES ==========

@login_required
@requiere_empresa
@permission_required('ventas.view_vendedor', raise_exception=True)
def vendedor_list(request):
    """Lista de vendedores y autorización de celulares para la app móvil."""
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'aprobar_solicitud':
            solicitud_id = request.POST.get('solicitud_id')
            vendedor_id = request.POST.get('vendedor_id')

            if not solicitud_id or not vendedor_id:
                messages.error(request, 'Datos incompletos para autorizar el dispositivo.')
                return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

            solicitud = get_object_or_404(SolicitudAccesoMovil, pk=solicitud_id, empresa=request.empresa)
            vendedor = get_object_or_404(Vendedor, pk=vendedor_id, empresa=request.empresa)

            ocupado = Vendedor.objects.filter(
                empresa=request.empresa, telefono_app=solicitud.telefono
            ).exclude(pk=vendedor.pk).first()
            if ocupado:
                messages.error(request, f'El número {solicitud.telefono_display} ya está asignado a {ocupado.nombre}.')
                return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

            vendedor.telefono_app = solicitud.telefono
            vendedor.app_movil_activa = True
            vendedor.app_movil_activado_en = timezone.now()
            vendedor.app_movil_revocado_en = None
            vendedor.save(update_fields=[
                'telefono_app', 'app_movil_activa', 'app_movil_activado_en', 'app_movil_revocado_en', 'fecha_modificacion'
            ])

            solicitud.estado = 'aprobada'
            solicitud.vendedor_asignado = vendedor
            solicitud.save(update_fields=['estado', 'vendedor_asignado', 'fecha_ultimo_intento'])

            messages.success(request, f'Celular {solicitud.telefono_display} asignado a {vendedor.nombre} y activado correctamente.')
            return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

        elif action == 'descartar_solicitud':
            solicitud_id = request.POST.get('solicitud_id')
            if not solicitud_id:
                messages.error(request, 'Solicitud no encontrada.')
                return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

            solicitud = get_object_or_404(SolicitudAccesoMovil, pk=solicitud_id, empresa=request.empresa)
            solicitud.estado = 'descartada'
            solicitud.save(update_fields=['estado', 'fecha_ultimo_intento'])

            messages.success(request, f'Solicitud de {solicitud.telefono_display} descartada.')
            return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

        elif action == 'save_telefono_app':
            vendedor_id = request.POST.get('device_vendedor_id')
            telefono = normalizar_telefono_cl(request.POST.get('telefono') or '')
            activar = request.POST.get('activar', 'on') == 'on'

            if not vendedor_id:
                messages.error(request, 'Seleccione el vendedor.')
                return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')
            if not telefono:
                messages.error(request, 'Ingrese un celular chileno, por ejemplo +56 9 63697225.')
                return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

            vendedor = Vendedor.objects.filter(pk=vendedor_id, empresa=request.empresa).first()
            if not vendedor:
                messages.error(request, 'Vendedor no encontrado.')
                return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

            ocupado = Vendedor.objects.filter(
                empresa=request.empresa, telefono_app=telefono
            ).exclude(pk=vendedor.pk).first()
            if ocupado:
                messages.error(request, f'El número {formatear_telefono_cl(telefono)} ya está en {ocupado.nombre}.')
                return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

            vendedor.telefono_app = telefono
            vendedor.app_movil_activa = activar
            if activar:
                vendedor.app_movil_activado_en = timezone.now()
                vendedor.app_movil_revocado_en = None
            else:
                vendedor.app_movil_revocado_en = timezone.now()
            vendedor.save(update_fields=[
                'telefono_app', 'app_movil_activa', 'app_movil_activado_en', 'app_movil_revocado_en', 'fecha_modificacion'
            ])

            # Si existía solicitud pendiente para este celular, actualizar estado
            if activar:
                SolicitudAccesoMovil.objects.filter(
                    empresa=request.empresa, telefono=telefono, estado='pendiente'
                ).update(estado='aprobada', vendedor_asignado=vendedor)

            estado = 'activo' if activar else 'registrado (sin acceso)'
            messages.success(request, f'Celular {formatear_telefono_cl(telefono)} de {vendedor.nombre}: {estado}.')
            return redirect(reverse('ventas:vendedor_list') + '?tab=telefonos')

    vendedores = Vendedor.objects.filter(empresa=request.empresa).order_by('codigo')

    search = request.GET.get('search', '')
    if search:
        vendedores = vendedores.filter(
            Q(codigo__icontains=search) |
            Q(nombre__icontains=search) |
            Q(telefono_app__icontains=re.sub(r'\D', '', search))
        )

    paginator = Paginator(vendedores, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    tel_q = (request.GET.get('tel') or '').strip()
    vendedores_tel = Vendedor.objects.filter(empresa=request.empresa).exclude(telefono_app='').order_by('nombre')
    if tel_q:
        digits = re.sub(r'\D', '', tel_q)
        vendedores_tel = vendedores_tel.filter(
            Q(nombre__icontains=tel_q) |
            Q(codigo__icontains=tel_q) |
            Q(telefono_app__icontains=digits)
        )

    # Solicitudes pendientes desde la App Móvil
    solicitudes_pendientes = SolicitudAccesoMovil.objects.filter(
        empresa=request.empresa, estado='pendiente'
    ).order_by('-fecha_ultimo_intento')
    solicitudes_pendientes_count = solicitudes_pendientes.count()

    pendientes_auth = Vendedor.objects.filter(
        empresa=request.empresa, telefono_app__gt='', app_movil_activa=False
    ).count()

    total_pendientes = solicitudes_pendientes_count + pendientes_auth

    context = {
        'page_obj': page_obj,
        'search': search,
        'vendedores_tel': vendedores_tel,
        'vendedores_activos': Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre'),
        'tab': request.GET.get('tab', 'vendedores'),
        'pendientes_auth': pendientes_auth,
        'solicitudes_pendientes': solicitudes_pendientes,
        'solicitudes_pendientes_count': solicitudes_pendientes_count,
        'total_pendientes': total_pendientes,
        'tel_q': tel_q,
        'auth_offline_hours': AUTH_OFFLINE_HOURS,
    }

    return render(request, 'ventas/vendedor_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_vendedor', raise_exception=True)
def vendedor_create(request):
    """Crear nuevo vendedor"""
    if request.method == 'POST':
        form = VendedorForm(request.POST)
        if form.is_valid():
            vendedor = form.save(commit=False)
            vendedor.empresa = request.empresa
            vendedor.save()
            messages.success(request, f'Vendedor {vendedor.nombre} creado exitosamente.')
            return redirect('ventas:vendedor_list')
        else:
            messages.error(request, 'Error al crear el vendedor. Por favor verifica los datos.')
            return redirect('ventas:vendedor_list')
    else:
        return redirect('ventas:vendedor_list')


@login_required
@requiere_empresa
@permission_required('ventas.view_vendedor', raise_exception=True)
def vendedor_detail(request, pk):
    """Detalle de vendedor - Fragmento para modal"""
    vendedor = get_object_or_404(Vendedor, pk=pk, empresa=request.empresa)
    return render(request, 'ventas/_vendedor_modal_detalle.html', {'vendedor': vendedor})


@login_required
@requiere_empresa
@permission_required('ventas.change_vendedor', raise_exception=True)
def vendedor_update(request, pk):
    """Editar vendedor - Fragmento para modal"""
    vendedor = get_object_or_404(Vendedor, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = VendedorForm(request.POST, instance=vendedor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Vendedor {vendedor.nombre} actualizado exitosamente.')
            from django.http import JsonResponse
            return JsonResponse({'success': True})
        else:
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'errors': form.errors})

    return render(request, 'ventas/_vendedor_modal_editar.html', {'vendedor': vendedor})


@login_required
@requiere_empresa
@permission_required('ventas.delete_vendedor', raise_exception=True)
def vendedor_delete(request, pk):
    """Eliminar vendedor"""
    vendedor = get_object_or_404(Vendedor, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nombre = vendedor.nombre
        vendedor.delete()
        from django.http import JsonResponse
        return JsonResponse({'success': True, 'message': f'Vendedor {nombre} eliminado exitosamente.'})
    
    from django.http import JsonResponse
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# ========== FORMAS DE PAGO ==========

@login_required
@requiere_empresa
@permission_required('ventas.view_formapago', raise_exception=True)
def formapago_list(request):
    """Lista de formas de pago"""
    formas_pago = FormaPago.objects.filter(empresa=request.empresa).order_by('codigo')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        formas_pago = formas_pago.filter(
            Q(codigo__icontains=search) |
            Q(nombre__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(formas_pago, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    
    return render(request, 'ventas/formapago_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_formapago', raise_exception=True)
def formapago_create(request):
    """Crear nueva forma de pago"""
    if request.method == 'POST':
        form = FormaPagoForm(request.POST)
        if form.is_valid():
            forma_pago = form.save(commit=False)
            forma_pago.empresa = request.empresa
            forma_pago.save()
            messages.success(request, f'Forma de pago {forma_pago.nombre} creada exitosamente.')
            return redirect('ventas:formapago_list')
    else:
        form = FormaPagoForm()
    
    context = {
        'form': form,
        'titulo': 'Crear Forma de Pago',
    }
    
    return render(request, 'ventas/formapago_form.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_formapago', raise_exception=True)
def formapago_detail(request, pk):
    """Detalle de forma de pago - Fragmento para modal"""
    forma_pago = get_object_or_404(FormaPago, pk=pk, empresa=request.empresa)
    
    html = f"""
    <div class="row">
        <div class="col-6 mb-3">
            <label class="text-muted small">Código</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{forma_pago.codigo}</p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Nombre</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{forma_pago.nombre}</p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Es Cuenta Corriente</label>
            <p class="mb-0">
                {'<span class="badge" style="background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%); color: #212529;"><i class="fas fa-check me-1"></i>Sí</span>' if forma_pago.es_cuenta_corriente else '<span class="badge" style="background: linear-gradient(135deg, #6c757d 0%, #545b62 100%); color: white;"><i class="fas fa-times me-1"></i>No</span>'}
            </p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Requiere Cheque</label>
            <p class="mb-0">
                {'<span class="badge" style="background: linear-gradient(135deg, #17a2b8 0%, #117a8b 100%); color: white;"><i class="fas fa-check me-1"></i>Sí</span>' if forma_pago.requiere_cheque else '<span class="badge" style="background: linear-gradient(135deg, #6c757d 0%, #545b62 100%); color: white;"><i class="fas fa-times me-1"></i>No</span>'}
            </p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Estado</label>
            <p class="mb-0">
                {'<span class="badge" style="background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%); color: white;">Activo</span>' if forma_pago.activo else '<span class="badge" style="background: linear-gradient(135deg, #dc3545 0%, #bd2130 100%); color: white;">Inactivo</span>'}
            </p>
        </div>
        <div class="col-6 mb-3">
            <label class="text-muted small">Fecha de Creación</label>
            <p class="mb-0" style="font-weight: 600; color: #2c3e50;">{forma_pago.fecha_creacion.strftime('%d-%m-%Y %H:%M')}</p>
        </div>
    </div>
    """
    
    from django.http import HttpResponse
    return HttpResponse(html)


@login_required
@requiere_empresa
@permission_required('ventas.change_formapago', raise_exception=True)
def formapago_update(request, pk):
    """Editar forma de pago - Fragmento para modal"""
    forma_pago = get_object_or_404(FormaPago, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = FormaPagoForm(request.POST, instance=forma_pago)
        if form.is_valid():
            form.save()
            messages.success(request, f'Forma de pago {forma_pago.nombre} actualizada exitosamente.')
            from django.http import JsonResponse
            return JsonResponse({'success': True})
        else:
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'errors': form.errors})
    
    from django.middleware.csrf import get_token
    csrf_token = get_token(request)
    
    html = f"""
    <form method="post" action="/ventas/formas-pago/{forma_pago.id}/editar/" id="formEditarFormaPagoSubmit">
        <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
        <div class="mb-3">
            <label class="form-label" style="font-weight: 600;">Código *</label>
            <input type="text" name="codigo" class="form-control" value="{forma_pago.codigo}" required>
        </div>
        <div class="mb-3">
            <label class="form-label" style="font-weight: 600;">Nombre *</label>
            <input type="text" name="nombre" class="form-control" value="{forma_pago.nombre}" required>
        </div>
        <div class="mb-3">
            <div class="form-check form-switch">
                <input type="checkbox" name="es_cuenta_corriente" class="form-check-input" id="esCuentaCorrienteEditar" {'checked' if forma_pago.es_cuenta_corriente else ''}>
                <label class="form-check-label" for="esCuentaCorrienteEditar">
                    Es Cuenta Corriente
                    <small class="text-muted d-block">Si está marcado, la factura pasa a cuenta corriente del cliente</small>
                </label>
            </div>
        </div>
        <div class="mb-3">
            <div class="form-check form-switch">
                <input type="checkbox" name="requiere_cheque" class="form-check-input" id="requiereChequeEditar" {'checked' if forma_pago.requiere_cheque else ''}>
                <label class="form-check-label" for="requiereChequeEditar">
                    Requiere Cheque
                    <small class="text-muted d-block">Si está marcado, se debe registrar información del cheque</small>
                </label>
            </div>
        </div>
        <div class="mb-3">
            <div class="form-check form-switch">
                <input type="checkbox" name="activo" class="form-check-input" id="activoEditar" {'checked' if forma_pago.activo else ''}>
                <label class="form-check-label" for="activoEditar">Forma de pago activa</label>
            </div>
        </div>
    </form>
    """
    
    from django.http import HttpResponse
    return HttpResponse(html)


@login_required
@requiere_empresa
@permission_required('ventas.delete_formapago', raise_exception=True)
def formapago_delete(request, pk):
    """Eliminar forma de pago"""
    forma_pago = get_object_or_404(FormaPago, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nombre = forma_pago.nombre
        forma_pago.delete()
        messages.success(request, f'Forma de pago {nombre} eliminada exitosamente.')
        return redirect('ventas:formapago_list')
    
    context = {
        'forma_pago': forma_pago,
    }
    
    return render(request, 'ventas/formapago_confirm_delete.html', context)


# ========== POS (PUNTO DE VENTA) ==========

@login_required
@requiere_empresa
def pos_main(request):
    """Vista principal del POS"""
    # Obtener datos necesarios
    clientes = Cliente.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    # Crear venta en borrador si no existe
    venta_actual, created = Venta.objects.get_or_create(
        empresa=request.empresa,
        numero_venta='TEMP',
        defaults={
            'fecha': timezone.localdate(),
            'usuario_creacion': request.user,
            'estado': 'borrador'
        }
    )
    
    context = {
        'clientes': clientes,
        'vendedores': vendedores,
        'formas_pago': formas_pago,
        'venta_actual': venta_actual,
    }
    
    return render(request, 'ventas/pos_main.html', context)


def _build_articulo_results(articulos, lista_precio_id, request):
    """Serializa un queryset de Artículo a lista de dicts para el POS."""
    from inventario.models import Stock
    from articulos.models import PrecioArticulo

    # Precios de lista
    precios_lista = {}
    if lista_precio_id:
        for p in PrecioArticulo.objects.filter(lista_precio_id=lista_precio_id, articulo__in=articulos).select_related('articulo'):
            precios_lista[p.articulo_id] = float(p.precio)

    articulo_ids = [articulo.id for articulo in articulos]
    stock_por_articulo = {
        row['articulo_id']: float(row['total'] or 0)
        for row in (
            Stock.objects.filter(
                empresa=request.empresa,
                articulo_id__in=articulo_ids,
                bodega__activa=True,
            )
            .values('articulo_id')
            .annotate(total=Sum('cantidad'))
        )
    }

    results = []
    for articulo in articulos:
        try:
            precio_neto = precios_lista.get(articulo.id, float(articulo._string_to_decimal(articulo.precio_venta)))
            iva = 0.0 if (articulo.categoria and articulo.categoria.exenta_iva) else precio_neto * 0.19
            impuesto_especifico = 0.0
            impuesto_esp_pct = 0
            if articulo.categoria and articulo.categoria.impuesto_especifico:
                try:
                    pct = float(articulo.categoria.impuesto_especifico.get_porcentaje_decimal())
                    impuesto_especifico = precio_neto * pct
                    impuesto_esp_pct = float(articulo.categoria.impuesto_especifico.porcentaje)
                except Exception:
                    pass
            precio_final = round(precio_neto + iva + impuesto_especifico)
            oferta_activa = bool(articulo.oferta_activa())
            precio_oferta = float(articulo.get_precio_oferta_decimal()) if oferta_activa else 0
            porcentaje_ahorro = float(articulo.get_porcentaje_ahorro()) if oferta_activa else 0
            precio_pos = round(precio_oferta) if precio_oferta > 0 else precio_final
            factor_total = 1 + (0 if (articulo.categoria and articulo.categoria.exenta_iva) else 0.19) + (impuesto_esp_pct / 100)
            precio_neto_pos = (precio_pos / factor_total) if factor_total > 0 else precio_neto

            stock_disponible = stock_por_articulo.get(articulo.id, 0.0)

            results.append({
                'id': articulo.id,
                'codigo': articulo.codigo or '',
                'codigo_barras': articulo.codigo_barras or '',
                'nombre': articulo.nombre or '',
                'descripcion': articulo.descripcion or articulo.nombre or '',
                'precio': precio_pos,
                'precio_normal': precio_final,
                'precio_neto': precio_neto_pos,
                'stock': stock_disponible,
                'control_stock': bool(getattr(articulo, 'control_stock', True)),
                'categoria_nombre': articulo.categoria.nombre if articulo.categoria else 'Sin Categoría',
                'categoria_exenta_iva': articulo.categoria.exenta_iva if articulo.categoria else False,
                'impuesto_especifico_porcentaje': impuesto_esp_pct,
                'en_oferta': oferta_activa,
                'precio_oferta': precio_oferta,
                'porcentaje_ahorro': porcentaje_ahorro,
            })
        except Exception as e:
            print(f"Error procesando artículo {articulo.id}: {e}")
            continue
    return results


@login_required
@requiere_empresa
def pos_buscar_articulo(request):
    """API para buscar artículos en el POS.

    Parámetros GET:
        q           – texto de búsqueda (código, nombre, descripción, código de barras)
        categoria   – ID o nombre exacto de categoría para filtrar (opcional)
        lista_precio – ID de lista de precios (opcional)

    Siempre opera sobre TODA la base de datos de la empresa (sin límite de 20).
    """
    try:
        query = request.GET.get('q', '').strip()
        lista_precio_id = request.GET.get('lista_precio', '').strip()
        categoria_param = request.GET.get('categoria', '').strip()
        modo_f10 = str(request.GET.get('f10') or '').strip().lower() in ('1', 'true', 'si')

        categoria_filter = Q()
        if categoria_param:
            if categoria_param.isdigit():
                categoria_filter = Q(categoria_id=int(categoria_param))
            else:
                categoria_filter = Q(categoria__nombre=categoria_param)

        # ── Filtro por categoría sin texto de búsqueda ────────────────────────
        if not query and categoria_param:
            print(f"[POS BUSCAR] Filtrando por categoría: '{categoria_param}'")
            articulos = Articulo.objects.filter(
                empresa=request.empresa,
                activo=True,
            ).filter(
                categoria_filter
            ).select_related('categoria', 'categoria__impuesto_especifico').order_by('nombre')
            print(f"[POS BUSCAR] Artículos en categoría '{categoria_param}': {articulos.count()}")
            return JsonResponse({'articulos': _build_articulo_results(articulos, lista_precio_id, request)})

        if not query:
            if modo_f10:
                articulos = list(Articulo.objects.filter(
                    empresa=request.empresa,
                    activo=True,
                ).select_related('categoria', 'categoria__impuesto_especifico').order_by('nombre')[:400])
                return JsonResponse({'articulos': _build_articulo_results(articulos, lista_precio_id, request)})
            return JsonResponse({'articulos': []})

        # ── Detectar código comodín ────────────────────────────────────────────
        estacion_id = request.session.get('pos_estacion_id')
        query_limpio = query.upper().strip()
        if estacion_id:
            try:
                estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa)
                if query_limpio == (estacion.codigo_comodin or '999999').upper().strip():
                    return JsonResponse({'es_comodin': True, 'codigo_comodin': estacion.codigo_comodin or '999999', 'articulos': []})
            except EstacionTrabajo.DoesNotExist:
                pass
        for estacion in EstacionTrabajo.objects.filter(empresa=request.empresa, activo=True):
            if query_limpio == (estacion.codigo_comodin or '999999').upper().strip():
                return JsonResponse({'es_comodin': True, 'codigo_comodin': estacion.codigo_comodin or '999999', 'articulos': []})

        # ── Búsqueda de texto completa sobre toda la BD ───────────────────────
        print(f"[POS BUSCAR] Búsqueda texto: '{query}' | Categoría: '{categoria_param}'")
        articulos_qs = Articulo.objects.filter(
            empresa=request.empresa,
            activo=True
        ).filter(
            Q(codigo_barras__icontains=query) |
            Q(codigo__icontains=query) |
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query)
        )
        if categoria_param:
            articulos_qs = articulos_qs.filter(categoria_filter)

        articulos = articulos_qs.select_related('categoria', 'categoria__impuesto_especifico').order_by('nombre')
        if modo_f10:
            articulos = list(articulos[:400])
        print(f"[POS BUSCAR] Resultados: {len(articulos) if modo_f10 else articulos.count()}")
        return JsonResponse({'articulos': _build_articulo_results(articulos, lista_precio_id, request)})

    except Exception as e:
        print(f"Error en pos_buscar_articulo: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e), 'articulos': []}, status=500)


@login_required
@requiere_empresa
def pos_agregar_articulo(request):
    """API para agregar un artículo a la venta actual"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    articulo_id = request.POST.get('articulo_id')
    cantidad = request.POST.get('cantidad', '1')
    venta_id = request.POST.get('venta_id')
    
    try:
        articulo = Articulo.objects.get(id=articulo_id, empresa=request.empresa)
        venta = Venta.objects.get(id=venta_id, empresa=request.empresa)
        cantidad = Decimal(cantidad)
        
        if cantidad <= 0:
            return JsonResponse({'success': False, 'error': 'La cantidad debe ser mayor a 0'})
        
        # Verificar stock disponible si el artículo tiene control de stock
        if articulo.control_stock:
            stock_disponible = articulo.stock_disponible
            
            # Verificar si el artículo ya está en la venta para calcular el total
            detalle_existente = VentaDetalle.objects.filter(venta=venta, articulo=articulo).first()
            cantidad_en_venta = detalle_existente.cantidad if detalle_existente else Decimal('0')
            cantidad_total = cantidad_en_venta + cantidad
            
            if cantidad_total > stock_disponible:
                return JsonResponse({
                    'success': False, 
                    'error': f'Stock insuficiente. Disponible: {stock_disponible}, Solicitado: {cantidad_total}'
                })
        
        # Obtener precio considerando cliente (si existe)
        from .utils_precios import obtener_precio_articulo
        precio_unitario = obtener_precio_articulo(
            articulo=articulo,
            cliente=venta.cliente if venta.cliente else None,
            empresa=request.empresa
        )
        
        # Verificar si el artículo ya está en la venta
        detalle_existente = VentaDetalle.objects.filter(venta=venta, articulo=articulo).first()
        
        if detalle_existente:
            # Actualizar cantidad
            detalle_existente.cantidad += cantidad
            detalle_existente.save()
        else:
            # Crear nuevo detalle con precio especial si aplica
            VentaDetalle.objects.create(
                venta=venta,
                articulo=articulo,
                cantidad=cantidad,
                precio_unitario=precio_unitario
            )
        
        return JsonResponse({'success': True})
        
    except Articulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Artículo no encontrado'})
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Venta no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@requiere_empresa
def pos_actualizar_detalle(request):
    """API para actualizar un detalle de la venta"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    detalle_id = request.POST.get('detalle_id')
    cantidad = request.POST.get('cantidad')
    
    try:
        detalle = VentaDetalle.objects.get(id=detalle_id, venta__empresa=request.empresa)
        cantidad = Decimal(cantidad)
        
        if cantidad <= 0:
            return JsonResponse({'success': False, 'error': 'La cantidad debe ser mayor a 0'})
        
        # Verificar stock disponible si el artículo tiene control de stock
        if detalle.articulo.control_stock:
            stock_disponible = detalle.articulo.stock_disponible
            
            if cantidad > stock_disponible:
                return JsonResponse({
                    'success': False, 
                    'error': f'Stock insuficiente. Disponible: {stock_disponible}, Solicitado: {cantidad}'
                })
        
        detalle.cantidad = cantidad
        detalle.save()
        
        return JsonResponse({'success': True})
        
    except VentaDetalle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Detalle no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@requiere_empresa
def pos_eliminar_detalle(request):
    """API para eliminar un detalle de la venta"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    detalle_id = request.POST.get('detalle_id')
    
    try:
        detalle = VentaDetalle.objects.get(id=detalle_id, venta__empresa=request.empresa)
        detalle.delete()
        
        return JsonResponse({'success': True})
        
    except VentaDetalle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Detalle no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@requiere_empresa
def pos_actualizar_venta(request):
    """API para actualizar datos de la venta (cliente, vendedor, etc.)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    venta_id = request.POST.get('venta_id')
    cliente_id = request.POST.get('cliente_id', '')
    vendedor_id = request.POST.get('vendedor_id', '')
    forma_pago_id = request.POST.get('forma_pago_id', '')
    descuento = request.POST.get('descuento', '0')
    
    try:
        venta = Venta.objects.get(id=venta_id, empresa=request.empresa)
        
        # Actualizar campos
        if cliente_id:
            cliente = Cliente.objects.get(id=cliente_id, empresa=request.empresa)
            venta.cliente = cliente
        else:
            venta.cliente = None
            
        if vendedor_id:
            vendedor = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa)
            venta.vendedor = vendedor
        else:
            venta.vendedor = None
            
        if forma_pago_id:
            forma_pago = FormaPago.objects.get(id=forma_pago_id, empresa=request.empresa)
            venta.forma_pago = forma_pago
        else:
            venta.forma_pago = None
        
        venta.descuento = Decimal(descuento)
        venta.save()
        
        return JsonResponse({'success': True})
        
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Venta no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@requiere_empresa
def pos_detalles_venta(request, venta_id):
    """API para obtener los detalles de una venta"""
    try:
        venta = Venta.objects.get(id=venta_id, empresa=request.empresa)
        detalles = VentaDetalle.objects.filter(venta=venta).select_related('articulo')
        
        detalles_data = []
        for detalle in detalles:
            detalles_data.append({
                'id': detalle.id,
                'cantidad': float(detalle.cantidad),
                'precio_unitario': float(detalle.precio_unitario),
                'precio_total': float(detalle.precio_total),
                'impuesto_especifico': float(detalle.impuesto_especifico),
                'articulo': {
                    'codigo': detalle.articulo.codigo,
                    'descripcion': detalle.articulo.descripcion,
                }
            })
        
        totales_data = {
            'subtotal': float(venta.subtotal),
            'descuento': float(venta.descuento),
            'neto': float(venta.neto),
            'iva': float(venta.iva),
            'impuesto_especifico': float(venta.impuesto_especifico),
            'total': float(venta.total),
        }
        
        return JsonResponse({
            'success': True,
            'detalles': detalles_data,
            'totales': totales_data
        })
        
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Venta no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ========== PUNTO DE VENTA (POS) ==========

@login_required
@requiere_empresa
@permission_required('ventas.add_venta', raise_exception=True)
def pos_view(request):
    """Vista principal del Punto de Venta"""
    ensure_estacion_caja_impresion()
    from articulos.models import Articulo, CategoriaArticulo
    from clientes.models import Cliente
    from caja.models import Caja
    from caja.forms import AperturaCajaForm
    from django.contrib import messages
    from django.shortcuts import render
    
    # DEBUG CRÍTICO: Verificar sesión POS
    print("[DEBUG] ==================== POS VIEW ====================")
    print(f"[DEBUG] Session Key: {request.session.session_key}")
    print(f"[DEBUG] pos_estacion_id en sesion: {request.session.get('pos_estacion_id')}")
    print(f"[DEBUG] pos_vendedor_id en sesion: {request.session.get('pos_vendedor_id')}")
    
    # VALIDAR SESIÓN POS ANTES DE CONTINUAR
    estacion_id = request.session.get('pos_estacion_id')
    vendedor_id = request.session.get('pos_vendedor_id')
    
    if not estacion_id or not vendedor_id:
        terminal = _buscar_terminal_pos(request)
        if (
            terminal
            and terminal.estacion_id
            and terminal.vendedor_id
            and terminal.estacion.activo
            and terminal.vendedor.activo
        ):
            _aplicar_sesion_pos(
                request, terminal.estacion, terminal.vendedor, terminal.bodega,
                nombre_estacion=terminal.nombre,
            )
            request.session.save()
            estacion_id = terminal.estacion_id
            vendedor_id = terminal.vendedor_id
        else:
            print("[ERROR] Sesion POS perdida - Redirigiendo a seleccion")
            messages.warning(request, 'Sesión POS perdida. Por favor, seleccione estación y vendedor nuevamente.')
            return redirect('ventas:pos_seleccion')
    
    print(f"[OK] Sesion POS valida - Estacion ID: {estacion_id}, Vendedor ID: {vendedor_id}")
    
    # VALIDACIÓN CRÍTICA: Verificar que haya sucursal activa
    # El encabezado puede mostrar sucursal (selector / fallback) aunque el
    # middleware deje request.sucursal_activa vacío ("Todas las sucursales").
    from empresas.middleware import resolver_sucursal_operativa
    sucursal_activa = resolver_sucursal_operativa(request)
    if not sucursal_activa:
        context = {
            'mostrar_alerta_sucursal': True,
            'mensaje_error': 'No puede operar en el POS sin una sucursal asignada',
            'mensaje_detalle': 'Contacte al administrador para que le asigne una sucursal en su perfil de usuario.'
        }
        return render(request, 'ventas/pos_sin_sucursal.html', context)
    request.sucursal_activa = sucursal_activa
    
    # Verificar caja abierta de esta estación/sucursal (no de otra sucursal)
    apertura_activa = _apertura_caja_estacion(request.empresa, None, sucursal_activa)
    estacion_id_sesion = request.session.get('pos_estacion_id')
    if estacion_id_sesion:
        try:
            est_sesion = EstacionTrabajo.objects.get(id=estacion_id_sesion, empresa=request.empresa)
            apertura_activa = _apertura_caja_estacion(request.empresa, est_sesion, sucursal_activa)
        except EstacionTrabajo.DoesNotExist:
            pass
    
    # Si no hay caja abierta, preparar formulario de apertura
    mostrar_modal_apertura = False
    form_apertura = None
    if not apertura_activa:
        mostrar_modal_apertura = True
        form_apertura = AperturaCajaForm(empresa=request.empresa, sucursal=sucursal_activa)
    
    def preparar_articulo_pos(articulo):
        precio_neto = float(articulo._string_to_decimal(articulo.precio_venta))
        
        # Calcular IVA solo si la categoría NO está exenta
        if articulo.categoria and articulo.categoria.exenta_iva:
            iva = 0.0
        else:
            iva = precio_neto * 0.19
        
        # Calcular impuesto específico si aplica
        impuesto_especifico = 0.0
        if articulo.categoria and articulo.categoria.impuesto_especifico:
            porcentaje_decimal = float(articulo.categoria.impuesto_especifico.get_porcentaje_decimal()) / 100
            impuesto_especifico = precio_neto * porcentaje_decimal
        
        precio_final = round(precio_neto + iva + impuesto_especifico)
        articulo.precio_final_calculado = precio_final
        oferta_activa = bool(articulo.oferta_activa())
        precio_oferta = float(articulo.get_precio_oferta_decimal()) if oferta_activa else 0
        articulo.oferta_pos_activa = bool(oferta_activa and precio_oferta > 0)
        articulo.precio_oferta_pos = round(precio_oferta) if articulo.oferta_pos_activa else 0
        articulo.precio_pos_calculado = articulo.precio_oferta_pos if articulo.oferta_pos_activa else precio_final
        factor_total = 1 + (0 if (articulo.categoria and articulo.categoria.exenta_iva) else 0.19)
        if articulo.categoria and articulo.categoria.impuesto_especifico:
            factor_total += float(articulo.categoria.impuesto_especifico.porcentaje or 0) / 100
        articulo.precio_neto_pos = (articulo.precio_pos_calculado / factor_total) if factor_total > 0 else precio_neto
        return articulo

    # Obtener datos para el POS con impuesto específico incluido
    # Limitar a 20 para máxima velocidad inicial. El resto se busca por AJAX.
    articulos_queryset = Articulo.objects.filter(empresa=request.empresa, activo=True).select_related('categoria', 'categoria__impuesto_especifico').order_by('-id')[:20]
    
    # Calcular precios finales directamente en la vista
    articulos = []
    for articulo in articulos_queryset:
        preparar_articulo_pos(articulo)
        articulos.append(articulo)

    ofertas_queryset = Articulo.objects.filter(
        empresa=request.empresa,
        activo=True,
        en_oferta=True,
    ).select_related('categoria', 'categoria__impuesto_especifico').order_by('nombre')
    ofertas = []
    for articulo in ofertas_queryset:
        preparar_articulo_pos(articulo)
        ofertas.append(articulo)
        
    # Mejorar la velocidad inicial: limitar clientes iniciales a los 50 más recientes para evitar colapso de memoria
    clientes = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('-id')[:50]
    
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    vendedores_pos = [
        {'id': v.id, 'codigo': v.codigo or '', 'nombre': v.nombre}
        for v in vendedores
    ]
    formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    formas_pago_pos = [
        {
            'id': fp.id,
            'nombre': fp.nombre,
            'codigo': fp.codigo or '',
            'es_cuenta_corriente': bool(fp.es_cuenta_corriente),
            'es_efectivo': (
                (fp.codigo or '').upper() in ('EF', 'EFE', 'EFECTIVO')
                or 'efectivo' in (fp.nombre or '').lower()
            ),
        }
        for fp in formas_pago
    ]
    estaciones = _estaciones_operativas(request, sucursal_activa).order_by('numero')
    
    # Detectar modo POS de la estación activa
    modo_pos = 'normal'  # Default
    estacion_activa = None
    estacion_id = request.session.get('pos_estacion_id')
    
    if estacion_id:
        try:
            estacion_activa = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa)
            modo_pos = estacion_activa.modo_pos
            # Cierre directo + RUT al inicio: pedir cliente antes de vender
            if estacion_activa.cierre_directo and estacion_activa.flujo_cierre_directo == 'rut_inicio':
                modo_pos = 'con_cliente'
            _sincronizar_config_estacion(request, estacion_activa)
        except EstacionTrabajo.DoesNotExist:
            pass
    
    # Generar próximo número de venta basado en el correlativo de la estación actual
    # CRÍTICO: Debe mostrar el siguiente número que se asignará al próximo vale de esta estación
    print(f"[DEBUG POS] Estación ID en sesión: {estacion_id}")
    print(f"[DEBUG POS] Estación activa encontrada: {estacion_activa}")
    
    if estacion_activa:
        # Usar el correlativo actual de la estación (sin incrementar, solo para mostrar)
        # IMPORTANTE: Refrescar desde la BD para asegurar que tenemos el valor más actualizado
        estacion_activa.refresh_from_db()
        correlativo_actual = estacion_activa.correlativo_ticket
        proximo_numero = f"{correlativo_actual:06d}"
        print(f"[DEBUG POS] Estación: {estacion_activa.nombre}, Correlativo actual: {correlativo_actual}, Próximo número mostrado: {proximo_numero}")
    else:
        # Fallback si no hay estación activa - usar último vale de la empresa
        print(f"[DEBUG POS] No hay estación activa, usando fallback")
        ultima_venta = Venta.objects.filter(empresa=request.empresa, tipo_documento='vale').order_by('-numero_venta').first()
        if ultima_venta:
            try:
                numero_actual = int(ultima_venta.numero_venta)
                proximo_numero = f"{numero_actual + 1:06d}"
                print(f"[DEBUG POS] Fallback: Último vale encontrado: {ultima_venta.numero_venta}, Próximo: {proximo_numero}")
            except ValueError:
                proximo_numero = "000001"
                print(f"[DEBUG POS] Fallback: Error al convertir número, usando 000001")
        else:
            proximo_numero = "000001"
            print(f"[DEBUG POS] Fallback: No hay vales, usando 000001")
    
    print(f"[DEBUG POS] NÚMERO FINAL QUE SE MOSTRARÁ EN EL POS: {proximo_numero}")
    
    # Cargar kits de ofertas disponibles
    kits = KitOferta.objects.filter(
        empresa=request.empresa,
        activo=True
    ).prefetch_related('items__articulo').order_by('-destacado', 'nombre')[:10]
    
    # Filtrar solo kits vigentes (sin requerir stock - el stock se valida al agregar al carrito)
    kits_disponibles = [kit for kit in kits if kit.activo and kit.esta_vigente]

    # Cargar TODAS las categorías que tengan al menos un artículo activo en esta empresa
    # (para el filtro de categorías, independiente de los 20 artículos iniciales del DOM)
    categorias_activas = CategoriaArticulo.objects.filter(
        empresa=request.empresa,
        articulo__activo=True
    ).distinct().order_by('nombre')
    
    context = {
        'articulos': articulos,
        'ofertas': ofertas,
        'categorias': categorias_activas,       # <- TODAS las categorías con artículos
        'clientes': clientes,
        'vendedores': vendedores,
        'vendedores_pos': vendedores_pos,
        'formas_pago': formas_pago,
        'formas_pago_pos': formas_pago_pos,
        'estaciones': estaciones,
        'proximo_numero': proximo_numero,
        'apertura_activa': apertura_activa,
        'mostrar_modal_apertura': mostrar_modal_apertura,
        'form_apertura': form_apertura,
        'modo_pos': modo_pos,
        'estacion_activa': estacion_activa,
        'nombre_estacion_pos': (request.session.get('pos_nombre_estacion') or '').strip(),
        'kits': kits_disponibles,
        'max_descuento_lineal': request.empresa.max_descuento_lineal,
        'max_descuento_total': request.empresa.max_descuento_total,
    }
    
    return render(request, 'ventas/pos.html', context)


@login_required
@requiere_empresa
def pos_seleccion_estacion(request):
    """Vista para seleccionar estación de trabajo y vendedor"""
    from bodegas.models import Bodega
    from empresas.middleware import resolver_sucursal_operativa
    sucursal_activa = resolver_sucursal_operativa(request)
    terminal = _buscar_terminal_pos(request)
    cambiar = request.GET.get('cambiar') == '1'

    if (
        terminal
        and terminal.estacion_id
        and terminal.vendedor_id
        and terminal.estacion.activo
        and terminal.vendedor.activo
        and not cambiar
    ):
        _aplicar_sesion_pos(
            request, terminal.estacion, terminal.vendedor, terminal.bodega,
            nombre_estacion=terminal.nombre,
        )
        request.session.save()
        terminal.ultimo_acceso = timezone.now()
        terminal.save(update_fields=['ultimo_acceso'])
        response = redirect('ventas:pos_view')
        return _guardar_cookie_terminal(response, terminal.token)

    estaciones = _estaciones_operativas(request, sucursal_activa)
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).select_related('sucursal').order_by('nombre')
    if sucursal_activa:
        bodegas_sucursal = bodegas.filter(Q(sucursal=sucursal_activa) | Q(sucursal__isnull=True))
        if bodegas_sucursal.exists():
            bodegas = bodegas_sucursal

    context = {
        'estaciones': estaciones,
        'vendedores': vendedores,
        'bodegas': bodegas,
        'sucursal_activa': sucursal_activa,
        'terminal': terminal,
        'nombre_equipo': (terminal.nombre if terminal else '') or '',
        'estacion_seleccionada_id': terminal.estacion_id if terminal else None,
        'vendedor_seleccionado_id': terminal.vendedor_id if terminal else None,
        'bodega_seleccionada_id': terminal.bodega_id if terminal else None,
    }
    
    return render(request, 'ventas/pos_seleccion.html', context)


@login_required
@requiere_empresa
def pos_iniciar(request):
    """Iniciar POS con estación y vendedor seleccionados"""
    print("[DEBUG] ==================== POS INICIAR ====================")
    print(f"[DEBUG] Metodo: {request.method}")
    print(f"[DEBUG] Usuario: {request.user}")
    print(f"[DEBUG] Empresa: {request.empresa}")
    print(f"[DEBUG] Session Key ANTES: {request.session.session_key}")
    
    if request.method == 'POST':
        estacion_id = request.POST.get('estacion_id')
        vendedor_id = request.POST.get('vendedor_id')
        bodega_id = (request.POST.get('bodega_id') or '').strip()
        
        print(f"[DEBUG] POST - Estacion ID: {estacion_id}")
        print(f"[DEBUG] POST - Vendedor ID: {vendedor_id}")
        
        if not estacion_id or not vendedor_id:
            print("[ERROR] Estacion o vendedor no proporcionados")
            return JsonResponse({'success': False, 'message': 'Debe seleccionar estación y vendedor'})
        
        try:
            estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa, activo=True)
            vendedor = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa, activo=True)
            from empresas.middleware import resolver_sucursal_operativa
            sucursal_pos = resolver_sucursal_operativa(request)
            if sucursal_pos and estacion.sucursal_id and estacion.sucursal_id != sucursal_pos.id:
                return JsonResponse({'success': False, 'message': 'La estación no pertenece a la sucursal activa'})
            
            print(f"[DEBUG] Estacion encontrada: {estacion.nombre}")
            print(f"[DEBUG] Vendedor encontrado: {vendedor.nombre}")
            
            # Guardar en sesión CON CICLO ASEGURADO
            bodega = None
            if bodega_id:
                from bodegas.models import Bodega
                bodega = Bodega.objects.filter(pk=bodega_id, empresa=request.empresa, activa=True).first()
            nombre_equipo = (request.POST.get('nombre_equipo') or '').strip()
            _aplicar_sesion_pos(request, estacion, vendedor, bodega, nombre_estacion=nombre_equipo)
            terminal = _registrar_o_actualizar_terminal(
                request, estacion, vendedor, bodega=bodega, nombre=nombre_equipo
            )
            
            # TRIPLE GUARDADO FORZADO (evitar race conditions)
            request.session.modified = True
            request.session.save()
            
            # Verificar que se guardó
            print(f"[DEBUG] Verificando guardado...")
            print(f"[DEBUG] - pos_estacion_id: {request.session.get('pos_estacion_id')}")
            print(f"[DEBUG] - pos_vendedor_id: {request.session.get('pos_vendedor_id')}")
            print(f"[DEBUG] - pos_estacion_nombre: {request.session.get('pos_estacion_nombre')}")
            print(f"[DEBUG] - pos_vendedor_nombre: {request.session.get('pos_vendedor_nombre')}")
            print(f"[DEBUG] Session Key DESPUES: {request.session.session_key}")
            print("[OK] Sesion guardada exitosamente")
            
            response = JsonResponse({
                'success': True, 
                'message': f'POS iniciado - Estación: {estacion.nombre}, Vendedor: {vendedor.nombre}',
                'redirect_url': reverse('ventas:pos_view'),
                'debug': {
                    'session_key': request.session.session_key,
                    'estacion_id': estacion.id,
                    'vendedor_id': vendedor.id
                }
            })
            return _guardar_cookie_terminal(response, terminal.token)
            
        except (EstacionTrabajo.DoesNotExist, Vendedor.DoesNotExist) as e:
            print(f"[ERROR] Estacion o vendedor no encontrados: {e}")
            return JsonResponse({'success': False, 'message': 'Estación o vendedor no válidos'})
        except Exception as e:
            print(f"[ERROR] Error inesperado en pos_iniciar: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
def pos_cambiar_estacion(request):
    """Cambiar la estación de trabajo en el POS sin reiniciar"""
    if request.method == 'POST':
        estacion_id = request.POST.get('estacion_id')
        
        if not estacion_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar una estación'})
        
        try:
            estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa, activo=True)
            from empresas.middleware import resolver_sucursal_operativa
            sucursal_pos = resolver_sucursal_operativa(request)
            if sucursal_pos and estacion.sucursal_id and estacion.sucursal_id != sucursal_pos.id:
                return JsonResponse({'success': False, 'message': 'La estación no pertenece a la sucursal activa'})
            
            # Actualizar estación en la sesión (mantener el vendedor)
            request.session['pos_estacion_id'] = int(estacion.id)
            request.session['pos_estacion_nombre'] = str(estacion.nombre)
            _sincronizar_config_estacion(request, estacion)
            
            request.session.modified = True
            request.session.save()

            terminal = _buscar_terminal_pos(request)
            if terminal:
                terminal.estacion = estacion
                if estacion.sucursal_id:
                    terminal.sucursal = estacion.sucursal
                terminal.ultimo_acceso = timezone.now()
                terminal.save(update_fields=['estacion', 'sucursal', 'ultimo_acceso'])
            
            # Obtener información completa de la estación para el frontend
            from facturacion_electronica.models import ArchivoCAF
            
            folios_factura = 0
            folios_boleta = 0
            folios_guia = 0
            
            try:
                caf_factura = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='33',
                    estado='activo'
                ).first()
                if caf_factura:
                    folios_factura = caf_factura.folio_hasta - caf_factura.folio_actual + 1
                
                caf_boleta = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='39',
                    estado='activo'
                ).first()
                if caf_boleta:
                    folios_boleta = caf_boleta.folio_hasta - caf_boleta.folio_actual + 1
                
                caf_guia = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='52',
                    estado='activo'
                ).first()
                if caf_guia:
                    folios_guia = caf_guia.folio_hasta - caf_guia.folio_actual + 1
            except Exception:
                pass
            
            return JsonResponse({
                'success': True,
                'message': f'Estación cambiada a: {estacion.nombre}',
                'cierre_directo': bool(estacion.cierre_directo),
                'enviar_sii_directo': bool(estacion.enviar_sii_directo),
                'flujo_directo': str(estacion.flujo_cierre_directo or 'rut_final'),
                'estacion': {
                    'id': estacion.id,
                    'numero': estacion.numero,
                    'nombre': estacion.nombre,
                    'modo_pos': estacion.modo_pos,
                    'cierre_directo': estacion.cierre_directo,
                    'enviar_sii_directo': estacion.enviar_sii_directo,
                    'flujo_cierre_directo': estacion.flujo_cierre_directo,
                    'tipos_documentos': estacion.get_tipos_documentos_permitidos(),
                    'folios_factura': folios_factura,
                    'folios_boleta': folios_boleta,
                    'folios_guia': folios_guia,
                },
                'estacion_nombre': estacion.nombre,
            })
        except EstacionTrabajo.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Estación no válida'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    # GET: Devolver lista de estaciones disponibles
    from empresas.middleware import resolver_sucursal_operativa
    estaciones = _estaciones_operativas(request, resolver_sucursal_operativa(request)).order_by('numero')
    estaciones_data = []
    for est in estaciones:
        estaciones_data.append({
            'id': est.id,
            'numero': est.numero,
            'nombre': est.nombre,
            'modo_pos': est.get_modo_pos_display(),
        })
    
    return JsonResponse({
        'success': True,
        'estaciones': estaciones_data,
        'estacion_actual_id': request.session.get('pos_estacion_id')
    })


@login_required
@requiere_empresa
def pos_session_info(request):
    """Obtener información de la sesión del POS"""
    try:
        print("[DEBUG] ==================== POS SESSION INFO ====================")
        print(f"[DEBUG] Usuario: {request.user}")
        print(f"[DEBUG] Empresa: {request.empresa}")
        
        estacion_id = request.session.get('pos_estacion_id')
        vendedor_id = request.session.get('pos_vendedor_id')
        estacion_nombre = request.session.get('pos_estacion_nombre')
        vendedor_nombre = request.session.get('pos_vendedor_nombre')
        
        print(f"[DEBUG] Estacion ID en sesion: {estacion_id}")
        print(f"[DEBUG] Vendedor ID en sesion: {vendedor_id}")
        print(f"[DEBUG] Estacion Nombre en sesion: {estacion_nombre}")
        print(f"[DEBUG] Vendedor Nombre en sesion: {vendedor_nombre}")
        
        if not estacion_id or not vendedor_id:
            print("[ERROR] Sesion POS no encontrada - Redirigiendo a seleccion")
            return JsonResponse({'success': False, 'message': 'Sesión no encontrada'})
        
        try:
            print(f"[DEBUG] Buscando estacion ID={estacion_id} y vendedor ID={vendedor_id}")
            estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa, activo=True)
            vendedor = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa, activo=True)
            print(f"[OK] Estacion y vendedor encontrados: {estacion.nombre}, {vendedor.nombre}")
            
            # Obtener folios disponibles reales desde la base de datos
            from facturacion_electronica.models import ArchivoCAF
            
            folios_factura = 0
            folios_boleta = 0
            folios_guia = 0
            
            try:
                # Facturas (tipo 33)
                caf_factura = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='33',
                    estado='activo'
                ).first()
                if caf_factura:
                    folios_factura = caf_factura.folio_hasta - caf_factura.folio_actual + 1
                
                # Boletas (tipo 39)
                caf_boleta = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='39',
                    estado='activo'
                ).first()
                if caf_boleta:
                    folios_boleta = caf_boleta.folio_hasta - caf_boleta.folio_actual + 1
                
                # Guías (tipo 52)
                caf_guia = ArchivoCAF.objects.filter(
                    empresa=request.empresa,
                    tipo_documento='52',
                    estado='activo'
                ).first()
                if caf_guia:
                    folios_guia = caf_guia.folio_hasta - caf_guia.folio_actual + 1
            except Exception as e:
                print(f"[WARN] Error al obtener folios disponibles: {e}")
            
            print(f"[DEBUG] Folios disponibles - Factura: {folios_factura}, Boleta: {folios_boleta}, Guia: {folios_guia}")
            print("[OK] Sesion POS valida - Devolviendo datos al frontend")
            
            _sincronizar_config_estacion(request, estacion)

            return JsonResponse({
                'success': True,
                'estacion_id': estacion.id,
                'vendedor_id': vendedor.id,
                'estacion_nombre': estacion_nombre,
                'nombre_estacion': (request.session.get('pos_nombre_estacion') or '').strip(),
                'vendedor_nombre': vendedor_nombre,
                'cierre_directo': bool(estacion.cierre_directo),
                'enviar_sii_directo': bool(estacion.enviar_sii_directo),
                'flujo_directo': str(estacion.flujo_cierre_directo or 'rut_final'),
                'estacion': {
                    'id': estacion.id,
                    'numero': estacion.numero,
                    'nombre': estacion.nombre,
                    'modo_pos': estacion.modo_pos,
                    'cierre_directo': estacion.cierre_directo,
                    'enviar_sii_directo': estacion.enviar_sii_directo,
                    'flujo_cierre_directo': estacion.flujo_cierre_directo,
                    'tipos_documentos': estacion.get_tipos_documentos_permitidos(),
                    'correlativo_ticket': estacion.correlativo_ticket,
                    'folios_factura': folios_factura,
                    'folios_boleta': folios_boleta,
                    'folios_guia': folios_guia,
                    'max_items': {
                        'factura': estacion.max_items_factura,
                        'boleta': estacion.max_items_boleta,
                        'guia': estacion.max_items_guia,
                        'cotizacion': estacion.max_items_cotizacion,
                        'vale': estacion.max_items_vale,
                    },
                    'copias': {
                        'factura': estacion.copias_factura,
                        'boleta': estacion.copias_boleta,
                        'guia': estacion.copias_guia,
                        'cotizacion': estacion.copias_cotizacion,
                        'ticket': estacion.copias_ticket,
                        'vale': estacion.copias_vale,
                    },
                    'folios_factura': folios_factura,
                    'folios_boleta': folios_boleta,
                    'folios_guia': folios_guia,
                }
            })
            
        except (EstacionTrabajo.DoesNotExist, Vendedor.DoesNotExist) as e:
            print(f"[ERROR] Estacion o vendedor no encontrados: {e}")
            return JsonResponse({'success': False, 'message': 'Estación o vendedor no válidos'})
    except Exception as e:
        print(f"[ERROR] Error inesperado en pos_session_info: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'})


@login_required
@requiere_empresa
def pos_buscar_cliente(request):
    """Buscar cliente por RUT o nombre"""
    q = request.GET.get('q', '').strip()
    
    if not q:
        return JsonResponse({'success': False, 'message': 'Término de búsqueda requerido'})
    
    try:
        from clientes.models import Cliente
        from django.db.models import Q
        
        # Búsqueda con filtro de empresa correcto
        if hasattr(request, 'empresa') and request.empresa:
            # Buscar en la empresa actual
            clientes = Cliente.objects.filter(
                Q(rut__icontains=q) | Q(nombre__icontains=q),
                empresa=request.empresa,
                estado='activo'
            ).order_by('nombre')[:10]
        else:
            # Si no hay empresa, devolver error
            return JsonResponse({'success': False, 'message': 'No se pudo identificar la empresa'})
        
        if clientes.exists():
            clientes_data = []
            for cliente in clientes:
                clientes_data.append({
                    'id': cliente.id,
                    'rut': cliente.rut,
                    'nombre': cliente.nombre,
                    'giro': cliente.giro,
                    'direccion': cliente.direccion,
                    'comuna': cliente.comuna,
                    'ciudad': cliente.ciudad,
                    'telefono': cliente.telefono,
                    'email': cliente.email,
                    'forma_pago_defecto_id': cliente.forma_pago_defecto_id,
                    'plazo_pago': cliente.plazo_pago or 30,
                })

            
            return JsonResponse({
                'success': True,
                'clientes': clientes_data
            })
        else:
            return JsonResponse({'success': False, 'message': 'No se encontraron clientes'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error en la búsqueda: {str(e)}'})


@login_required
@requiere_empresa
@permission_required('clientes.add_cliente', raise_exception=True)
def pos_crear_cliente_boleta(request):
    """Crear cliente automático para boletas"""
    if request.method == 'POST':
        try:
            from clientes.models import Cliente
            
            # Verificar si ya existe el cliente de boleta
            cliente_boleta, created = Cliente.objects.get_or_create(
                rut='66666666-6',
                empresa=request.empresa,
                defaults={
                    'nombre': 'CLIENTE BOLETA',
                    'giro': 'Consumidor Final',
                    'direccion': request.empresa.direccion or 'Sin dirección',
                    'comuna': request.empresa.comuna or 'Santiago',
                    'ciudad': request.empresa.ciudad or 'Santiago',
                    'telefono': request.empresa.telefono or '',
                    'email': request.empresa.email or '',
                    'estado': 'activo'
                }
            )
            
            return JsonResponse({
                'success': True,
                'cliente': {
                    'id': cliente_boleta.id,
                    'rut': cliente_boleta.rut,
                    'nombre': cliente_boleta.nombre,
                    'giro': cliente_boleta.giro,
                    'direccion': cliente_boleta.direccion,
                    'comuna': cliente_boleta.comuna,
                    'ciudad': cliente_boleta.ciudad,
                    'telefono': cliente_boleta.telefono,
                    'email': cliente_boleta.email
                },
                'created': created
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al crear cliente: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
@permission_required('clientes.add_cliente', raise_exception=True)
def pos_crear_cliente(request):
    """Crear nuevo cliente"""
    if request.method == 'POST':
        try:
            import json
            from clientes.models import Cliente

            data = json.loads(request.body)

            # Validar datos requeridos
            if not data.get('rut') or not data.get('nombre'):
                return JsonResponse({'success': False, 'message': 'RUT y nombre son requeridos'})

            # Crear cliente con todos los campos requeridos
            cliente = Cliente.objects.create(
                empresa=request.empresa,
                rut=data['rut'],
                nombre=data['nombre'],
                giro=data.get('giro', 'Sin giro'),
                direccion=data.get('direccion', 'Sin dirección'),
                comuna=data.get('comuna', 'Sin especificar'),
                ciudad=data.get('ciudad', 'Sin especificar'),
                region=data.get('region', 'Sin especificar'),  # ← AGREGADO
                telefono=data.get('telefono', 'Sin teléfono'),
                email=data.get('email', ''),
                estado='activo'
            )
            
            return JsonResponse({
                'success': True,
                'cliente': {
                    'id': cliente.id,
                    'rut': cliente.rut,
                    'nombre': cliente.nombre,
                    'giro': cliente.giro,
                    'direccion': cliente.direccion,
                    'comuna': cliente.comuna,
                    'ciudad': cliente.ciudad,
                    'telefono': cliente.telefono,
                    'email': cliente.email
                }
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al crear cliente: {str(e)}'})

    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
def pos_procesar_preventa(request):
    """Procesar preventa"""
    if request.method == 'POST':
        try:
            import json
            from clientes.models import Cliente
            from articulos.models import Articulo

            # Inicializar variables de retorno para evitar UnboundLocalError
            ticket_vale_id = None
            ticket_vale_numero = None

            print(f"[RAW BODY] {request.body.decode('utf-8')[:500]}")
            data = json.loads(request.body)
            
            # Función de limpieza para IDs (elimina espacios, caracteres especiales, etc)
            def clean_id(value):
                """Limpia un ID eliminando espacios no separables y otros caracteres"""
                if value is None:
                    return None
                if isinstance(value, int):
                    return value
                if isinstance(value, str):
                    # Eliminar espacios normales, espacios no separables (\xa0), y otros caracteres raros
                    cleaned = ''.join(filter(str.isdigit, value))
                    return int(cleaned) if cleaned else None
                return value
            
            # Limpiar y obtener IDs
            estacion_id = clean_id(data.get('estacion_id'))
            vendedor_id = clean_id(data.get('vendedor_id'))
            cliente_id = clean_id(data.get('cliente_id'))
            vehiculo_id = clean_id(data.get('vehiculo_id'))
            chofer_id = clean_id(data.get('chofer_id'))
            
            print(f"[DEBUG] IDs limpiados:")
            print(f"  Estacion ID: {data.get('estacion_id')} -> {estacion_id}")
            print(f"  Vendedor ID: {data.get('vendedor_id')} -> {vendedor_id}")
            print(f"  Cliente ID: {data.get('cliente_id')} -> {cliente_id}")
            print(f"  Vehiculo ID: {data.get('vehiculo_id')} -> {vehiculo_id}")
            print(f"  Chofer ID: {data.get('chofer_id')} -> {chofer_id}")

            # Obtener objetos con IDs limpios
            estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa)
            vendedor = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa)
            cliente = Cliente.objects.get(id=cliente_id, empresa=request.empresa)
            
            _sincronizar_config_estacion(request, estacion)
            
            # Debug: verificar configuración de cierre directo
            print(f"[DEBUG] Configuración de cierre directo:")
            print(f"  Estación.cierre_directo (BD): {estacion.cierre_directo}")
            print(f"  Sesión pos_cierre_directo: {request.session.get('pos_cierre_directo', False)}")
            print(f"  Sesión pos_estacion_id: {request.session.get('pos_estacion_id')}")
            print(f"  Estación ID actual: {estacion_id}")
            
            # Obtener vehículo y chofer si están presentes
            vehiculo = None
            chofer = None
            if vehiculo_id:
                from pedidos.models_transporte import Vehiculo
                vehiculo = Vehiculo.objects.get(id=vehiculo_id, empresa=request.empresa)
            if chofer_id:
                from pedidos.models_transporte import Chofer
                chofer = Chofer.objects.get(id=chofer_id, empresa=request.empresa)
            
            # Generar número de preventa único
            # IMPORTANTE: Los vales y documentos iniciales del POS usan SOLO el correlativo de ticket de la estación (independiente de folios CAF)
            # Las facturas/boletas/guías oficiales usan folios CAF que se asignan al procesar (cierre directo o posterior en caja)
            if data['tipo_documento'] in ['vale', 'ticket', 'boleta', 'factura', 'guia', 'cotizacion']:
                # Para vales y tickets: usar correlativo de ticket de la estación
                # CRÍTICO: Usar bloqueo select_for_update para evitar condiciones de carrera
                from django.db import transaction
                
                with transaction.atomic():
                    # Bloquear la estación para evitar condiciones de carrera
                    estacion_bloqueada = EstacionTrabajo.objects.select_for_update().get(pk=estacion.pk)
                    print(f"[DEBUG] Estación bloqueada: {estacion_bloqueada.nombre}, correlativo ANTES: {estacion_bloqueada.correlativo_ticket}")
                    
                    numero_ticket = estacion_bloqueada.incrementar_correlativo_ticket()
                    print(f"[DEBUG] Correlativo DESPUÉS de incrementar: {numero_ticket}")
                    
                    proximo_numero = f"{numero_ticket:06d}"
                    
                    # Verificar que el número no exista en ESTA estación (cada TPV tiene su correlativo)
                    existe_numero = Venta.objects.filter(
                        empresa=request.empresa,
                        tipo_documento=data['tipo_documento'],
                        estacion_trabajo=estacion_bloqueada,
                        numero_venta=proximo_numero,
                    ).exists()
                    print(f"[DEBUG] Número generado: {proximo_numero}, ¿existe?: {existe_numero}")
                    
                    max_intentos = 100
                    intento = 0
                    while existe_numero and intento < max_intentos:
                        print(f"[WARN] El número {proximo_numero} de tipo {data['tipo_documento']} ya existe, incrementando correlativo...")
                        numero_ticket = estacion_bloqueada.incrementar_correlativo_ticket()
                        proximo_numero = f"{numero_ticket:06d}"
                        existe_numero = Venta.objects.filter(
                            empresa=request.empresa,
                            tipo_documento=data['tipo_documento'],
                            estacion_trabajo=estacion_bloqueada,
                            numero_venta=proximo_numero,
                        ).exists()
                        print(f"[DEBUG] Nuevo número: {proximo_numero}, ¿existe?: {existe_numero}")
                        intento += 1
                    
                    if intento >= max_intentos:
                        raise Exception(f"No se pudo generar un número único después de {max_intentos} intentos")
                    
                    if intento > 0:
                        print(f"[WARN] Se requirieron {intento} intentos adicionales para encontrar un número disponible")
                
                print(f"[DEBUG] Número de vale generado: {proximo_numero} (correlativo estación: {numero_ticket})")
            else:
                # Para facturas/boletas/guías: usar números temporales (se reemplazarán por folios CAF al procesar)
                # Buscar el último número de venta de la empresa (solo para números temporales)
                ultima_venta = Venta.objects.filter(
                    empresa=request.empresa
                ).exclude(tipo_documento='vale').order_by('-id').first()
                
                if ultima_venta and ultima_venta.numero_venta and ultima_venta.numero_venta != 'TEMP':
                    try:
                        ultimo_numero = int(ultima_venta.numero_venta)
                        proximo_numero = f"{ultimo_numero + 1:06d}"
                    except ValueError:
                        # Si el número no es convertible, usar correlativo de ticket como fallback
                        numero_ticket = estacion.incrementar_correlativo_ticket()
                        proximo_numero = f"{int(numero_ticket):06d}"
                else:
                    # Si no hay ventas previas, usar correlativo de ticket como fallback
                    numero_ticket = estacion.incrementar_correlativo_ticket()
                    proximo_numero = f"{int(numero_ticket):06d}"
                
                # Verificar que el número no exista (por seguridad, excluyendo vales)
                while Venta.objects.filter(empresa=request.empresa).exclude(tipo_documento='vale').filter(numero_venta=proximo_numero).exists():
                    proximo_numero = f"{int(proximo_numero) + 1:06d}"
            
            # Debug: verificar datos recibidos
            print(f"DEBUG - Datos recibidos:")
            print(f"  Estacion ID: {data['estacion_id']} (tipo: {type(data['estacion_id'])})")
            print(f"  Vendedor ID: {data['vendedor_id']} (tipo: {type(data['vendedor_id'])})")
            print(f"  Cliente ID: {data['cliente_id']} (tipo: {type(data['cliente_id'])})")
            print(f"  Items: {len(data['items'])}")
            for i, item in enumerate(data['items']):
                print(f"    Item {i}: {item}")
            print(f"  Totales: {data['totales']}")
            
            # Convertir valores a Decimal para evitar errores de tipo
            from decimal import Decimal
            
            # Crear preventa
            # Usar los valores calculados correctamente desde el frontend
            subtotal = Decimal(str(data['totales']['subtotal']))
            neto = Decimal(str(data['totales']['neto']))
            iva = Decimal(str(data['totales']['iva']))
            impuesto_especifico = Decimal(str(data['totales']['impuesto_especifico']))
            total = Decimal(str(data['totales']['total']))
            descuento = Decimal(str(data['totales']['descuento']))
            
            print(f"DEBUG - Valores a guardar en BD:")
            print(f"  Subtotal: {subtotal}")
            print(f"  Neto: {neto}")
            print(f"  IVA: {iva}")
            print(f"  Impuesto Específico: {impuesto_especifico}")
            print(f"  Total: {total}")

            from empresas.middleware import resolver_sucursal_operativa
            sucursal_activa = _sucursal_de_venta(request, estacion) or resolver_sucursal_operativa(request)
            if sucursal_activa:
                request.sucursal_activa = sucursal_activa
            if not sucursal_activa:
                return JsonResponse({
                    'success': False,
                    'message': 'No hay sucursal activa. Asigne una sucursal a la estación o al usuario.',
                }, status=400)
            
            # CRÍTICO: Asegurar que tipo_documento_planeado siempre tenga un valor válido
            # TODO lo que viene del POS es un TICKET (preventa)
            # El tipo_documento_planeado indica lo que será al final (boleta, factura, guia o vale)
            tipo_doc_planeado = data.get('tipo_documento_planeado')
            
            # Si no viene planeado o es 'ticket' (que es un valor temporal invaid), intentar recuperar el original
            if not tipo_doc_planeado or tipo_doc_planeado == 'ticket':
                # Intentar usar el tipo original seleccionado en el frontend
                if data.get('tipo_documento_original'):
                    print(f"[DEBUG] Recuperando tipo_doc_planeado desde original: {data.get('tipo_documento_original')}")
                    tipo_doc_planeado = data.get('tipo_documento_original')
            
            if not tipo_doc_planeado:
                # Si no viene planeado, usamos el tipo_documento que envió el POS
                tipo_doc_planeado = data.get('tipo_documento')
            
            # Forzamos que la preventa sea SIEMPRE tipo 'ticket'
            tipo_documento_preventa = 'ticket'
            if data.get('tipo_documento') == 'cotizacion':
                tipo_documento_preventa = 'cotizacion'
                tipo_doc_planeado = 'cotizacion'

            print("=" * 80)
            
            # Validar que sea un tipo válido para el futuro
            tipos_validos = ['factura', 'boleta', 'guia', 'cotizacion', 'vale']
            if tipo_doc_planeado not in tipos_validos:
                print(f"[WARN] tipo_documento_planeado inválido: {tipo_doc_planeado}, usando 'boleta' como fallback")
                tipo_doc_planeado = 'boleta'
            print("[DEBUG] *** DATOS RECIBIDOS DEL FRONTEND ***")
            print(f"[DEBUG] tipo_documento: {data['tipo_documento']}")
            print(f"[DEBUG] tipo_documento_planeado: {tipo_doc_planeado}")
            print(f"[DEBUG] tipo_despacho recibido: {data.get('tipo_despacho')}")
            print(f"[DEBUG] referencias recibidas: {data.get('referencias')}")
            print(f"[DEBUG] data completo: {data}")
            print("=" * 80)
            
            
            # LOGGING CRÍTICO: Verificar tipo_despacho ANTES de crear preventa
            print("=" * 80)
            print("[CRITICAL DEBUG] ANTES DE CREAR PREVENTA:")
            print(f"  data.get('tipo_despacho'): {data.get('tipo_despacho')}")
            print(f"  Tipo: {type(data.get('tipo_despacho'))}")
            print(f"  Es None: {data.get('tipo_despacho') is None}")
            print(f"  Es string vacio: {data.get('tipo_despacho') == ''}")
            print(f"  tipo_documento: {data['tipo_documento']}")
            print("=" * 80)
            
            # FORZAR tipo_despacho si es guía
            tipo_despacho_final = data.get('tipo_despacho')
            if (data.get('tipo_documento') == 'guia' or tipo_doc_planeado == 'guia') and not tipo_despacho_final:
                print("[ERROR] Guía de despacho sin tipo de traslado (tipo_despacho)")
                return JsonResponse({
                    'success': False,
                    'message': 'Debe seleccionar un Motivo de Traslado para la Guía de Despacho.'
                }, status=400)

            # El estado depende de si es algo que ya está "listo" (ticket/vale) o borrador
            # NOTA: Los vales internos también se quedan como pendientes (facturado=False)
            estado_inicial = 'confirmada'
            if data.get('tipo_documento') == 'cotizacion':
                estado_inicial = 'borrador'
                
            # facturado=False significa que está PENDIENTE en la lista de la Caja
            # Queremos que los tickets y los vales aparezcan como pendientes
            es_facturado = False
            if data.get('tipo_documento') == 'cotizacion':
                es_facturado = True

            preventa = Venta.objects.create(
                empresa=request.empresa,
                sucursal=sucursal_activa,
                numero_venta=proximo_numero,
                cliente=cliente,
                vendedor=vendedor,
                vehiculo=vehiculo,
                chofer=chofer,
                estacion_trabajo=estacion,
                tipo_documento=tipo_documento_preventa,
                tipo_documento_planeado=tipo_doc_planeado,
                tipo_despacho=tipo_despacho_final,
                subtotal=subtotal,
                descuento=descuento,
                neto=neto,
                iva=iva,
                impuesto_especifico=impuesto_especifico,
                total=total,
                estado=estado_inicial,
                estado_cotizacion='pendiente' if data.get('tipo_documento') == 'cotizacion' else None,
                facturado=es_facturado,
                fecha=fecha_documento_caja(_apertura_caja_estacion(request.empresa, estacion, sucursal_activa)),
                usuario_creacion=request.user
            )
            
            # LOGGING CRÍTICO: Verificar tipo_despacho DESPUÉS de crear preventa
            print("=" * 80)
            print("[CRITICAL DEBUG] DESPUÉS DE CREAR PREVENTA:")
            print(f"  preventa.id: {preventa.id}")
            print(f"  preventa.tipo_despacho: {preventa.tipo_despacho}")
            print(f"  preventa.tipo_documento: {preventa.tipo_documento}")
            
            # VERIFICAR EN BD INMEDIATAMENTE
            preventa.refresh_from_db()
            print(f"  preventa.tipo_despacho (refresh): {preventa.tipo_despacho}")
            print("=" * 80)

            
            # Crear detalles
            print("DEBUG - Creando detalles de venta...")
            from articulos.models import KitOferta, KitOfertaItem
            
            for i, item in enumerate(data['items']):
                print(f"DEBUG - Procesando item {i}: {item}")
                
                # Verificar si es un kit
                if item.get('tipo') == 'kit' or item.get('kitId'):
                    kit_id = clean_id(item.get('kitId'))
                    cantidad_kit = Decimal(str(item['cantidad']))
                    precio_kit_total = Decimal(str(item['precio']))
                    
                    print(f"DEBUG - Es un KIT. Kit ID: {kit_id}, Cantidad: {cantidad_kit}, Precio total: {precio_kit_total}")
                    
                    try:
                        kit = KitOferta.objects.get(id=kit_id, empresa=request.empresa)
                        kit_items = kit.items.select_related('articulo').all()
                        
                        # Calcular precio total normal de todos los items del kit
                        precio_total_normal = Decimal('0.00')
                        for kit_item in kit_items:
                            try:
                                precio_articulo = Decimal(str(kit_item.articulo.precio_final_calculado))
                            except (ValueError, AttributeError, TypeError):
                                try:
                                    precio_articulo = Decimal(str(kit_item.articulo.precio_venta))
                                except:
                                    precio_articulo = Decimal('0.00')
                            precio_total_normal += precio_articulo * Decimal(str(kit_item.cantidad))
                        
                        # Calcular factor de descuento proporcional
                        if precio_total_normal > 0:
                            factor_descuento = precio_kit_total / precio_total_normal
                        else:
                            factor_descuento = Decimal('1.00')
                        
                        print(f"DEBUG - Precio total normal del kit: {precio_total_normal}")
                        print(f"DEBUG - Factor descuento: {factor_descuento}")
                        
                        # Crear detalles para cada artículo del kit
                        for kit_item in kit_items:
                            try:
                                precio_articulo_normal = Decimal(str(kit_item.articulo.precio_final_calculado))
                            except (ValueError, AttributeError, TypeError):
                                try:
                                    precio_articulo_normal = Decimal(str(kit_item.articulo.precio_venta))
                                except:
                                    precio_articulo_normal = Decimal('0.00')
                            
                            # Precio proporcional del artículo
                            precio_proporcional = precio_articulo_normal * factor_descuento
                            cantidad_articulo = Decimal(str(kit_item.cantidad)) * cantidad_kit
                            precio_total_articulo = precio_proporcional * cantidad_articulo
                            
                            print(f"DEBUG - Artículo del kit: {kit_item.articulo.nombre}")
                            print(f"DEBUG -   Precio normal: {precio_articulo_normal}")
                            print(f"DEBUG -   Precio proporcional: {precio_proporcional}")
                            print(f"DEBUG -   Cantidad: {cantidad_articulo}")
                            print(f"DEBUG -   Precio total: {precio_total_articulo}")
                            
                            VentaDetalle.objects.create(
                                venta=preventa,
                                articulo=kit_item.articulo,
                                cantidad=cantidad_articulo,
                                precio_unitario=precio_proporcional,
                                precio_total=precio_total_articulo,
                                impuesto_especifico=Decimal('0.00')
                            )
                            print(f"DEBUG - VentaDetalle creado para artículo del kit")
                            
                    except KitOferta.DoesNotExist:
                        print(f"ERROR - Kit con ID {kit_id} no encontrado")
                        raise Exception(f"Kit con ID {kit_id} no encontrado")
                    except Exception as e:
                        print(f"ERROR al procesar kit: {e}")
                        import traceback
                        print(traceback.format_exc())
                        raise e
                        
                else:
                    # Es un artículo normal o producto comodín
                    articulo_id_limpio = clean_id(item.get('articuloId'))
                    es_comodin = item.get('esComodin') == True or articulo_id_limpio is None
                    
                    print(f"DEBUG - Es un ARTÍCULO. ID: {item.get('articuloId')} -> {articulo_id_limpio}, esComodin: {es_comodin}")
                    
                    if es_comodin:
                        # Es un producto comodín - usar artículo especial "COMODIN"
                        print(f"DEBUG - Es PRODUCTO COMODÍN: {item.get('nombre', 'Sin nombre')}")
                        
                        # Obtener categoría y unidad de medida por defecto
                        from articulos.models import CategoriaArticulo, UnidadMedida
                        
                        # Buscar o crear categoría "COMODIN"
                        categoria_comodin, _ = CategoriaArticulo.objects.get_or_create(
                            empresa=request.empresa,
                            codigo='COMODIN',
                            defaults={
                                'nombre': 'Productos Comodín',
                                'descripcion': 'Categoría para productos personalizados del POS',
                                'exenta_iva': False
                            }
                        )
                        
                        # Buscar o crear unidad de medida "UNIDAD"
                        unidad_comodin, _ = UnidadMedida.objects.get_or_create(
                            empresa=request.empresa,
                            nombre='UNIDAD',
                            defaults={
                                'simbolo': 'UN',
                                'activa': True
                            }
                        )
                        
                        # Buscar o crear artículo "COMODIN" para productos comodín
                        try:
                            articulo_comodin = Articulo.objects.get(empresa=request.empresa, codigo='COMODIN')
                            # Si existe pero no tiene categoría o unidad, actualizarlos
                            if not articulo_comodin.categoria or not articulo_comodin.unidad_medida:
                                articulo_comodin.categoria = categoria_comodin
                                articulo_comodin.unidad_medida = unidad_comodin
                                articulo_comodin.save()
                                print(f"DEBUG - Artículo COMODIN actualizado con categoría y unidad: {articulo_comodin.id}")
                            else:
                                print(f"DEBUG - Artículo COMODIN existente: {articulo_comodin.id}")
                        except Articulo.DoesNotExist:
                            # Crear nuevo artículo COMODIN
                            articulo_comodin = Articulo.objects.create(
                                empresa=request.empresa,
                                codigo='COMODIN',
                                nombre='Producto Comodín',
                                descripcion='Producto personalizado creado desde el POS',
                                categoria=categoria_comodin,
                                unidad_medida=unidad_comodin,
                                precio_venta='0.00',
                                precio_costo='0.00',
                                precio_final='0.00',
                                activo=True,
                                control_stock=False
                            )
                            print(f"DEBUG - Artículo COMODIN creado: {articulo_comodin.id}")
                        
                        articulo = articulo_comodin
                        nombre_comodin = item.get('nombre', 'Producto Comodín')
                        print(f"DEBUG - Nombre del producto comodín: {nombre_comodin}")
                        
                    elif not articulo_id_limpio:
                        print(f"ERROR - Item sin articuloId: {item}")
                        raise Exception(f"Item sin articuloId válido: {item}")
                    else:
                        try:
                            articulo = Articulo.objects.get(id=articulo_id_limpio, empresa=request.empresa)
                            print(f"DEBUG - Artículo encontrado: {articulo.nombre}")
                        except Articulo.DoesNotExist:
                            print(f"ERROR - Artículo con ID {articulo_id_limpio} no encontrado")
                            raise Exception(f"Artículo con ID {articulo_id_limpio} no encontrado")
                    
                    print(f"DEBUG - Creando VentaDetalle...")
                    print(f"DEBUG - Valores a crear:")
                    print(f"  cantidad: {Decimal(str(item['cantidad']))}")
                    print(f"  precio_unitario: {Decimal(str(item['precio']))}")
                    print(f"  precio_total: {Decimal(str(item.get('total', item['precio'] * item['cantidad'])))}")
                    
                    # Crear el detalle
                    try:
                        detalle = VentaDetalle.objects.create(
                            venta=preventa,
                            articulo=articulo,
                            cantidad=Decimal(str(item['cantidad'])),
                            precio_unitario=Decimal(str(item['precio'])),
                            precio_total=Decimal(str(item.get('total', float(item['precio']) * float(item['cantidad'])))),
                            impuesto_especifico=Decimal(str(item.get('impuesto_especifico', '0.00')))
                        )
                        print(f"DEBUG - VentaDetalle creado exitosamente")
                        
                        # Si es producto comodín, actualizar el nombre del artículo temporalmente para esta venta
                        # Nota: Esto no persiste en la BD, pero ayuda en la visualización
                        if es_comodin and 'nombre' in item:
                            # Guardar el nombre personalizado en algún lugar si es necesario
                            # Por ahora, el nombre se perderá y se mostrará "Producto Comodín"
                            print(f"DEBUG - Nombre personalizado del comodín: {item['nombre']}")
                            
                    except Exception as e:
                        print(f"ERROR al crear VentaDetalle: {e}")
                        print(f"Tipo de error: {type(e)}")
                        import traceback
                        print(traceback.format_exc())
                        raise e
            
            # Crear referencias si existen
            if data.get('referencias'):
                print(f"DEBUG - Creando {len(data['referencias'])} referencias...")
                from .models import VentaReferencia
                from datetime import datetime
                
                for ref in data['referencias']:
                    try:
                        VentaReferencia.objects.create(
                            venta=preventa,
                            tipo_referencia=ref['tipo'],
                            folio_referencia=ref['folio'],
                            fecha_referencia=datetime.strptime(ref['fecha'], '%Y-%m-%d').date(),
                            razon_referencia=ref.get('razon', '')
                        )
                        print(f"DEBUG - Referencia creada: {ref['tipo']} - {ref['folio']}")
                    except Exception as e:
                        print(f"ERROR al crear referencia: {e}")
                        # No detenemos el proceso si falla una referencia
            
            # ============================================================================
            # CIERRE DIRECTO: emitir DTE. Esta estación no genera vale.
            # ============================================================================
            estacion.refresh_from_db()
            cierre_directo_ticket = bool(estacion.cierre_directo)

            print("=" * 80)
            print("[CIERRE DIRECTO TICKET] Verificando configuración:")
            print(f"  tipo_documento: {data['tipo_documento']}")
            print(f"  tipo_documento_planeado: {tipo_doc_planeado}")
            print(f"  Estación.cierre_directo: {estacion.cierre_directo}")
            print(f"  ¿Entrará en cierre directo?: {cierre_directo_ticket}")
            print("=" * 80)

            if cierre_directo_ticket and data.get('tipo_documento') != 'cotizacion':
                if tipo_doc_planeado not in ['factura', 'boleta', 'guia']:
                    tipo_doc_planeado = 'boleta'
                    preventa.tipo_documento_planeado = tipo_doc_planeado
                    preventa.save(update_fields=['tipo_documento_planeado'])
                print("[OK] CIERRE DIRECTO TICKET ACTIVO - Procesando automaticamente")
                
                try:
                    from caja.models import AperturaCaja, Caja, VentaProcesada, MovimientoCaja
                    from facturacion_electronica.dte_service import DTEService
                    from django.db import transaction
                    
                    apertura_activa = _apertura_caja_estacion(request.empresa, estacion, sucursal_activa)
                    
                    if not apertura_activa:
                        return JsonResponse({
                            'success': False,
                            'error': 'sin_caja',
                            'message': 'Esta estación no tiene una caja abierta. Abra la caja asociada a esta estación.',
                        }, status=400)
                    
                    pagos, error_pago = _resolver_pagos_documento(
                        request.empresa,
                        tipo_doc_planeado,
                        preventa.total,
                        data.get('pagos') or data.get('formas_pago') or [],
                    )
                    if error_pago:
                        return JsonResponse({
                            'success': False,
                            'error': 'pago',
                            'message': error_pago,
                        }, status=400)

                    forma_pago = pagos[0]['forma_pago'] if pagos else None
                    
                    with transaction.atomic():
                        # Verificar folios disponibles
                        tipo_dte_map = {
                            'factura': '33',
                            'boleta': '39',
                            'guia': '52',
                        }
                        tipo_dte_codigo = tipo_dte_map.get(tipo_doc_planeado, '39')
                        
                        from facturacion_electronica.models import ArchivoCAF
                        caf_activo = ArchivoCAF.objects.filter(
                            empresa=request.empresa,
                            tipo_documento=tipo_dte_codigo,
                            estado='activo',
                            folio_actual__lte=F('folio_hasta')
                        ).first()
                        
                        if not caf_activo:
                            nombres_doc = {'33': 'Facturas', '39': 'Boletas', '52': 'Guías de Despacho'}
                            nombre_doc = nombres_doc.get(tipo_dte_codigo, 'Documentos')
                            return JsonResponse({
                                'success': False,
                                'error': 'sin_folios',
                                'message': f'No hay folios disponibles para emitir {nombre_doc}',
                            }, status=400)
                        
                        # Actualizar tipo_despacho en la preventa si viene
                        if data.get('tipo_despacho'):
                            preventa.tipo_despacho = data.get('tipo_despacho')
                            preventa.save()
                        
                        fecha_doc = fecha_documento_caja(apertura_activa)
                        preventa.fecha = fecha_doc
                        preventa.save(update_fields=['fecha'])

                        # Generar DTE
                        print(f"[CIERRE DIRECTO VALE] Generando DTE tipo {tipo_dte_codigo}...")
                        dte_service = DTEService(request.empresa)
                        dte = dte_service.generar_dte_desde_venta(preventa, tipo_dte_codigo)
                        
                        if not dte:
                            return JsonResponse({
                                'success': False,
                                'error': 'dte',
                                'message': 'No se pudo generar el DTE. Revise el CAF y los datos del cliente.',
                            }, status=400)
                        
                        numero_venta_final = f"{dte.folio:06d}"
                        print(f"[OK] CIERRE DIRECTO TICKET: DTE generado - Folio {dte.folio}")
                        
                        # Crear venta final (copia del ticket)
                        venta_final = Venta.objects.create(
                            empresa=request.empresa,
                            sucursal=preventa.sucursal,
                            estacion_trabajo=preventa.estacion_trabajo or estacion,
                            tipo_documento=tipo_doc_planeado,  # El tipo final (factura, boleta, guia)
                            numero_venta=numero_venta_final,
                            cliente=preventa.cliente,
                            vendedor=preventa.vendedor,
                            estado='confirmada',
                            subtotal=preventa.subtotal,
                            descuento=preventa.descuento,
                            neto=preventa.neto,
                            iva=preventa.iva,
                            impuesto_especifico=preventa.impuesto_especifico,
                            total=preventa.total,
                            tipo_despacho=preventa.tipo_despacho,
                            fecha=fecha_doc,
                            usuario_creacion=request.user
                        )
                        
                        # Copiar detalles
                        for detalle in preventa.ventadetalle_set.all():
                            VentaDetalle.objects.create(
                                venta=venta_final,
                                articulo=detalle.articulo,
                                cantidad=detalle.cantidad,
                                precio_unitario=detalle.precio_unitario,
                                precio_total=detalle.precio_total,
                                impuesto_especifico=detalle.impuesto_especifico
                            )
                        
                        monto_recibido, monto_cambio, primer_movimiento = _aplicar_pagos_cierre_directo(
                            venta_final,
                            apertura_activa,
                            pagos,
                            tipo_doc_planeado,
                            numero_venta_final,
                            request.user,
                            dte=dte,
                        )
                        forma_pago = venta_final.forma_pago or forma_pago
                        
                        venta_procesada = VentaProcesada.objects.create(
                            venta_preventa=preventa,
                            venta_final=venta_final,
                            apertura_caja=apertura_activa,
                            movimiento_caja=primer_movimiento,
                            usuario_proceso=request.user,
                            monto_recibido=monto_recibido,
                            monto_cambio=monto_cambio,
                            stock_descontado=True,
                            dte_generado=dte,
                            cuenta_corriente_actualizada=bool(
                                tipo_doc_planeado == 'factura' and venta_final.saldo_pendiente > 0
                            ),
                        )
                        
                        # Descontar stock
                        from inventario.models import Stock
                        bodega_caja = apertura_activa.caja.bodega
                        for detalle in preventa.ventadetalle_set.all():
                            stock = Stock.objects.filter(
                                empresa=request.empresa,
                                bodega=bodega_caja,
                                articulo=detalle.articulo
                            ).first()
                            if stock:
                                stock.cantidad -= detalle.cantidad
                                stock.save()
                        
                        # Marcar ticket como facturado
                        preventa.facturado = True
                        preventa.save()
                        _finalizar_dte_cierre_directo(dte, venta_final, forma_pago, apertura_activa)
                        
                        # Generar URL del documento con parámetros de autoclose y return al POS
                        from django.urls import reverse
                        from urllib.parse import quote
                        doc_url_base = reverse('facturacion_electronica:ver_factura_electronica', args=[dte.pk])
                        pos_url = reverse('ventas:pos_view')
                        doc_url = f"{doc_url_base}?auto=1&autoclose=1&autoclose_delay=1000&return_url={quote(pos_url, safe='')}"
                        
                        # Enviar al SII si corresponde
                        if estacion.enviar_sii_directo and request.empresa.facturacion_electronica:
                            try:
                                from facturacion_electronica.background_sender import get_background_sender
                                sender = get_background_sender()
                                if sender.enviar_dte(dte.id, request.empresa.id):
                                    print("[OK] CIERRE DIRECTO TICKET: DTE agregado a cola de envío")
                            except Exception as e_envio:
                                print(f"[WARN] Error al enviar DTE: {e_envio}")
                        
                        # ENVIAR A COLA DE IMPRESIÓN LOCAL (agente)
                        impresion_silenciosa = False
                        try:
                            from caja.impresion_utils import encolar_impresion_agente

                            impresion_silenciosa = encolar_impresion_agente(
                                request.empresa,
                                venta_final,
                                estacion=estacion,
                                dte=dte,
                                tipo_documento='dte',
                            )
                            if impresion_silenciosa:
                                print("[OK] CIERRE DIRECTO DTE ENCOLADO PARA AGENTE LOCAL")
                            else:
                                print("[WARN] No se encontró caja para encolar impresión silenciosa")
                        except Exception as e:
                            print(f"[ERROR] Error al encolar DTE en pos_procesar_preventa: {e}")

                        print("=" * 80)
                        print("[OK] CIERRE DIRECTO TICKET - COMPLETADO")
                        print(f"   Tipo: {tipo_doc_planeado}")
                        print(f"   Folio: {dte.folio}")
                        print(f"   doc_url: {doc_url}")
                        print("=" * 80)
                        
                        return JsonResponse({
                            'success': True,
                            'cierre_directo': True,
                            'tipo_documento': tipo_doc_planeado,
                            'tipo_documento_planeado': tipo_doc_planeado,
                            'numero_venta': numero_venta_final,
                            'numero_preventa': proximo_numero,
                            'doc_url': doc_url,
                            'preventa_id': preventa.id,
                            'venta_final_id': venta_final.id,
                            'impresion_silenciosa': impresion_silenciosa
                        })
                    
                except Exception as e_cierre_ticket:
                    print(f"[ERROR] CIERRE DIRECTO TICKET: {e_cierre_ticket}")
                    import traceback
                    traceback.print_exc()
                    return JsonResponse({
                        'success': False,
                        'error': 'cierre_directo',
                        'message': f'No se pudo emitir el documento con cierre directo: {e_cierre_ticket}',
                    }, status=400)
            
            # ============================================================================
            # PROCESAMIENTO PARA VALES INTERNOS (No se convierten, afectan caja inmediatamente)
            # ============================================================================
            if data['tipo_documento'] == 'vale':
                from caja.models import AperturaCaja, Caja, MovimientoCaja
                
                # Buscar apertura activa
                apertura_activa = None
                for caja in Caja.objects.filter(empresa=request.empresa, activo=True):
                    apertura = caja.get_apertura_activa()
                    if apertura:
                        apertura_activa = apertura
                        break
                
                if apertura_activa:
                    print("[OK] PROCESANDO VALE INTERNO - Creando movimiento de caja")
                    # Obtener forma de pago por defecto (Efectivo)
                    forma_pago = FormaPago.objects.filter(
                        empresa=request.empresa,
                        codigo__iexact='EF'
                    ).first() or FormaPago.objects.filter(
                        empresa=request.empresa,
                        activo=True
                    ).first()
                    
                    if forma_pago:
                        from django.db import transaction
                        with transaction.atomic():
                            # Crear movimiento de caja
                            MovimientoCaja.objects.create(
                                apertura_caja=apertura_activa,
                                venta=preventa,
                                tipo='venta',
                                forma_pago=forma_pago,
                                monto=preventa.total,
                                descripcion=f"Vale Interno #{proximo_numero}",
                                usuario=request.user
                            )
                            apertura_activa.calcular_totales()
                            
                            # Descontar stock
                            from inventario.models import Stock
                            bodega_caja = apertura_activa.caja.bodega
                            for detalle in preventa.ventadetalle_set.all():
                                stock = Stock.objects.filter(
                                    empresa=request.empresa,
                                    bodega=bodega_caja,
                                    articulo=detalle.articulo
                                ).first()
                                if stock:
                                    stock.cantidad -= detalle.cantidad
                                    stock.save()
                    else:
                        print("[WARN] VALE INTERNO: No se encontró forma de pago por defecto")
                else:
                    print("[WARN] VALE INTERNO: No hay caja abierta para procesar el vale inmediatamente")
            
            # El documento para impresión y procesamiento es la preventa misma
            # Se desactiva la clonación de tickets para prevenir duplicados en caja
            ticket_vale = preventa
            ticket_vale_id = preventa.id
            ticket_vale_numero = preventa.numero_venta

            if False: # Bloque desactivado: data['tipo_documento'] in ['factura', 'boleta', 'guia']:
                
                # Generar número de ticket usando SOLO el correlativo de ticket de la estación
                # Este correlativo es independiente de los folios CAF de facturas/boletas/guías
                # CRÍTICO: Usar bloqueo select_for_update para evitar condiciones de carrera
                from django.db import transaction
                
                with transaction.atomic():
                    # Bloquear la estación para evitar condiciones de carrera
                    estacion_bloqueada = EstacionTrabajo.objects.select_for_update().get(pk=estacion.pk)
                    print(f"[DEBUG] Estación bloqueada: {estacion_bloqueada.nombre}, correlativo ANTES: {estacion_bloqueada.correlativo_ticket}")
                    
                    numero_ticket_vale = estacion_bloqueada.incrementar_correlativo_ticket()
                    print(f"[DEBUG] Correlativo DESPUÉS de incrementar: {numero_ticket_vale}")
                    
                    numero_vale = f"{numero_ticket_vale:06d}"
                    
                    # Verificar que el número no exista (solo entre vales) - por seguridad
                    existe_numero = Venta.objects.filter(empresa=request.empresa, tipo_documento='vale', numero_venta=numero_vale).exists()
                    print(f"[DEBUG] Número de vale generado: {numero_vale}, ¿existe?: {existe_numero}")
                    
                    max_intentos = 100
                    intento = 0
                    while existe_numero and intento < max_intentos:
                        print(f"[WARN] El número de vale {numero_vale} ya existe, incrementando correlativo...")
                        numero_ticket_vale = estacion_bloqueada.incrementar_correlativo_ticket()
                        numero_vale = f"{numero_ticket_vale:06d}"
                        existe_numero = Venta.objects.filter(empresa=request.empresa, tipo_documento='vale', numero_venta=numero_vale).exists()
                        print(f"[DEBUG] Nuevo número de vale: {numero_vale}, ¿existe?: {existe_numero}")
                        intento += 1
                    
                    if intento >= max_intentos:
                        raise Exception(f"No se pudo generar un número único después de {max_intentos} intentos")
                    
                    if intento > 0:
                        print(f"[WARN] Se requirieron {intento} intentos adicionales para encontrar un número disponible")
                
                print(f"[DEBUG] Número de vale generado: {numero_vale} (correlativo estación: {numero_ticket_vale})")
                
                # Crear el vale
                print(f"DEBUG - Creando ticket vale...")
                print(f"DEBUG - Items recibidos: {len(data['items'])}")
                
                # CRÍTICO: Validar que tipo_documento_planeado siempre tenga un valor válido
                # Este vale facturable viene de factura/boleta/guía, así que debe tener ese tipo
                tipo_doc_planeado_vale = data.get('tipo_documento')
                tipos_validos = ['factura', 'boleta', 'guia', 'cotizacion']
                
                if not tipo_doc_planeado_vale or tipo_doc_planeado_vale not in tipos_validos:
                    print(f"[ERROR] tipo_documento inválido para vale facturable: {tipo_doc_planeado_vale}, usando 'boleta' como fallback")
                    tipo_doc_planeado_vale = 'boleta'
                
                # NUNCA debe ser 'ticket' porque un ticket no se convierte en otro ticket
                if tipo_doc_planeado_vale == 'ticket' or tipo_doc_planeado_vale == 'vale':
                    print(f"[ERROR] tipo_documento_planeado no puede ser 'ticket' o 'vale', corrigiendo a 'boleta'")
                    tipo_doc_planeado_vale = 'boleta'
                
                print(f"[DEBUG] Ticket facturable - tipo_documento_planeado: {tipo_doc_planeado_vale}")
                
                ticket_vale = Venta.objects.create(
                    empresa=request.empresa,
                    sucursal=sucursal_activa,
                    numero_venta=numero_vale,
                    fecha=fecha_documento_caja(_apertura_caja_estacion(request.empresa, estacion, sucursal_activa)),
                    cliente=cliente,
                    vendedor=vendedor,
                    estacion_trabajo=estacion,
                    tipo_documento='ticket',
                    tipo_documento_planeado=tipo_doc_planeado_vale,  # ← SIEMPRE debe tener un valor válido
                    subtotal=subtotal,
                    descuento=descuento,
                    neto=neto,
                    iva=iva,
                    impuesto_especifico=impuesto_especifico,
                    total=total,
                    estado='confirmada',  # Tickets impresos siempre están confirmados y disponibles para facturar
                    facturado=False,  # ← NO facturado aún, aparecerá en caja para procesar
                    tipo_despacho=preventa.tipo_despacho,  # ← CRÍTICO: Propagar tipo de despacho (para Guías)
                    usuario_creacion=request.user,
                    observaciones=f"Ticket generado automáticamente para {tipo_doc_planeado_vale} #{proximo_numero}"
                )

                # Crear detalles del vale
                for item in data['items']:
                    # Verificar si es un kit
                    if item.get('tipo') == 'kit' or item.get('kitId'):
                        kit_id = clean_id(item.get('kitId'))
                        cantidad_kit = Decimal(str(item['cantidad']))
                        precio_kit_total = Decimal(str(item['precio']))
                        
                        print(f"DEBUG - Vale: Es un KIT. Kit ID: {kit_id}, Cantidad: {cantidad_kit}, Precio total: {precio_kit_total}")
                        
                        try:
                            kit = KitOferta.objects.get(id=kit_id, empresa=request.empresa)
                            kit_items = kit.items.select_related('articulo').all()
                            
                            # Calcular precio total normal de todos los items del kit
                            precio_total_normal = Decimal('0.00')
                            for kit_item in kit_items:
                                try:
                                    precio_articulo = Decimal(str(kit_item.articulo.precio_final_calculado))
                                except (ValueError, AttributeError, TypeError):
                                    try:
                                        precio_articulo = Decimal(str(kit_item.articulo.precio_venta))
                                    except:
                                        precio_articulo = Decimal('0.00')
                                precio_total_normal += precio_articulo * Decimal(str(kit_item.cantidad))
                            
                            # Calcular factor de descuento proporcional
                            if precio_total_normal > 0:
                                factor_descuento = precio_kit_total / precio_total_normal
                            else:
                                factor_descuento = Decimal('1.00')
                            
                            # Crear detalles para cada artículo del kit
                            for kit_item in kit_items:
                                try:
                                    precio_articulo_normal = Decimal(str(kit_item.articulo.precio_final_calculado))
                                except (ValueError, AttributeError, TypeError):
                                    try:
                                        precio_articulo_normal = Decimal(str(kit_item.articulo.precio_venta))
                                    except:
                                        precio_articulo_normal = Decimal('0.00')
                                
                                # Precio proporcional del artículo
                                precio_proporcional = precio_articulo_normal * factor_descuento
                                cantidad_articulo = Decimal(str(kit_item.cantidad)) * cantidad_kit
                                precio_total_articulo = precio_proporcional * cantidad_articulo
                                
                                # Obtener impuesto específico del item (viene del carrito del POS)
                                impuesto_esp_item = Decimal(str(item.get('impuesto_especifico', 0)))
                                
                                print(f"DEBUG - Vale: Artículo del kit: {kit_item.articulo.nombre}")
                                print(f"DEBUG - Vale:   Precio proporcional: {precio_proporcional}")
                                print(f"DEBUG - Vale:   Cantidad: {cantidad_articulo}")
                                
                                VentaDetalle.objects.create(
                                    venta=ticket_vale,
                                    articulo=kit_item.articulo,
                                    cantidad=cantidad_articulo,
                                    precio_unitario=precio_proporcional,
                                    precio_total=precio_total_articulo,
                                    impuesto_especifico=impuesto_esp_item * cantidad_articulo
                                )
                                
                        except KitOferta.DoesNotExist:
                            print(f"ERROR - Vale: Kit con ID {kit_id} no encontrado")
                            raise Exception(f"Kit con ID {kit_id} no encontrado")
                        except Exception as e:
                            print(f"ERROR al procesar kit en vale: {e}")
                            import traceback
                            print(traceback.format_exc())
                            raise e
                    else:
                        # Es un artículo normal
                        articulo_id_limpio = clean_id(item.get('articuloId'))
                        
                        if not articulo_id_limpio:
                            print(f"ERROR - Vale: Item sin articuloId: {item}")
                            raise Exception(f"Item sin articuloId válido: {item}")
                        
                        try:
                            articulo = Articulo.objects.get(id=articulo_id_limpio, empresa=request.empresa)
                            
                            # Obtener impuesto específico del item (viene del carrito del POS)
                            impuesto_esp_item = Decimal(str(item.get('impuesto_especifico', 0)))
                            
                            print(f"DEBUG - Vale: Item: {item.get('nombre', 'Sin nombre')}")
                            print(f"DEBUG - Vale: Impuesto específico unitario: {impuesto_esp_item}")
                            print(f"DEBUG - Vale: Cantidad: {item['cantidad']}")
                            print(f"DEBUG - Vale: Impuesto específico total: {impuesto_esp_item * Decimal(str(item['cantidad']))}")
                            
                            VentaDetalle.objects.create(
                                venta=ticket_vale,
                                articulo=articulo,
                                cantidad=Decimal(str(item['cantidad'])),
                                precio_unitario=Decimal(str(item['precio'])),
                                precio_total=Decimal(str(item['total'])),
                                impuesto_especifico=impuesto_esp_item * Decimal(str(item['cantidad']))
                            )
                        except Articulo.DoesNotExist:
                            print(f"ERROR - Vale: Artículo con ID {articulo_id_limpio} no encontrado")
                            raise Exception(f"Artículo con ID {articulo_id_limpio} no encontrado")
                        except Exception as e:
                            print(f"ERROR al crear VentaDetalle en vale: {e}")
                            import traceback
                            print(traceback.format_exc())
                            raise e

                ticket_vale_id = ticket_vale.id
                ticket_vale_numero = numero_vale
                print(f"DEBUG - Ticket facturable (vale) #{numero_vale} generado exitosamente")
                
                # CIERRE DIRECTO: Procesar automáticamente el ticket y generar DTE
                # CRÍTICO: Refrescar desde BD para obtener la configuración más reciente
                estacion.refresh_from_db()
                cierre_directo_activo = bool(estacion.cierre_directo)
                cierre_directo_sesion = request.session.get('pos_cierre_directo', False)
                
                print("=" * 80)
                print("[DEBUG CIERRE DIRECTO] Verificando configuración:")
                print(f"  Estación ID: {estacion.id}")
                print(f"  Estación Nombre: {estacion.nombre}")
                print(f"  Estación.cierre_directo (BD refrescado): {estacion.cierre_directo} (tipo: {type(estacion.cierre_directo)})")
                print(f"  cierre_directo_activo (bool): {cierre_directo_activo} (tipo: {type(cierre_directo_activo)})")
                print(f"  Sesión pos_cierre_directo: {cierre_directo_sesion}")
                print(f"  Sesión pos_estacion_id: {request.session.get('pos_estacion_id')}")
                print(f"  ¿Entrará en cierre directo?: {cierre_directo_activo}")
                print("=" * 80)
                
                if cierre_directo_activo and tipo_doc_planeado in ['factura', 'boleta', 'guia']:
                    print("[OK] CIERRE DIRECTO ACTIVO - Procesando automaticamente")
                else:
                    print("[INFO] CIERRE DIRECTO DESACTIVADO O NO APLICA A ESTE DOCUMENTO")
                
                if cierre_directo_activo and tipo_doc_planeado in ['factura', 'boleta', 'guia']:
                    print(f"[CIERRE DIRECTO] Procesando ticket automaticamente")
                    
                    # Procesar el ticket automáticamente
                    try:
                        from caja.models import AperturaCaja, Caja, VentaProcesada, MovimientoCaja
                        from django.db import transaction
                        
                        apertura_activa = _apertura_caja_estacion(request.empresa, estacion, sucursal_activa)
                        
                        if not apertura_activa:
                            return JsonResponse({
                                'success': False,
                                'error': 'sin_caja',
                                'message': 'Esta estación no tiene una caja abierta. Abra la caja asociada a esta estación.',
                            }, status=400)
                        
                        # Obtener forma de pago por defecto (Efectivo)
                        forma_pago = FormaPago.objects.filter(
                            empresa=request.empresa,
                            codigo__iexact='EF'
                        ).first()
                        
                        if not forma_pago:
                            # Si no existe efectivo, usar la primera forma de pago activa
                            forma_pago = FormaPago.objects.filter(
                                empresa=request.empresa,
                                activo=True
                            ).first()
                        
                        if not forma_pago:
                            print(f"[WARN] CIERRE DIRECTO: No hay formas de pago configuradas")
                            return JsonResponse({
                                'success': False,
                                'message': 'No hay formas de pago configuradas'
                            }, status=400)
                        
                        # Procesar el ticket con transacción atómica
                        with transaction.atomic():
                            # Generar número de venta temporal (será reemplazado por el folio del DTE)
                            # Buscar el número más alto existente
                            ventas_existentes = Venta.objects.filter(
                                empresa=request.empresa
                            ).order_by('-numero_venta')
                            
                            numero = 1
                            if ventas_existentes.exists():
                                for venta_temp in ventas_existentes[:20]:
                                    try:
                                        num_actual = int(venta_temp.numero_venta)
                                        if num_actual >= numero:
                                            numero = num_actual + 1
                                    except ValueError:
                                        continue
                            
                            # Buscar número disponible
                            numero_venta_temp = f"{numero:06d}"
                            while Venta.objects.filter(
                                empresa=request.empresa,
                                numero_venta=numero_venta_temp
                            ).exists():
                                numero += 1
                                numero_venta_temp = f"{numero:06d}"
                            
                            print(f"[CIERRE DIRECTO] Numero de venta temporal: {numero_venta_temp}")
                            
                            # Primero generar el DTE para obtener el folio correcto
                            dte = None
                            numero_venta_final = numero_venta_temp
                            
                            if tipo_doc_planeado in ['factura', 'boleta', 'guia']:
                                try:
                                    from facturacion_electronica.dte_service import DTEService
                                    from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF
                                    
                                    print(f"[CIERRE DIRECTO] Verificando si ya existe DTE para preventa {preventa.id}...")
                                    
                                    # Mapear tipo de documento a código SII
                                    tipo_dte_map = {
                                        'factura': '33',  # Factura Electrónica
                                        'boleta': '39',   # Boleta Electrónica
                                        'guia': '52',     # Guía de Despacho Electrónica
                                    }
                                    tipo_dte_codigo = tipo_dte_map.get(tipo_doc_planeado, '39')
                                    
                                    # VALIDAR FOLIOS DISPONIBLES ANTES DE CONTINUAR
                                    print(f"[VALIDACION] Verificando folios disponibles para tipo DTE {tipo_dte_codigo}...")
                                    from facturacion_electronica.models import ArchivoCAF
                                    caf_disponible = ArchivoCAF.objects.filter(
                                        empresa=request.empresa,
                                        tipo_documento=tipo_dte_codigo,
                                        estado='activo'
                                    ).first()
                                    
                                    if not caf_disponible:
                                        nombres_doc = {'33': 'Facturas', '39': 'Boletas', '52': 'Guías de Despacho'}
                                        nombre_doc = nombres_doc.get(tipo_dte_codigo, 'Documentos')
                                        
                                        print(f"[ERROR] NO HAY FOLIOS DISPONIBLES para {nombre_doc}")
                                        return JsonResponse({
                                            'success': False,
                                            'error': 'sin_folios',
                                            'message': f'No hay folios disponibles para emitir {nombre_doc}',
                                            'detalle': f'Debe cargar un archivo CAF activo para {nombre_doc} en Facturación Electrónica → Gestión de CAF',
                                            'tipo_documento': data['tipo_documento']
                                        }, status=400)
                                    
                                    # Verificar si ya existe un DTE para este ticket
                                    # Buscar por VentaProcesada asociada al ticket
                                    from caja.models import VentaProcesada as VentaProcesadaCheck
                                    venta_proc_existente = VentaProcesadaCheck.objects.filter(
                                        venta_preventa=preventa,
                                        dte_generado__isnull=False
                                    ).first()
                                    
                                    if venta_proc_existente and venta_proc_existente.dte_generado:
                                        # Ya existe un DTE para este ticket, reutilizarlo
                                        dte = venta_proc_existente.dte_generado
                                        numero_venta_final = f"{dte.folio:06d}"
                                        print(f"[OK] CIERRE DIRECTO: DTE ya existe - Folio {dte.folio} (reutilizando)")
                                        
                                        # Actualizar el número de venta de preventa
                                        preventa.numero_venta = numero_venta_final
                                        preventa.tipo_documento = data['tipo_documento']
                                        preventa.estado = 'confirmada'
                                        preventa.facturado = True  # ← Marcar como facturado
                                        preventa.save()
                                    else:
                                        # No existe DTE, generar uno nuevo
                                        print(f"[CIERRE DIRECTO] Generando DTE nuevo para obtener folio...")
                                        
                                        # Preparar venta temporal para generar DTE
                                        preventa.numero_venta = numero_venta_temp
                                        preventa.tipo_documento = data['tipo_documento']
                                        preventa.estado = 'confirmada'
                                        preventa.facturado = True  # ← Marcar como facturado
                                        preventa.fecha = fecha_documento_caja(apertura_activa)
                                        preventa.save()
                                        
                                        # Generar DTE
                                        dte_service = DTEService(request.empresa)
                                        dte = dte_service.generar_dte_desde_venta(preventa, tipo_dte_codigo)
                                        
                                        if dte:
                                            # Usar el folio del DTE como número de venta final
                                            numero_venta_final = f"{dte.folio:06d}"
                                            print(f"[OK] CIERRE DIRECTO: DTE generado - Folio {dte.folio}")
                                            print(f"[OK] CIERRE DIRECTO: Número de venta final actualizado a: {numero_venta_final}")
                                            
                                            # Actualizar el número de venta del preventa con el folio
                                            preventa.numero_venta = numero_venta_final
                                            preventa.save()
                                        
                                except Exception as e_dte:
                                    print(f"[ERROR] CIERRE DIRECTO: Error al generar DTE: {e_dte}")
                                    import traceback
                                    traceback.print_exc()
                                    raise
                            
                            if not dte:
                                raise ValueError('No se pudo generar el DTE. Revise el CAF y los datos del cliente.')
                            
                            # Verificar si ya existe una venta final con ese folio
                            venta_final = Venta.objects.filter(
                                empresa=request.empresa,
                                tipo_documento=tipo_doc_planeado,
                                numero_venta=numero_venta_final
                            ).first()
                            
                            if not venta_final:
                                # Crear venta final definitiva solo si no existe
                                venta_final = Venta.objects.create(
                                    empresa=request.empresa,
                                    sucursal=preventa.sucursal,  # Usar sucursal del ticket
                                    estacion_trabajo=preventa.estacion_trabajo or estacion,
                                    tipo_documento=tipo_doc_planeado,
                                    numero_venta=numero_venta_final,
                                    cliente=cliente,
                                    vendedor=preventa.vendedor,
                                    estado='confirmada',
                                    subtotal=preventa.subtotal,
                                    descuento=preventa.descuento,
                                    neto=preventa.neto,
                                    iva=preventa.iva,
                                    total=preventa.total,
                                    fecha=fecha_documento_caja(apertura_activa),
                                    usuario_creacion=request.user
                                )
                                
                                # Copiar detalles del ticket a la venta final
                                for detalle in preventa.ventadetalle_set.all():
                                    VentaDetalle.objects.create(
                                        venta=venta_final,
                                        articulo=detalle.articulo,
                                        cantidad=detalle.cantidad,
                                        precio_unitario=detalle.precio_unitario,
                                        precio_total=detalle.precio_total,
                                        impuesto_especifico=detalle.impuesto_especifico
                                    )
                                print(f"[OK] CIERRE DIRECTO: Venta final creada - ID {venta_final.id}")
                            else:
                                print(f"[INFO] CIERRE DIRECTO: Venta final ya existe - ID {venta_final.id}, reutilizando")
                                # CRÍTICO: Asegurar que el tipo de documento sea el correcto
                                if venta_final.tipo_documento != tipo_doc_planeado:
                                    print(f"[FIX] Corrigiendo tipo de documento de {venta_final.tipo_documento} a {tipo_doc_planeado}")
                                    venta_final.tipo_documento = tipo_doc_planeado
                                    venta_final.save()
                            
                            # Si hay DTE, asociarlo a la venta final
                            if dte:
                                dte.venta = venta_final
                                dte.save()
                                
                                # Generar hoja de ruta automáticamente si aplica
                                if tipo_doc_planeado == 'factura' and venta_final.cliente:
                                    try:
                                        from pedidos.utils_hoja_ruta import generar_hoja_ruta_automatica
                                        hoja_ruta = generar_hoja_ruta_automatica(dte, venta_final, request.empresa)
                                        if hoja_ruta:
                                            print(f"[OK] CIERRE DIRECTO: Hoja de ruta generada automáticamente: {hoja_ruta.numero_ruta}")
                                    except Exception as e_hr:
                                        print(f"[WARN] CIERRE DIRECTO: Error al generar hoja de ruta automática: {e_hr}")
                                        import traceback
                                        traceback.print_exc()
                            
                            # Crear movimiento de caja (solo si no es guía de despacho)
                            movimiento_caja = None
                            if tipo_doc_planeado != 'guia':
                                movimiento_caja = MovimientoCaja.objects.create(
                                    apertura_caja=apertura_activa,
                                    venta=venta_final,
                                    tipo='venta',
                                    forma_pago=forma_pago,
                                    monto=total,
                                    descripcion=f"{tipo_doc_planeado.title()} #{numero_venta_final}",
                                    usuario=request.user
                                )
                                
                                # Recalcular totales de la apertura
                                apertura_activa.calcular_totales()
                            
                            # Crear venta procesada con los campos correctos del modelo
                            venta_procesada = VentaProcesada.objects.create(
                                venta_preventa=ticket_vale,
                                venta_final=venta_final,
                                apertura_caja=apertura_activa,
                                movimiento_caja=movimiento_caja,
                                usuario_proceso=request.user,
                                monto_recibido=total,
                                monto_cambio=Decimal('0.00'),
                                stock_descontado=True,
                                dte_generado=dte
                            )
                            
                            # Descontar stock
                            from inventario.models import Stock
                            bodega_caja = apertura_activa.caja.bodega
                            
                            for detalle in ticket_vale.ventadetalle_set.all():
                                # Buscar stock en la bodega de la caja
                                stock = Stock.objects.filter(
                                    empresa=request.empresa,
                                    bodega=bodega_caja,
                                    articulo=detalle.articulo
                                ).first()
                                
                                if stock:
                                    stock.cantidad -= detalle.cantidad
                                    stock.save()
                                    print(f"[CIERRE DIRECTO] Stock descontado: {detalle.articulo.nombre} - {detalle.cantidad}")
                            
                            # Generar URL del documento y enviar al SII si corresponde
                            doc_url = None
                            impresion_silenciosa = False
                            if dte:
                                # Generar URL del documento electrónico con parámetros de autoclose y return al POS
                                from django.urls import reverse
                                from urllib.parse import quote
                                doc_url_base = reverse('facturacion_electronica:ver_factura_electronica', args=[dte.pk])
                                pos_url = reverse('ventas:pos_view')
                                doc_url = f"{doc_url_base}?auto=1&autoclose=1&autoclose_delay=1000&return_url={quote(pos_url, safe='')}"
                                
                                # Enviar al SII si está configurado (en segundo plano)
                                if estacion.enviar_sii_directo and request.empresa.facturacion_electronica:
                                    try:
                                        from facturacion_electronica.background_sender import get_background_sender
                                        
                                        sender = get_background_sender()
                                        if sender.enviar_dte(dte.id, request.empresa.id):
                                            print("[OK] CIERRE DIRECTO: DTE agregado a cola de envío (background)")
                                        else:
                                            print("[WARN] CIERRE DIRECTO: No se pudo agregar DTE a cola")
                                    except Exception as e_envio:
                                        print(f"[WARN] CIERRE DIRECTO: Error al iniciar envío background: {e_envio}")

                                try:
                                    from caja.impresion_utils import encolar_impresion_agente

                                    impresion_silenciosa = encolar_impresion_agente(
                                        request.empresa,
                                        venta_final,
                                        estacion=estacion,
                                        dte=dte,
                                        tipo_documento='dte',
                                    )
                                    if impresion_silenciosa:
                                        print("[OK] CIERRE DIRECTO: DTE ENCOLADO PARA AGENTE LOCAL")
                                    else:
                                        print("[WARN] CIERRE DIRECTO: No se encontró caja para encolar DTE")
                                except Exception as e_imp:
                                    print(f"[ERROR] CIERRE DIRECTO: Error al encolar DTE para agente local: {e_imp}")
                            
                            # Marcar ticket como procesado y facturado
                            ticket_vale.estado = 'confirmada'
                            ticket_vale.facturado = True  # ← Marcar como facturado
                            ticket_vale.save()
                            _finalizar_dte_cierre_directo(dte, venta_final, forma_pago, apertura_activa)
                            
                            print("=" * 80)
                            print("[OK] VENTA PROCESADA EXITOSAMENTE")
                            print(f"   Venta Final ID: {venta_final.id}")
                            print(f"   Numero: {numero_venta_final}")
                            print(f"   Tipo: {data['tipo_documento']}")
                            print(f"   Total: ${total}")
                            print(f"   DTE Generado: {dte.id if dte else None}")
                            print("=" * 80)
                            
                            # Retornar respuesta con documento generado
                            return JsonResponse({
                                'success': True,
                                'cierre_directo': True,
                                'tipo_documento': data['tipo_documento'],
                                'tipo_documento_planeado': tipo_doc_planeado,  # ← Agregar tipo planeado para el frontend
                                'numero_venta': numero_venta_final,
                                'doc_url': doc_url or '',
                                'ticket_vale_id': ticket_vale_id,
                                'ticket_vale_numero': ticket_vale_numero,
                                'venta_final_id': venta_final.id,
                                'impresion_silenciosa': impresion_silenciosa
                            })
                    
                    except Exception as e_cierre:
                        print(f"[ERROR] ERROR en cierre directo: {e_cierre}")
                        import traceback
                        traceback.print_exc()
                        return JsonResponse({
                            'success': False,
                            'error': 'cierre_directo',
                            'message': f'No se pudo emitir el documento con cierre directo: {e_cierre}',
                        }, status=400)
            
            # Retorno normal (sin cierre directo)
            # Retornar JSON con URL de redirección para que el frontend redirija
            from django.urls import reverse as django_reverse
            
            procesamiento_url = ""
            if ticket_vale_id:
                # Caso Factura Directa/Boleta Directa (modo manual)
                procesamiento_url = django_reverse('ventas:procesar_venta_pos', args=[ticket_vale_id])

            impresion_silenciosa = False
            if ticket_vale_id and data.get('tipo_documento') != 'cotizacion':
                try:
                    from caja.impresion_utils import encolar_impresion_agente

                    impresion_silenciosa = encolar_impresion_agente(
                        request.empresa,
                        ticket_vale,
                        estacion=estacion,
                        tipo_documento='vale' if tipo_doc_planeado == 'vale' else 'ticket',
                    )
                except Exception as e_imp:
                    print(f"[ERROR] POS: Error al encolar impresion local: {e_imp}")
             
            respuesta_normal = {
                'success': True,
                'numero_preventa': proximo_numero,
                'tipo_documento': data['tipo_documento'],
                'tipo_documento_planeado': tipo_doc_planeado,  # ← CRÍTICO para el frontend
                'preventa_id': preventa.id,
                'ticket_vale_id': ticket_vale_id,
                'ticket_vale_numero': ticket_vale_numero,
                'cierre_directo': False, 
                'redirect_url': '' if impresion_silenciosa else procesamiento_url,
                'impresion_silenciosa': impresion_silenciosa
            }
            print("=" * 80)
            print("[RETORNO NORMAL] Sin cierre directo - Respuesta JSON:")
            print(f"  cierre_directo: {respuesta_normal.get('cierre_directo')}")
            print(f"  ticket_vale_id: {respuesta_normal.get('ticket_vale_id')}")
            print(f"  tipo_documento: {respuesta_normal.get('tipo_documento')}")
            print(f"  tipo_documento_planeado: {respuesta_normal.get('tipo_documento_planeado')}")
            print(f"  redirect_url: {procesamiento_url}")
            print("=" * 80)
            return JsonResponse(respuesta_normal)
            
        except Exception as e:
            import traceback
            print("=" * 80)
            print("ERROR AL PROCESAR PREVENTA:")
            print(f"Error: {str(e)}")
            print("Traceback completo:")
            print(traceback.format_exc())
            print("=" * 80)
            return JsonResponse({'success': False, 'message': f'Error al procesar preventa: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# ========== ESTACIONES DE TRABAJO ==========

@login_required
@requiere_empresa
@permission_required('ventas.view_estaciontrabajo', raise_exception=True)
def descargar_agente_impresion(request):
    """Baja el programa de impresión (exe) para el PC de la estación."""
    from caja.views_impresion import descargar_agente
    return descargar_agente(request)


def _etiqueta_modalidad_estacion(estacion):
    if estacion is None:
        return ''
    modo = 'Cliente al inicio' if estacion.modo_pos == 'con_cliente' else 'Cliente al final'
    partes = [estacion.numero, modo]
    if estacion.cierre_directo:
        partes.append(
            'RUT al inicio' if estacion.flujo_cierre_directo == 'rut_inicio' else 'RUT al final'
        )
    emits = []
    if estacion.puede_vale:
        emits.append('Vale')
    if estacion.puede_ticket:
        emits.append('Ticket')
    if emits:
        partes.append('emite ' + ' / '.join(emits))
    return ' · '.join(str(p) for p in partes if p)


def _resolver_estacion_conectar(request, pk=None):
    """Estación de esta pantalla: URL, POST, GET o la abierta en el POS."""
    empresa = request.empresa
    qs = EstacionTrabajo.objects.filter(empresa=empresa).select_related(
        'sucursal', 'caja_impresion', 'impresora_vales'
    )
    if request.GET.get('elegir') == '1' and request.method != 'POST':
        return None
    estacion_id = pk or request.POST.get('estacion_id') or request.GET.get('estacion_id')
    if not estacion_id:
        estacion_id = request.session.get('pos_estacion_id')
    if not estacion_id:
        return None
    return qs.filter(id=estacion_id).first()


def _tomar_impresora_agente_vivo(estacion):
    """Si el programa ya corre, usa esa impresora. No pide descargar de nuevo."""
    from caja.models import Caja, ImpresoraAgente, asignar_impresora_estacion_desde_agente, caja_cola_para_estacion

    if estacion is None:
        return
    caja = getattr(estacion, 'caja_impresion', None) or caja_cola_para_estacion(estacion)
    if caja:
        asignar_impresora_estacion_desde_agente(caja)
    limite = timezone.now() - timedelta(seconds=180)
    qs = ImpresoraAgente.objects.filter(
        empresa_id=estacion.empresa_id,
        ultimo_reporte__gte=limite,
    ).select_related('caja')
    if estacion.sucursal_id:
        qs = qs.filter(sucursal_id=estacion.sucursal_id)
    ultima = qs.order_by('-en_uso', '-ultimo_reporte').first()
    if ultima is None:
        caja_viva = (
            Caja.objects.filter(
                empresa_id=estacion.empresa_id,
                activo=True,
                agente_ultimo_ping__gte=limite,
            )
            .order_by('-agente_ultimo_ping')
            .first()
        )
        if caja_viva and estacion.sucursal_id:
            caja_viva = (
                Caja.objects.filter(
                    pk=caja_viva.pk, sucursal_id=estacion.sucursal_id
                ).first() or caja_viva
            )
        if caja_viva:
            asignar_impresora_estacion_desde_agente(caja_viva)
        return
    if estacion.caja_impresion_id != ultima.caja_id:
        estacion.caja_impresion = ultima.caja
        estacion.save(update_fields=['caja_impresion'])
    asignar_impresora_estacion_desde_agente(ultima.caja, ultima.nombre)


@login_required
@requiere_empresa
@permission_required('ventas.view_estaciontrabajo', raise_exception=True)
def conectar_impresora_estacion(request, pk=None):
    """Conecta el programa de impresión a una estación, no a una caja de cobro."""
    from caja.models import CodigoVinculoImpresion, caja_cola_para_estacion
    from caja.views_impresion import _nuevo_codigo, _url_api_impresion

    empresa = request.empresa
    estaciones = (
        EstacionTrabajo.objects.filter(empresa=empresa, activo=True)
        .select_related('sucursal')
        .order_by('numero', 'nombre')
    )
    estacion = _resolver_estacion_conectar(request, pk)
    estacion_abierta_id = request.session.get('pos_estacion_id')
    codigo_mostrado = None
    error = None
    agente_en_linea = False

    if request.method == 'POST':
        post_id = request.POST.get('estacion_id')
        if post_id:
            estacion = EstacionTrabajo.objects.filter(
                empresa=empresa, id=post_id
            ).select_related('sucursal', 'caja_impresion', 'impresora_vales').first()
        if not estacion:
            error = 'Elija la estación de este computador.'
        elif not estacion.sucursal_id:
            error = 'Esta estación no tiene sucursal. Ábrala y asígnele una sucursal.'
        else:
            caja = caja_cola_para_estacion(estacion)
            if not caja:
                error = 'No se pudo preparar la impresión de esta estación.'
            else:
                codigo_mostrado = _nuevo_codigo()
                CodigoVinculoImpresion.objects.create(
                    codigo=codigo_mostrado,
                    empresa=empresa,
                    sucursal=estacion.sucursal,
                    caja=caja,
                    api_base_url=_url_api_impresion(request),
                    creado_por=request.user,
                    fecha_expiracion=timezone.now() + timedelta(hours=24),
                )
                estacion.refresh_from_db()

    if estacion and request.method != 'POST':
        _tomar_impresora_agente_vivo(estacion)
        estacion = EstacionTrabajo.objects.filter(pk=estacion.pk).select_related(
            'sucursal', 'caja_impresion', 'impresora_vales'
        ).first() or estacion

    if estacion:
        ping = getattr(getattr(estacion, 'caja_impresion', None), 'agente_ultimo_ping', None)
        if ping and (timezone.now() - ping).total_seconds() < 180:
            agente_en_linea = True
        elif estacion.sucursal_id:
            from caja.models import Caja
            agente_en_linea = Caja.objects.filter(
                empresa=estacion.empresa,
                sucursal_id=estacion.sucursal_id,
                activo=True,
                agente_ultimo_ping__gte=timezone.now() - timedelta(seconds=180),
            ).exists()

    info_imp = estacion.info_impresora() if estacion else {
        'nombre': '', 'en_linea': False, 'conectada': False,
    }
    if request.GET.get('estado') == '1':
        if estacion:
            _tomar_impresora_agente_vivo(estacion)
            estacion = EstacionTrabajo.objects.filter(pk=estacion.pk).select_related(
                'sucursal', 'caja_impresion', 'impresora_vales'
            ).first() or estacion
            info_imp = estacion.info_impresora()
            ping = getattr(estacion.caja_impresion, 'agente_ultimo_ping', None) if estacion.caja_impresion_id else None
            agente_en_linea = bool(ping and (timezone.now() - ping).total_seconds() < 180)
        return JsonResponse({
            'ok': bool(estacion),
            'agente_en_linea': agente_en_linea,
            'nombre': info_imp.get('nombre') or '',
            'conectada': bool(info_imp.get('conectada') or agente_en_linea),
            'en_linea': bool(info_imp.get('en_linea') or agente_en_linea),
        })

    return render(request, 'ventas/conectar_impresora.html', {
        'empresa': empresa,
        'estaciones': estaciones,
        'estacion': estacion,
        'estacion_abierta': bool(estacion and estacion_abierta_id == estacion.id),
        'modalidad': _etiqueta_modalidad_estacion(estacion),
        'codigo': codigo_mostrado,
        'agente_en_linea': agente_en_linea,
        'info_impresora': info_imp,
        'error': error,
    })


@login_required
@requiere_empresa
@permission_required('ventas.view_estaciontrabajo', raise_exception=True)
@never_cache
def estaciontrabajo_list(request):
    """Lista de estaciones de trabajo"""
    ensure_estacion_caja_impresion()
    from caja.models import ensure_impresoras_agente
    ensure_impresoras_agente()
    estaciones = EstacionTrabajo.objects.filter(empresa=request.empresa).select_related(
        'sucursal', 'caja_impresion', 'impresora_vales'
    ).prefetch_related('caja_impresion__impresoras_agente').order_by('numero')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        estaciones = estaciones.filter(
            Q(numero__icontains=search) |
            Q(nombre__icontains=search) |
            Q(sucursal__nombre__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(estaciones, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    estacion_actual = None
    estacion_id = request.session.get('pos_estacion_id')
    if estacion_id:
        estacion_actual = EstacionTrabajo.objects.filter(pk=estacion_id, empresa=request.empresa).first()
    if not estacion_actual:
        terminal = _buscar_terminal_pos(request)
        if terminal and terminal.estacion_id and terminal.estacion and terminal.estacion.empresa_id == request.empresa.id:
            estacion_actual = terminal.estacion

    from caja.impresion_utils import agente_impresion_en_linea
    from empresas.middleware import resolver_sucursal_operativa

    context = {
        'page_obj': page_obj,
        'search': search,
        'form_crear': EstacionTrabajoForm(auto_id='crear_%s', empresa=request.empresa),
        'estacion_actual': estacion_actual,
        'alerta_agente_impresion': not agente_impresion_en_linea(
            request.empresa, resolver_sucursal_operativa(request)
        ),
    }
    
    return render(request, 'ventas/estaciontrabajo_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_estaciontrabajo', raise_exception=True)
def estaciontrabajo_create(request):
    """Crear nueva estación de trabajo"""
    if request.method == 'POST':
        form = EstacionTrabajoForm(request.POST, empresa=request.empresa)
        if form.is_valid():
            estacion = form.save(commit=False)
            estacion.empresa = request.empresa
            estacion.save()
            response = JsonResponse({'success': True, 'message': 'Estación de trabajo creada exitosamente'})
            response['Content-Type'] = 'application/json'
            return response
        else:
            response = JsonResponse({'success': False, 'errors': form.errors}, status=400)
            response['Content-Type'] = 'application/json'
            return response

    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
@permission_required('ventas.view_estaciontrabajo', raise_exception=True)
def estaciontrabajo_detail(request, pk):
    """Detalle de estación de trabajo"""
    try:
        estacion = EstacionTrabajo.objects.select_related(
            'caja_impresion', 'caja_impresion__sucursal', 'impresora_vales'
        ).get(pk=pk, empresa=request.empresa)
        return render(request, 'ventas/estaciontrabajo_detail.html', {'estacion': estacion})
    except EstacionTrabajo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Estación de trabajo no encontrada'})


@login_required
@requiere_empresa
@permission_required('ventas.change_estaciontrabajo', raise_exception=True)
def estaciontrabajo_edit(request, pk):
    """Editar estación de trabajo"""
    try:
        estacion = EstacionTrabajo.objects.get(pk=pk, empresa=request.empresa)

        if request.method == 'POST':
            form = EstacionTrabajoForm(request.POST, instance=estacion, empresa=request.empresa)
            if form.is_valid():
                estacion = form.save()  # Guardar y obtener la instancia actualizada
                
                # CRÍTICO: Refrescar desde BD para asegurar que tenemos los valores más recientes
                estacion.refresh_from_db()
                
                # Si esta estación está activa en el POS, actualizar la sesión
                if request.session.get('pos_estacion_id') == estacion.id:
                    _sincronizar_config_estacion(request, estacion)
                    request.session.save()
                    print("=" * 80)
                    print(f"[DEBUG] Sesión POS actualizada para estación activa ID {estacion.id}")
                    print(f"  Estación Nombre: {estacion.nombre}")
                    print(f"  cierre_directo (BD): {estacion.cierre_directo}")
                    print(f"  cierre_directo (Sesión): {request.session.get('pos_cierre_directo')}")
                    print(f"  enviar_sii_directo (BD): {estacion.enviar_sii_directo}")
                    print(f"  enviar_sii_directo (Sesión): {request.session.get('pos_enviar_sii_directo')}")
                    print("=" * 80)
                
                response = JsonResponse({'success': True, 'message': 'Estación de trabajo actualizada exitosamente'})
                response['Content-Type'] = 'application/json'
                return response
            else:
                response = JsonResponse({'success': False, 'errors': form.errors})
                response['Content-Type'] = 'application/json'
                return response

        form = EstacionTrabajoForm(instance=estacion, auto_id='editar_%s', empresa=request.empresa)
        return render(request, 'ventas/estaciontrabajo_form.html', {
            'form': form,
            'estacion': estacion,
        })

    except EstacionTrabajo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Estación de trabajo no encontrada'})


@login_required
@requiere_empresa
@permission_required('ventas.delete_estaciontrabajo', raise_exception=True)
def estaciontrabajo_delete(request, pk):
    """Eliminar estación de trabajo"""
    if request.method == 'POST':
        try:
            estacion = EstacionTrabajo.objects.get(pk=pk, empresa=request.empresa)
            estacion.delete()
            response = JsonResponse({'success': True, 'message': 'Estación de trabajo eliminada exitosamente'})
            response['Content-Type'] = 'application/json'
            return response
        except EstacionTrabajo.DoesNotExist:
            response = JsonResponse({'success': False, 'message': 'Estación de trabajo no encontrada'})
            response['Content-Type'] = 'application/json'
            return response
    
    response = JsonResponse({'success': False, 'message': 'Método no permitido'})
    response['Content-Type'] = 'application/json'
    return response


# ========== VALES ==========

@login_required
@requiere_empresa
def vale_html(request, pk):
    """Vista para imprimir vale de venta con código de barras"""
    try:
        # Intentar con tipo_documento='ticket' o 'vale'
        from django.db.models import Q
        try:
            venta = Venta.objects.get(Q(tipo_documento='ticket') | Q(tipo_documento='vale'), pk=pk, empresa=request.empresa)
        except Venta.DoesNotExist:
            # Fallback: buscar cualquier tipo de documento por ID
            venta = Venta.objects.get(pk=pk, empresa=request.empresa)
        
        detalles = VentaDetalle.objects.filter(venta=venta)
        
        # Verificar si el documento ya fue procesado para mostrar el tipo de documento final
        tipo_documento_final = None
        venta_procesada = None
        formas_pago_list = []
        
        if venta.tipo_documento in ['vale', 'ticket']:
            from caja.models import VentaProcesada, MovimientoCaja
            try:
                venta_procesada = VentaProcesada.objects.get(venta_preventa=venta)
                tipo_documento_final = venta_procesada.venta_final.tipo_documento
                
                # Obtener formas de pago de los movimientos de caja asociados a la venta final
                movimientos = MovimientoCaja.objects.filter(
                    venta=venta_procesada.venta_final,
                    tipo='venta'
                ).select_related('forma_pago').order_by('id')
                
                # Agrupar por forma de pago y sumar montos
                from decimal import Decimal
                formas_pago_dict = {}
                for mov in movimientos:
                    if mov.forma_pago:
                        fp_nombre = mov.forma_pago.nombre
                        if fp_nombre not in formas_pago_dict:
                            formas_pago_dict[fp_nombre] = {
                                'forma_pago': mov.forma_pago,
                                'monto': Decimal('0.00'),
                                'movimientos': []
                            }
                        formas_pago_dict[fp_nombre]['monto'] += mov.monto
                        formas_pago_dict[fp_nombre]['movimientos'].append(mov)
                
                # Convertir a lista para el template
                formas_pago_list = [
                    {
                        'forma_pago': fp_data['forma_pago'],
                        'monto': fp_data['monto'],
                        'movimientos': fp_data['movimientos']
                    }
                    for fp_data in formas_pago_dict.values()
                ]
            except VentaProcesada.DoesNotExist:
                pass
        
        context = {
            'venta': venta,
            'detalles': detalles,
            'empresa': request.empresa,
            'tipo_documento_final': tipo_documento_final,
            'venta_procesada': venta_procesada,
            'formas_pago_list': formas_pago_list,
        }
        
        # Determinar el template según el tipo de impresora configurado para vales
        empresa = request.empresa
        tipo_impresora = getattr(empresa, 'impresora_vale', 'laser')
        
        if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
            template_name = 'ventas/vale_termica.html'
            # vale_termica.html espera la variable 'vale' y 'copias_range'
            context['vale'] = venta
            
            n_copias = 1
            estacion = getattr(venta, 'estacion_trabajo', None)
            if not estacion:
                estacion_id = request.session.get('pos_estacion_id')
                if estacion_id:
                    from ventas.aislamiento import estacion_de_empresa
                    estacion = estacion_de_empresa(request.empresa, estacion_id)
            if estacion and getattr(estacion, 'empresa_id', None) == getattr(request.empresa, 'id', None):
                # Los vales del POS se guardan como ticket con tipo_documento_planeado='vale'.
                # Para copias, un vale debe respetar copias_vale de la estación.
                tipo_para_copias = venta.tipo_documento
                if tipo_para_copias == 'ticket' and venta.tipo_documento_planeado == 'vale':
                    tipo_para_copias = 'vale'
                n_copias = estacion.get_copias_por_tipo(tipo_para_copias)
            context['copias_range'] = range(n_copias)
        else:
            template_name = 'ventas/vale_html.html'
            
        return render(request, template_name, context)
    
    except Venta.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Documento no encontrado'})


@login_required
@requiere_empresa
def vale_termica(request, pk):
    """Vista HTML optimizada para impresoras térmicas (80mm)"""
    try:
        # Intentar con tipo_documento='ticket' o 'vale'
        from django.db.models import Q
        try:
            venta = Venta.objects.get(Q(tipo_documento='ticket') | Q(tipo_documento='vale'), pk=pk, empresa=request.empresa)
        except Venta.DoesNotExist:
            # Fallback: buscar cualquier tipo de documento por ID
            venta = Venta.objects.get(pk=pk, empresa=request.empresa)
        
        detalles = VentaDetalle.objects.filter(venta=venta)
        
        # Obtener configuración de copias de la estación (prioritario)
        n_copias = 1
        estacion = getattr(venta, 'estacion_trabajo', None)
        if not estacion:
            estacion_id = request.session.get('pos_estacion_id')
            if estacion_id:
                from ventas.aislamiento import estacion_de_empresa
                estacion = estacion_de_empresa(request.empresa, estacion_id)
        
        if estacion and getattr(estacion, 'empresa_id', None) == getattr(request.empresa, 'id', None):
            # Los vales del POS se guardan como ticket con tipo_documento_planeado='vale'.
            # Para copias, un vale debe respetar copias_vale de la estación.
            tipo_para_copias = venta.tipo_documento
            if tipo_para_copias == 'ticket' and venta.tipo_documento_planeado == 'vale':
                tipo_para_copias = 'vale'
            n_copias = estacion.get_copias_por_tipo(tipo_para_copias)
        
        context = {
            'vale': venta,
            'detalles': detalles,
            'nombre_impresora': request.GET.get('printer', ''),
            'copias_range': range(n_copias),
        }
        
        return render(request, 'ventas/vale_termica.html', context)
    
    except Venta.DoesNotExist:
        return HttpResponse("Documento no encontrado", status=404)


# ========== COTIZACIONES ==========

@login_required
@requiere_empresa
@requiere_permiso(['ventas.view_cotizacion', 'ventas.view_venta'])
def cotizacion_list(request):
    """Lista de cotizaciones"""
    cotizaciones = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='cotizacion'
    ).order_by('-fecha_creacion')
    
    # Filtro por estado: por defecto solo cotizaciones activas (pendiente, enviada, aceptada)
    estado = request.GET.get('estado', '')
    if estado == 'todas':
        # Mostrar todas sin excepción
        pass
    elif estado:
        cotizaciones = cotizaciones.filter(estado_cotizacion=estado)
    else:
        # Por defecto (Opción A): mostrar activas excluyendo convertidas, rechazadas y vencidas
        cotizaciones = cotizaciones.filter(
            Q(estado_cotizacion__in=['pendiente', 'enviada', 'aceptada']) |
            Q(estado_cotizacion__isnull=True) |
            Q(estado_cotizacion='')
        )
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        cotizaciones = cotizaciones.filter(
            Q(numero_venta__icontains=search) |
            Q(cliente__nombre__icontains=search) |
            Q(cliente__rut__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(cotizaciones, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opciones de estado para el filtro
    ESTADO_CHOICES = [
        ('', 'Activas (Pendientes, Enviadas, Aceptadas)'),
        ('todas', 'Todas las cotizaciones'),
        ('pendiente', 'Pendiente'),
        ('enviada', 'Enviada'),
        ('aceptada', 'Aceptada'),
        ('convertida', 'Convertida en Venta'),
        ('rechazada', 'Rechazada / Cancelada'),
        ('vencida', 'Vencida'),
    ]
    
    # Estadísticas para el Estilo Piedra
    stats = {
        'total_pendientes': Venta.objects.filter(empresa=request.empresa, tipo_documento='cotizacion', estado_cotizacion__in=['pendiente', 'enviada', None, '']).count(),
        'monto_pendientes': Venta.objects.filter(empresa=request.empresa, tipo_documento='cotizacion', estado_cotizacion__in=['pendiente', 'enviada', None, '']).aggregate(Sum('total'))['total__sum'] or 0,
        'total_aceptadas': Venta.objects.filter(empresa=request.empresa, tipo_documento='cotizacion', estado_cotizacion='aceptada').count(),
        'monto_aceptadas': Venta.objects.filter(empresa=request.empresa, tipo_documento='cotizacion', estado_cotizacion='aceptada').aggregate(Sum('total'))['total__sum'] or 0,
        'total_convertidas': Venta.objects.filter(empresa=request.empresa, tipo_documento='cotizacion', estado_cotizacion='convertida').count(),
        'total_hoy': Venta.objects.filter(empresa=request.empresa, tipo_documento='cotizacion', fecha_creacion__date=datetime.now().date()).count(),
        'total_mes': Venta.objects.filter(empresa=request.empresa, tipo_documento='cotizacion', fecha_creacion__month=datetime.now().month).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'estado': estado,
        'estado_choices': ESTADO_CHOICES,
        'stats': stats,
    }
    
    return render(request, 'ventas/cotizacion_list.html', context)


@login_required
@requiere_empresa
@requiere_permiso(['ventas.add_cotizacion', 'ventas.add_venta'])
def cotizacion_create(request):
    """Crear nueva cotización con la interfaz estandarizada de propuestas y pedidos"""
    from articulos.models import Articulo
    from .forms import CotizacionForm, CotizacionItemFormSet
    
    empresa = request.empresa
    
    if request.method == 'POST':
        form = CotizacionForm(request.POST, empresa=empresa)
        formset = CotizacionItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
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
                    fecha = form.cleaned_data.get('fecha') or timezone.localdate()
                    
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
                        fecha=fecha,
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
                        usuario_creacion=request.user
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
                    
                messages.success(request, f'Cotización #{cotizacion.numero_venta} creada exitosamente.')
                return redirect('ventas:cotizacion_list')
            except Exception as e:
                import traceback
                print(f"Error al crear cotización: {str(e)}")
                print(traceback.format_exc())
                messages.error(request, f'Error al guardar cotización: {str(e)}')
        else:
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'Campo {field}: {error}')
            if formset.errors:
                for i, form_errors in enumerate(formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            for error in errors:
                                messages.error(request, f'Ítem {i+1} - {field}: {error}')
    else:
        form = CotizacionForm(empresa=empresa, initial={'fecha': timezone.localdate()})
        formset = CotizacionItemFormSet()

    from pedidos.views import articulos_con_stock
    articulos_empresa = articulos_con_stock(empresa)
    
    context = {
        'form': form,
        'formset': formset,
        'articulos_empresa': articulos_empresa,
        'empresa': empresa,
    }
    return render(request, 'ventas/cotizacion_form.html', context)


@login_required
@requiere_empresa
@requiere_permiso(['ventas.change_cotizacion', 'ventas.change_venta'])
def cotizacion_edit(request, pk):
    """Editar cotización existente"""
    from articulos.models import Articulo
    from .forms import CotizacionForm, CotizacionItemFormSet
    
    empresa = request.empresa
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=empresa, tipo_documento='cotizacion')
    
    if cotizacion.estado_cotizacion == 'convertida':
        messages.warning(request, 'No se puede editar una cotización que ya ha sido convertida en venta.')
        return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)
        
    if request.method == 'POST':
        form = CotizacionForm(request.POST, instance=cotizacion, empresa=empresa)
        formset = CotizacionItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    cotizacion = form.save(commit=False)
                    cotizacion.empresa = empresa
                    cotizacion.save()
                    
                    cotizacion.ventadetalle_set.all().delete()
                    
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
                    
                messages.success(request, f'Cotización #{cotizacion.numero_venta} actualizada exitosamente.')
                return redirect('ventas:cotizacion_list')
            except Exception as e:
                import traceback
                print(f"Error al editar cotización: {str(e)}")
                print(traceback.format_exc())
                messages.error(request, f'Error al actualizar cotización: {str(e)}')
        else:
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'Campo {field}: {error}')
            if formset.errors:
                for i, form_errors in enumerate(formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            for error in errors:
                                messages.error(request, f'Ítem {i+1} - {field}: {error}')
    else:
        form = CotizacionForm(instance=cotizacion, empresa=empresa)
        
        initial_items = []
        for det in cotizacion.ventadetalle_set.all():
            initial_items.append({
                'id': det.id,
                'articulo': det.articulo,
                'cantidad': det.cantidad,
                'precio_unitario': det.precio_unitario,
                'descuento_porcentaje': Decimal('0'),
                'impuesto_porcentaje': 19
            })
        formset = CotizacionItemFormSet(initial=initial_items)
        if initial_items:
            formset.extra = 0

    from pedidos.views import articulos_con_stock
    articulos_empresa = articulos_con_stock(empresa)
    
    context = {
        'cotizacion': cotizacion,
        'form': form,
        'formset': formset,
        'articulos_empresa': articulos_empresa,
        'empresa': empresa,
    }
    return render(request, 'ventas/cotizacion_form.html', context)


@login_required
@requiere_empresa
@requiere_permiso(['ventas.delete_cotizacion', 'ventas.delete_venta'])
def cotizacion_delete(request, pk):
    """Eliminar una cotización"""
    empresa = request.empresa
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=empresa, tipo_documento='cotizacion')
    
    if cotizacion.estado_cotizacion == 'convertida':
        messages.error(request, 'No se puede eliminar una cotización que ya fue convertida en venta.')
        return redirect('ventas:cotizacion_list')
        
    num = cotizacion.numero_venta
    cotizacion.ventadetalle_set.all().delete()
    cotizacion.delete()
    messages.success(request, f'Cotización #{num} eliminada exitosamente.')
    return redirect('ventas:cotizacion_list')


@login_required
@requiere_empresa
@requiere_permiso(['ventas.view_cotizacion', 'ventas.view_venta'])
def cotizacion_detail(request, pk):
    """Detalle de cotización"""
    from pedidos.models_transporte import Vehiculo, Chofer
    
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    detalles = VentaDetalle.objects.filter(venta=cotizacion).select_related('articulo')
    
    vehiculos = Vehiculo.objects.filter(empresa=request.empresa, activo=True).order_by('patente')
    choferes = Chofer.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    venta_convertida = None
    dte_convertido = None
    if cotizacion.estado_cotizacion == 'convertida':
        venta_convertida = Venta.objects.filter(
            empresa=request.empresa,
            observaciones__icontains=f"Convertida desde cotización #{cotizacion.numero_venta}"
        ).order_by('-id').first()
        if venta_convertida:
            dte_convertido = getattr(venta_convertida, 'dte', None) or getattr(venta_convertida, 'dte_asociado', None)
    
    context = {
        'cotizacion': cotizacion,
        'detalles': detalles,
        'venta_convertida': venta_convertida,
        'dte_convertido': dte_convertido,
        'estados': Venta.ESTADO_COTIZACION_CHOICES,
        'tipos_venta': [
            ('factura', 'Factura'),
            ('boleta', 'Boleta'),
            ('guia', 'Guía de Despacho'),
        ],
        'tipo_despacho_choices': Venta.TIPO_DESPACHO_CHOICES,
        'tipo_despacho_sii_choices': TIPO_DESPACHO_SII_CHOICES,
        'vehiculos': vehiculos,
        'choferes': choferes,
        'rut_empresa': request.empresa.rut or '',
        'hora_actual': timezone.localtime().strftime('%H:%M'),
        'today': timezone.localdate(),
        'abrir_modal': request.GET.get('modal'),
    }
    
    return render(request, 'ventas/cotizacion_detail.html', context)


@login_required
@requiere_empresa
def cotizacion_pdf(request, pk):
    """Generar PDF de cotización"""
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    detalles = VentaDetalle.objects.filter(venta=cotizacion).select_related('articulo')
    
    # Crear buffer para el PDF
    buffer = io.BytesIO()
    
    # Crear documento PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo personalizado para el título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    # Estilo para subtítulos
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.HexColor('#34495e')
    )
    
    # Estilo para texto normal
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Contenido del PDF
    story = []
    
    # Logo de la empresa (si existe)
    if cotizacion.empresa.logo:
        try:
            logo_path = cotizacion.empresa.logo.path
            logo = Image(logo_path, width=2*inch, height=1*inch)
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 20))
        except:
            pass
    
    # Título
    story.append(Paragraph("COTIZACIÓN", title_style))
    story.append(Spacer(1, 20))
    
    # Información de la empresa
    empresa_info = f"""
    <b>{cotizacion.empresa.razon_social}</b><br/>
    RUT: {cotizacion.empresa.rut}<br/>
    {cotizacion.empresa.direccion}<br/>
    {cotizacion.empresa.comuna}, {cotizacion.empresa.ciudad}<br/>
    Teléfono: {cotizacion.empresa.telefono}<br/>
    Email: {cotizacion.empresa.email}
    """
    story.append(Paragraph(empresa_info, normal_style))
    story.append(Spacer(1, 20))
    
    # Información de la cotización
    cotizacion_info = f"""
    <b>Número de Cotización:</b> {cotizacion.numero_venta}<br/>
    <b>Fecha:</b> {cotizacion.fecha.strftime('%d-%m-%Y')}<br/>
    <b>Válida hasta:</b> {(cotizacion.fecha + timezone.timedelta(days=30)).strftime('%d-%m-%Y')}<br/>
    <b>Vendedor:</b> {cotizacion.vendedor.nombre if cotizacion.vendedor else 'No asignado'}
    """
    story.append(Paragraph(cotizacion_info, normal_style))
    story.append(Spacer(1, 20))
    
    # Información del cliente
    if cotizacion.cliente:
        cliente_info = f"""
        <b>Cliente:</b><br/>
        {cotizacion.cliente.nombre}<br/>
        RUT: {cotizacion.cliente.rut}<br/>
        {cotizacion.cliente.direccion}<br/>
        {cotizacion.cliente.comuna}, {cotizacion.cliente.ciudad}<br/>
        Teléfono: {cotizacion.cliente.telefono}<br/>
        Email: {cotizacion.cliente.email}
        """
        story.append(Paragraph(cliente_info, normal_style))
        story.append(Spacer(1, 20))
    
    # Tabla de productos
    story.append(Paragraph("DETALLE DE PRODUCTOS", subtitle_style))
    
    # Datos de la tabla
    table_data = [['Código', 'Descripción', 'Cantidad', 'Precio Unit.', 'Total']]
    
    for detalle in detalles:
        table_data.append([
            detalle.articulo.codigo,
            detalle.articulo.descripcion,
            str(detalle.cantidad),
            f"${detalle.precio_unitario:,.0f}".replace(',', '.'),
            f"${detalle.precio_total:,.0f}".replace(',', '.')
        ])
    
    # Crear tabla
    table = Table(table_data, colWidths=[1*inch, 3*inch, 0.8*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Totales
    totales_data = [
        ['', '', '', 'Subtotal:', f"${cotizacion.subtotal:,.0f}".replace(',', '.')],
        ['', '', '', 'Descuento:', f"${cotizacion.descuento:,.0f}".replace(',', '.')],
        ['', '', '', 'Neto:', f"${cotizacion.neto:,.0f}".replace(',', '.')],
        ['', '', '', 'IVA (19%):', f"${cotizacion.iva:,.0f}".replace(',', '.')],
        ['', '', '', 'Imp. Específico:', f"${cotizacion.impuesto_especifico:,.0f}".replace(',', '.')],
        ['', '', '', 'TOTAL:', f"${cotizacion.total:,.0f}".replace(',', '.')],
    ]
    
    totales_table = Table(totales_data, colWidths=[1*inch, 3*inch, 0.8*inch, 1*inch, 1*inch])
    totales_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
    ]))
    
    story.append(totales_table)
    story.append(Spacer(1, 30))
    
    # Observaciones
    if cotizacion.observaciones:
        story.append(Paragraph("OBSERVACIONES", subtitle_style))
        story.append(Paragraph(cotizacion.observaciones, normal_style))
        story.append(Spacer(1, 20))
    
    # Términos y condiciones
    terminos = """
    <b>TÉRMINOS Y CONDICIONES:</b><br/>
    • Esta cotización tiene una validez de 30 días desde su emisión.<br/>
    • Los precios están expresados en pesos chilenos e incluyen IVA.<br/>
    • Los productos están sujetos a disponibilidad de stock.<br/>
    • El pago debe realizarse según las condiciones acordadas.<br/>
    • Cualquier modificación debe ser aprobada por escrito.
    """
    story.append(Paragraph(terminos, normal_style))
    
    # Construir PDF
    doc.build(story)
    
    # Obtener el PDF del buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Crear respuesta HTTP
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cotizacion_{cotizacion.numero_venta}.pdf"'
    
    return response


@login_required
@requiere_empresa
@requiere_permiso(['ventas.view_cotizacion', 'ventas.view_venta'])
def cotizacion_enviar_email(request, pk):
    """Envía la cotización por correo, con el PDF adjunto."""
    from django.conf import settings
    from django.core.exceptions import ValidationError
    from django.core.mail import EmailMessage
    from django.core.validators import validate_email

    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    destino = redirect('ventas:cotizacion_detail', pk=cotizacion.pk)

    if request.method != 'POST':
        return destino

    email = (request.POST.get('email') or '').strip()
    if not email and cotizacion.cliente:
        email = (cotizacion.cliente.email or '').strip()
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, 'Indique un correo válido para enviar la cotización.')
        return destino

    from utilidades.utils import aviso_correo_no_entregado, conexion_correo, datos_smtp
    smtp = datos_smtp(cotizacion.empresa)
    if not smtp['listo']:
        messages.error(request, aviso_correo_no_entregado(email))
        return destino

    try:
        pdf_response = cotizacion_pdf(request, pk)
        pdf_bytes = getattr(pdf_response, 'content', b'') or b''
    except Exception as exc:
        messages.error(request, f'No se pudo generar el PDF de la cotización ({exc}).')
        return destino
    if not pdf_bytes:
        messages.error(request, 'No se pudo generar el PDF de la cotización.')
        return destino

    empresa = cotizacion.empresa
    cliente_nombre = cotizacion.cliente.nombre if cotizacion.cliente else 'Cliente'
    total = f"{int(round(float(cotizacion.total or 0))):,}".replace(',', '.')
    extra = (request.POST.get('mensaje') or '').strip()
    extra_txt = f"{extra}\n\n" if extra else ""
    cuerpo = (
        f"Estimado/a {cliente_nombre},\n\n"
        f"{extra_txt}"
        f"Adjuntamos la cotización N° {cotizacion.numero_venta} de {empresa.nombre}.\n"
        f"Total: ${total}\n\n"
        f"Quedamos atentos a su confirmación.\n\n"
        f"{empresa.nombre}\n"
        f"{empresa.telefono or ''}\n"
        f"{empresa.email or ''}\n"
    )
    copia = (empresa.email or '').strip()
    try:
        mensaje = EmailMessage(
            subject=f"Cotización N° {cotizacion.numero_venta} — {empresa.nombre}",
            body=cuerpo,
            from_email=smtp['from_email'] or empresa.email,
            to=[email],
            cc=[copia] if copia and copia.lower() != email.lower() else None,
            connection=conexion_correo(empresa),
        )
        mensaje.attach(f'cotizacion_{cotizacion.numero_venta}.pdf', pdf_bytes, 'application/pdf')
        mensaje.send(fail_silently=False)
    except Exception as exc:
        messages.error(request, f'No se pudo enviar el correo ({exc}).')
        return destino

    if (cotizacion.estado_cotizacion or 'pendiente') in ('pendiente', ''):
        cotizacion.estado_cotizacion = 'enviada'
        cotizacion.save(update_fields=['estado_cotizacion'])

    messages.success(request, f'Cotización #{cotizacion.numero_venta} enviada a {email}.')
    return destino


def cotizacion_html_debug(request, pk):
    """Vista HTML de cotización - VERSIÓN DEBUG SIN DECORADORES"""
    print(f"DEBUG - Buscando cotización ID: {pk}")
    print(f"DEBUG - Usuario: {request.user}")
    print(f"DEBUG - Usuario autenticado: {request.user.is_authenticated}")
    print(f"DEBUG - Es superusuario: {request.user.is_superuser}")
    
    # Verificar si tiene empresa
    if hasattr(request, 'empresa'):
        print(f"DEBUG - Empresa: {request.empresa}")
    else:
        print("DEBUG - No tiene empresa asignada")
    
    try:
        # Buscar sin filtros primero
        cotizacion = Venta.objects.get(pk=pk)
        print(f"DEBUG - Cotización encontrada: {cotizacion.numero_venta}")
        print(f"DEBUG - Empresa de la cotización: {cotizacion.empresa.nombre}")
        print(f"DEBUG - Tipo de documento: {cotizacion.tipo_documento}")
        
        # Verificar si es cotización
        if cotizacion.tipo_documento != 'cotizacion':
            print(f"DEBUG - ERROR: No es una cotización, es: {cotizacion.tipo_documento}")
            raise Http404("No es una cotización")
        
        # Verificar empresa si no es superusuario
        if not request.user.is_superuser and hasattr(request, 'empresa') and request.empresa:
            if cotizacion.empresa != request.empresa:
                print(f"DEBUG - ERROR: Empresa no coincide. Usuario: {request.empresa.nombre}, Cotización: {cotizacion.empresa.nombre}")
                raise Http404("Empresa no coincide")
        
    except Venta.DoesNotExist:
        print("DEBUG - Cotización no existe en absoluto")
        raise Http404("Cotización no encontrada")
    
    detalles = VentaDetalle.objects.filter(venta=cotizacion).select_related('articulo')
    
    context = {
        'cotizacion': cotizacion,
        'detalles': detalles,
    }
    
    return render(request, 'ventas/cotizacion_html.html', context)

@login_required
def cotizacion_html(request, pk):
    """Vista HTML de cotización"""
    print(f"DEBUG - Buscando cotización ID: {pk}")
    print(f"DEBUG - Usuario: {request.user}")
    print(f"DEBUG - Es superusuario: {request.user.is_superuser}")
    
    try:
        # Buscar la cotización
        cotizacion = Venta.objects.get(pk=pk, tipo_documento='cotizacion')
        print(f"DEBUG - Cotización encontrada: {cotizacion.numero_venta}")
        print(f"DEBUG - Empresa de la cotización: {cotizacion.empresa.nombre}")
        
        # Verificar permisos de empresa
        if not request.user.is_superuser:
            if hasattr(request, 'empresa') and request.empresa:
                if cotizacion.empresa != request.empresa:
                    print(f"DEBUG - ERROR: Empresa no coincide. Usuario: {request.empresa.nombre}, Cotización: {cotizacion.empresa.nombre}")
                    raise Http404("No tiene permisos para acceder a esta cotización")
            else:
                print("DEBUG - ERROR: Usuario no tiene empresa asignada")
                raise Http404("No tiene permisos para acceder a esta cotización")
        
    except Venta.DoesNotExist:
        print("DEBUG - Cotización no existe")
        raise Http404("Cotización no encontrada")
    
    detalles = VentaDetalle.objects.filter(venta=cotizacion).select_related('articulo')
    
    # Obtener configuración de impresora
    empresa = cotizacion.empresa
    tipo_impresora = getattr(empresa, 'impresora_cotizacion', 'laser')
    nombre_impresora = getattr(empresa, 'impresora_cotizacion_nombre', None)
    
    # Seleccionar template según configuración
    if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
        template = 'ventas/cotizacion_termica.html'
        print(f"[PRINT] Cotizacion -> Formato TERMICO 80mm")
    else:
        template = 'ventas/cotizacion_html.html'
        print(f"[PRINT] Cotizacion -> Formato LASER A4")
    
    if nombre_impresora:
        print(f"[PRINT] Impresora fisica configurada: {nombre_impresora}")
    
    context = {
        'cotizacion': cotizacion,
        'detalles': detalles,
        'empresa': empresa,
        'nombre_impresora': nombre_impresora,
    }
    
    return render(request, template, context)


def _resolver_dte_de_venta(venta):
    """DTE oficial de la venta (relación directa, caja o búsqueda por folio)."""
    from django.core.exceptions import ObjectDoesNotExist
    from facturacion_electronica.models import DocumentoTributarioElectronico
    from caja.models import VentaProcesada

    try:
        dte = venta.dte
        if dte:
            return dte
    except (ObjectDoesNotExist, AttributeError):
        pass

    vp = (
        VentaProcesada.objects.filter(Q(venta_final=venta) | Q(venta_preventa=venta))
        .exclude(dte_generado_id__isnull=True)
        .select_related('dte_generado')
        .order_by('-id')
        .first()
    )
    if vp and vp.dte_generado_id:
        return vp.dte_generado

    return DocumentoTributarioElectronico.objects.filter(venta=venta).order_by('-id').first()


class SafeAttrProxy:
    """Objeto seguro para evitar VariableDoesNotExist en cadenas de atributos en templates."""
    def __getattr__(self, name):
        return SafeAttrProxy()
    def __str__(self):
        return ""
    def __bool__(self):
        return False


class DTEProxy:
    """Proxy de compatibilidad cuando una venta no tiene objeto DTE asociado en BD."""
    def __init__(self, venta):
        self._venta = venta
        self.id = None
        self.pk = None
        self.venta = venta
        self.empresa = getattr(venta, 'empresa', None)
        self.empresa_id = getattr(venta, 'empresa_id', None)
        self.fecha_emision = getattr(venta, 'fecha', None)
        self.folio = getattr(venta, 'numero_venta', None)
        tipo = getattr(venta, 'tipo_documento', '')
        if tipo in ('factura', 'factura_electronica'):
            self.tipo_dte = '33'
        elif tipo in ('boleta', 'boleta_electronica'):
            self.tipo_dte = '39'
        elif tipo == 'guia':
            self.tipo_dte = '52'
        else:
            self.tipo_dte = '39'
        self.monto_neto = getattr(venta, 'neto', 0)
        self.monto_iva = getattr(venta, 'iva', 0)
        self.monto_total = getattr(venta, 'total', 0)
        self.monto_exento = getattr(venta, 'exento', 0)
        self.datos_pdf417 = None
        self.timbre_pdf417 = None
        self.ambiente = 0
        self.estado_sii = 'NO_ENVIADO'
        self.track_id = None
        cliente = getattr(venta, 'cliente', None)
        self.rut_receptor = getattr(cliente, 'rut', '') if cliente else '66666666-6'
        self.razon_social_receptor = getattr(cliente, 'nombre', '') if cliente else 'Cliente Genérico'
        self.giro_receptor = getattr(cliente, 'giro', '') if cliente else ''
        self.direccion_receptor = getattr(cliente, 'direccion', '') if cliente else ''
        self.comuna_receptor = getattr(cliente, 'comuna', '') if cliente else ''
        self.ciudad_receptor = getattr(cliente, 'ciudad', '') if cliente else ''
        self.contacto_receptor = getattr(cliente, 'telefono', '') if cliente else ''
        self.observaciones = getattr(venta, 'observaciones', '')

    def __getattr__(self, name):
        return SafeAttrProxy()


@login_required
def venta_html(request, pk):
    """Vista HTML de venta (detecta automáticamente el tipo de documento)"""
    try:
        venta = Venta.objects.get(pk=pk)
        
        # Verificar permisos de empresa
        if not request.user.is_superuser:
            if hasattr(request, 'empresa') and request.empresa:
                if venta.empresa != request.empresa:
                    raise Http404("No tiene permisos para acceder a esta venta")
            else:
                raise Http404("No tiene permisos para acceder a esta venta")
    except Venta.DoesNotExist:
        raise Http404("Venta no encontrada")
    
    # Cargar relaciones necesarias para evitar consultas adicionales
    venta = Venta.objects.select_related(
        'cliente', 'vendedor', 'empresa', 'estacion_trabajo', 'forma_pago', 'sucursal'
    ).get(pk=venta.pk)
    
    detalles = VentaDetalle.objects.filter(venta=venta).select_related('articulo')
    
    dte = _resolver_dte_de_venta(venta)
    if dte:
        q = request.GET.urlencode()
        destino = reverse('facturacion_electronica:ver_factura_electronica', args=[dte.pk])
        return redirect(f'{destino}?{q}' if q else destino)

    forzar_a4 = (request.GET.get('formato') or '').strip().lower() in ('a4', 'carta', 'laser')
    
    # Determinar el template según el tipo de documento Y tipo de impresora configurado
    empresa = venta.empresa
    
    # Obtener nombre de impresora física configurada (para pasarlo al template)
    nombre_impresora = None
    
    if venta.tipo_documento in ['factura', 'factura_electronica']:
        # Verificar si usa impresora térmica o láser
        tipo_impresora = getattr(empresa, 'impresora_factura', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_factura_nombre', None)
        
        if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
            template_name = 'ventas/factura_electronica_termica.html'
            print(f"[PRINT] Factura -> Formato TERMICO 80mm")
        else:
            template_name = 'ventas/factura_electronica_html.html'
            print(f"[PRINT] Factura -> Formato LASER A4")
    
    elif venta.tipo_documento in ['boleta', 'boleta_electronica']:
        # Verificar si usa impresora térmica o láser
        tipo_impresora = getattr(empresa, 'impresora_boleta', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_boleta_nombre', None)
        
        if dte:  # Si tiene DTE, usar templates electrónicos
            if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
                template_name = 'ventas/boleta_electronica_termica.html'
                print(f"[PRINT] Boleta Electronica -> Formato TERMICO 80mm")
            else:
                template_name = 'ventas/boleta_electronica_html.html'
                print(f"[PRINT] Boleta Electronica -> Formato LASER A4")
        else:
            # Boleta sin DTE (boleta manual)
            template_name = 'ventas/boleta_html.html'
            print(f"[PRINT] Boleta Manual -> Formato estandar")
    
    elif venta.tipo_documento == 'guia':
        # Guías de despacho electrónicas
        tipo_impresora = getattr(empresa, 'impresora_guia', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_guia_nombre', None)
        
        if dte:  # Guía electrónica con DTE
            if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
                template_name = 'inventario/guia_despacho_electronica_termica.html'
                print(f"[PRINT] Guia Electronica -> Formato TERMICO 80mm")
            else:
                template_name = 'inventario/guia_despacho_electronica_html.html'
                print(f"[PRINT] Guia Electronica -> Formato LASER A4")
        else:
            # Guía manual sin DTE
            template_name = 'inventario/guia_despacho_html.html'
            print(f"[PRINT] Guia Manual -> Formato estandar")
    
    else:
        # Otros documentos (vale, cotización, NC, ND).
        # Un ticket facturable NO se imprime como boleta/factura: solo indica el destino.
        tipo_final = venta.tipo_documento

        if tipo_final == 'ticket':
            tipo_impresora = getattr(empresa, 'impresora_vale', 'termica_80')
            nombre_impresora = getattr(empresa, 'impresora_vale_nombre', None)
            if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
                template_name = 'ventas/vale_termica.html'
                print(f"[PRINT] Ticket facturable -> Formato TERMICO 80mm")
            else:
                template_name = 'ventas/vale_html.html'
                print(f"[PRINT] Ticket facturable -> Formato LASER A4")
        elif tipo_final == 'vale':
            tipo_impresora = getattr(empresa, 'impresora_vale', 'laser')
            nombre_impresora = getattr(empresa, 'impresora_vale_nombre', None)
            
            if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
                template_name = 'ventas/vale_termica.html'
                print(f"[PRINT] Vale/Ticket -> Formato TERMICO 80mm")
            else:
                template_name = 'ventas/vale_html.html'
                print(f"[PRINT] Vale/Ticket -> Formato LASER A4")
                
        elif tipo_final == 'cotizacion':
            tipo_impresora = getattr(empresa, 'impresora_cotizacion', 'laser')
            nombre_impresora = getattr(empresa, 'impresora_cotizacion_nombre', None)
            
            if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
                template_name = 'ventas/cotizacion_termica.html'
                print(f"[PRINT] Cotizacion -> Formato TERMICO 80mm")
            else:
                template_name = 'ventas/cotizacion_html.html'
                print(f"[PRINT] Cotizacion -> Formato LASER A4")
        else:
            # Default para otros tipos
            template_name = 'ventas/boleta_html.html'

    if forzar_a4:
        if 'termica' in template_name or template_name.endswith('vale_termica.html'):
            if venta.tipo_documento in ['factura', 'factura_electronica'] or (dte and str(getattr(dte, 'tipo_dte', '')) in ['33', '34']):
                template_name = 'ventas/factura_electronica_html.html'
            elif venta.tipo_documento == 'guia' or (dte and str(getattr(dte, 'tipo_dte', '')) == '52'):
                template_name = 'inventario/guia_despacho_electronica_html.html'
            elif venta.tipo_documento in ['boleta', 'boleta_electronica'] or (dte and str(getattr(dte, 'tipo_dte', '')) in ['39', '41']):
                template_name = 'ventas/boleta_electronica_html.html'
            elif venta.tipo_documento in ('ticket', 'vale'):
                template_name = 'ventas/vale_html.html'
            else:
                template_name = 'ventas/boleta_html.html'
    
    # Log de impresora física
    if nombre_impresora:
        print(f"[PRINT] Impresora fisica configurada: {nombre_impresora}")
    
    # Obtener formas de pago múltiples (desde MovimientoCaja)
    formas_pago_list = []
    try:
        from caja.impresion_utils import obtener_formas_pago_ticket

        formas_pago_list = [
            {
                'forma_pago': pago['nombre'],
                'monto': pago['monto'],
            }
            for pago in obtener_formas_pago_ticket(venta)
        ]
    except Exception as e:
        print(f"[WARN] Error al obtener formas de pago: {str(e)}")
    
    # Obtener configuración de copias de la estación (prioritario)
    n_copias = 1
    estacion = getattr(venta, 'estacion_trabajo', None)
    if not estacion:
        estacion_id = request.session.get('pos_estacion_id')
        if estacion_id:
            from ventas.aislamiento import estacion_de_empresa
            estacion = estacion_de_empresa(request.empresa, estacion_id)
    
    if estacion and getattr(estacion, 'empresa_id', None) == getattr(request.empresa, 'id', None):
        # Los vales del POS se guardan como ticket con tipo_documento_planeado='vale'.
        # Para copias, un vale debe respetar copias_vale de la estación.
        tipo_para_copias = venta.tipo_documento
        if tipo_para_copias == 'ticket' and venta.tipo_documento_planeado == 'vale':
            tipo_para_copias = 'vale'
        n_copias = estacion.get_copias_por_tipo(tipo_para_copias)

    dte_context = dte if dte else DTEProxy(venta)

    context = {
        'venta': venta,
        'detalles': detalles,
        'empresa': empresa,
        'dte': dte_context,  # Objeto DTE o DTEProxy seguro para templates
        'dte_real': dte,     # DTE de BD (None si no existe)
        'nombre_impresora': nombre_impresora,  # Nombre de impresora física
        'formas_pago_list': formas_pago_list,  # Lista de formas de pago múltiples
        'copias_range': range(n_copias),
        'vehiculo': getattr(venta, 'vehiculo', None),
        'chofer': getattr(venta, 'chofer', None),
        # Alias para compatibilidad con templates específicos
        'boleta': venta if venta.tipo_documento == 'boleta' or (venta.tipo_documento == 'ticket' and venta.tipo_documento_planeado == 'boleta') else None,
        'factura': venta if venta.tipo_documento == 'factura' or (venta.tipo_documento == 'ticket' and venta.tipo_documento_planeado == 'factura') else None,
        'vale': venta if venta.tipo_documento in ('vale', 'ticket') or (venta.tipo_documento == 'ticket' and venta.tipo_documento_planeado == 'vale') else None,
        'cotizacion': venta if venta.tipo_documento == 'cotizacion' or (venta.tipo_documento == 'ticket' and venta.tipo_documento_planeado == 'cotizacion') else None,
        'es_ticket': venta.tipo_documento == 'ticket',
    }

    from facturacion_electronica.views_dte import _build_receptor_display, resolver_bodega_documento, resolver_referencias_documento
    context['receptor_display'] = _build_receptor_display(dte, fallback_cliente=getattr(venta, 'cliente', None))
    context['bodega_display'] = resolver_bodega_documento(venta=venta, dte=dte)
    context['referencias_list'] = resolver_referencias_documento(venta=venta, dte=dte)
    est_doc = getattr(venta, 'estacion_trabajo', None)
    if est_doc:
        context['estacion_display'] = str(est_doc.nombre or '').strip()
    else:
        context['estacion_display'] = ''
    
    # Para guías, pasar el DTE como 'guia' para compatibilidad con template de transferencias
    if venta.tipo_documento == 'guia' and dte:
        context['guia'] = dte
    elif venta.tipo_documento == 'guia':
        # Si no hay DTE, crear objeto temporal con datos de la venta
        class GuiaTemp:
            def __init__(self, venta):
                self.folio = venta.numero_venta
                self.monto_neto = venta.neto
                self.monto_iva = venta.iva
                self.monto_total = venta.total
                # Datos receptor
                if venta.cliente:
                    self.rut_receptor = venta.cliente.rut
                    self.razon_social_receptor = venta.cliente.nombre
                    self.giro_receptor = getattr(venta.cliente, 'giro', '')
                    self.direccion_receptor = venta.cliente.direccion or ''
                    self.comuna_receptor = venta.cliente.comuna or ''
                    self.ciudad_receptor = venta.cliente.ciudad or ''
                else:
                    self.rut_receptor = '66666666-6'
                    self.razon_social_receptor = 'Cliente Genérico'
                    self.giro_receptor = ''
                    self.direccion_receptor = ''
                    self.comuna_receptor = ''
                    self.ciudad_receptor = ''
                # Generar placeholder PDF417 en base64 para mostrar timbre
                try:
                    from facturacion_electronica.pdf417_generator import PDF417Generator
                    placeholder_bytes = PDF417Generator._generar_placeholder(280, 100)
                    import base64
                    self.datos_pdf417 = base64.b64encode(placeholder_bytes).decode('ascii')
                    self.timbre_pdf417 = None  # Usamos datos base64
                except Exception:
                    self.timbre_pdf417 = None
                    self.datos_pdf417 = None
                # Tipo traslado display helper
                self.get_tipo_traslado_display = lambda: 'Venta'
        context['guia'] = GuiaTemp(venta)
        # Pasar detalles para template compacto
        context['detalles'] = list(venta.ventadetalle_set.all())

    return render(request, template_name, context)


@login_required
def venta_imprimir_y_volver(request, pk):
    """Wrapper de impresión: abre el documento asociado a la venta, dispara impresión y retorna al POS"""
    try:
        venta = Venta.objects.get(pk=pk)
        # Verificar permisos de empresa, salvo superusuario
        if not request.user.is_superuser:
            if hasattr(request, 'empresa') and request.empresa:
                if venta.empresa != request.empresa:
                    raise Http404("No tiene permisos para acceder a esta venta")
            else:
                raise Http404("No tiene permisos para acceder a esta venta")
    except Venta.DoesNotExist:
        raise Http404("Venta no encontrada")

    dte = _resolver_dte_de_venta(venta)

    if dte:
        try:
            doc_url = reverse('facturacion_electronica:ver_factura_electronica', args=[dte.id])
        except Exception:
            doc_url = reverse('ventas:venta_html', args=[venta.id])
    else:
        doc_url = reverse('ventas:venta_html', args=[venta.id])

    # Agregar indicador de auto-impresión para facilitar retorno al POS si se abre en la misma pestaña
    if '?' in doc_url:
        doc_url = f"{doc_url}&auto=1"
    else:
        doc_url = f"{doc_url}?auto=1"

    return render(request, 'ventas/venta_imprimir_y_volver.html', {
        'venta': venta,
        'doc_url': doc_url,
    })

@login_required
@requiere_empresa
@permission_required('ventas.change_cotizacion', raise_exception=True)
def cotizacion_cambiar_estado(request, pk):
    """Cambiar estado de una cotización"""
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['pendiente', 'enviada', 'aceptada', 'rechazada', 'vencida']:
            cotizacion.estado_cotizacion = nuevo_estado
            cotizacion.save()
            
            messages.success(request, f'Estado de cotización actualizado a: {cotizacion.get_estado_cotizacion_display()}')
            return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)
    
    return redirect(reverse('ventas:cotizacion_detail', args=[pk]) + '?modal=estado')


@login_required
@requiere_empresa
@permission_required('ventas.add_venta', raise_exception=True)
def cotizacion_convertir_venta(request, pk):
    """Convertir cotización en venta electrónica oficial (Factura, Boleta o Guía) con DTE, timbre y envío al SII"""
    from pedidos.models_transporte import Vehiculo, Chofer
    from facturacion_electronica.dte_service import DTEService
    
    cotizacion = get_object_or_404(Venta, pk=pk, empresa=request.empresa, tipo_documento='cotizacion')
    
    if request.method == 'POST':
        tipo_venta = request.POST.get('tipo_venta')
        
        if tipo_venta in ['factura', 'boleta', 'guia']:
            # Mapear tipo de documento a código DTE
            if tipo_venta == 'guia':
                tipo_dte = '52'
            elif tipo_venta == 'factura':
                todos_exentos = all(bool(getattr(d.articulo.categoria, 'exenta_iva', False)) for d in cotizacion.ventadetalle_set.all()) if cotizacion.ventadetalle_set.exists() else False
                tipo_dte = '34' if todos_exentos else '33'
            elif tipo_venta == 'boleta':
                todos_exentos = all(bool(getattr(d.articulo.categoria, 'exenta_iva', False)) for d in cotizacion.ventadetalle_set.all()) if cotizacion.ventadetalle_set.exists() else False
                tipo_dte = '41' if todos_exentos else '39'
            else:
                tipo_dte = '39'

            vehiculo = None
            chofer = None
            tipo_despacho = None
            tipo_despacho_sii = '2'
            patente_carro = ''
            rut_transportista = ''
            fecha_salida = None
            hora_salida = ''
            fecha_llegada = None
            obs_extra = []
            
            if tipo_venta == 'guia':
                vehiculo_id = request.POST.get('vehiculo_id')
                chofer_id = request.POST.get('chofer_id')
                tipo_despacho = request.POST.get('tipo_despacho') or '1'
                tipo_despacho_sii = request.POST.get('tipo_despacho_sii') or '2'
                patente_carro = (request.POST.get('patente_carro') or '').strip().upper()[:8]
                rut_transportista = (request.POST.get('rut_transportista') or '').strip()
                fecha_salida = request.POST.get('fecha_salida')
                hora_salida = (request.POST.get('hora_salida') or '').strip()
                fecha_llegada = request.POST.get('fecha_llegada')
                
                if vehiculo_id:
                    vehiculo = Vehiculo.objects.filter(pk=vehiculo_id, empresa=request.empresa, activo=True).first()
                if chofer_id:
                    chofer = Chofer.objects.filter(pk=chofer_id, empresa=request.empresa, activo=True).first()
                
                # Fallback inteligente si solo se seleccionó uno
                if not chofer and vehiculo and vehiculo.chofer:
                    chofer = vehiculo.chofer
                if not vehiculo and chofer:
                    vehiculo = Vehiculo.objects.filter(empresa=request.empresa, chofer=chofer, activo=True).first()
                
                despacho_detalles = []
                if tipo_despacho:
                    despacho_detalles.append(f"Tipo Traslado: {dict(Venta.TIPO_DESPACHO_CHOICES).get(tipo_despacho, tipo_despacho)}")
                if tipo_despacho_sii:
                    despacho_detalles.append(f"Tipo Despacho SII: {tipo_despacho_sii}")
                if vehiculo:
                    despacho_detalles.append(f"Vehículo: {vehiculo.patente}")
                if chofer:
                    despacho_detalles.append(f"Chofer: {chofer.nombre} ({chofer.rut})")
                if rut_transportista:
                    despacho_detalles.append(f"RUT Transp: {rut_transportista}")
                if patente_carro:
                    despacho_detalles.append(f"Carro: {patente_carro}")
                if fecha_salida:
                    despacho_detalles.append(f"Salida: {fecha_salida} {hora_salida}".strip())
                if fecha_llegada:
                    despacho_detalles.append(f"Llegada: {fecha_llegada}")
                
                if despacho_detalles:
                    obs_extra.append("[DATOS GUÍA] " + " | ".join(despacho_detalles))
            
            obs_final = f"Convertida desde cotización #{cotizacion.numero_venta}"
            if cotizacion.observaciones:
                obs_final = f"{obs_final}\n{cotizacion.observaciones}"
            if obs_extra:
                obs_final = f"{obs_final}\n" + "\n".join(obs_extra)
            
            # Validaciones de cliente para Factura y Guía
            cliente = cotizacion.cliente
            if tipo_dte in ['33', '34', '52']:
                if not cliente or not cliente.rut:
                    messages.error(request, 'El cliente debe tener un RUT válido para emitir Factura o Guía Electrónica.')
                    return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)
            
            # Buscar estación de trabajo para asignar a la venta
            estacion = cotizacion.estacion_trabajo
            if not estacion:
                estacion_id = request.session.get('pos_estacion_id')
                if estacion_id:
                    estacion = EstacionTrabajo.objects.filter(id=estacion_id, empresa=request.empresa, activo=True).first()
            if not estacion:
                estacion = EstacionTrabajo.objects.filter(empresa=request.empresa, activo=True).order_by('numero').first()

            forma_pago = cotizacion.forma_pago
            if not forma_pago and cliente and cliente.forma_pago_defecto:
                forma_pago = cliente.forma_pago_defecto
            if not forma_pago:
                forma_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).first()

            try:
                with transaction.atomic():
                    temp_numero = f"CV{timezone.now().strftime('%y%m%d%H%M%S%f')[:18]}"
                    nueva_venta = Venta.objects.create(
                        empresa=cotizacion.empresa,
                        sucursal=cotizacion.sucursal,
                        numero_venta=temp_numero,
                        fecha=timezone.localdate(),
                        cliente=cotizacion.cliente,
                        vendedor=cotizacion.vendedor,
                        forma_pago=forma_pago,
                        estacion_trabajo=estacion,
                        tipo_documento=tipo_venta,
                        tipo_documento_planeado=tipo_venta,
                        direccion_despacho=cotizacion.direccion_despacho,
                        comuna_despacho=cotizacion.comuna_despacho,
                        ciudad_despacho=cotizacion.ciudad_despacho,
                        direccion_cliente=cotizacion.direccion_cliente,
                        vehiculo=vehiculo,
                        chofer=chofer,
                        tipo_despacho=tipo_despacho,
                        subtotal=cotizacion.subtotal,
                        descuento=cotizacion.descuento,
                        neto=cotizacion.neto,
                        iva=cotizacion.iva,
                        impuesto_especifico=cotizacion.impuesto_especifico,
                        total=cotizacion.total,
                        estado='confirmada',
                        observaciones=obs_final,
                        usuario_creacion=request.user
                    )
                    
                    # Copiar detalles
                    for detalle in cotizacion.ventadetalle_set.all():
                        VentaDetalle.objects.create(
                            venta=nueva_venta,
                            articulo=detalle.articulo,
                            cantidad=detalle.cantidad,
                            precio_unitario=detalle.precio_unitario,
                            precio_total=detalle.precio_total,
                            impuesto_especifico=detalle.impuesto_especifico
                        )
                    
                    nueva_venta.calcular_totales()
                    nueva_venta.save()

                    # Generar DTE oficial con timbre electrónico
                    dte_service = DTEService(request.empresa)
                    patente_transporte = (vehiculo.patente if vehiculo else '') or (request.POST.get('patente_transporte') or '').strip()
                    nombre_chofer = (chofer.nombre if chofer else '') or (request.POST.get('nombre_chofer') or '').strip()
                    
                    dte = dte_service.generar_dte_desde_venta(
                        nueva_venta,
                        tipo_dte,
                        patente_transporte=patente_transporte,
                        rut_transportista=rut_transportista,
                        nombre_chofer=nombre_chofer,
                        tipo_despacho_sii=tipo_despacho_sii,
                        patente_carro=patente_carro,
                        fecha_salida=fecha_salida,
                        hora_salida=hora_salida,
                        fecha_llegada=fecha_llegada,
                    )
                    
                    if not dte:
                        raise ValueError("El servicio DTE no pudo generar el documento tributario.")
                    
                    numero_final = f"{dte.folio:06d}"
                    if not Venta.objects.filter(empresa=request.empresa, tipo_documento=nueva_venta.tipo_documento, numero_venta=numero_final).exclude(pk=nueva_venta.pk).exists():
                        nueva_venta.numero_venta = numero_final
                        nueva_venta.save(update_fields=['numero_venta'])
                    
                    # Actualizar estado de la cotización
                    cotizacion.estado_cotizacion = 'convertida'
                    cotizacion.save(update_fields=['estado_cotizacion'])

                # Envío al SII
                envio = {'success': False, 'message': 'No enviado'}
                try:
                    envio = dte_service.enviar_dte_al_sii(dte)
                except Exception as exc:
                    envio = {'success': False, 'message': str(exc)}
                
                if envio.get('success'):
                    messages.success(request, f'{dte.get_tipo_dte_display()} #{dte.folio} emitida con timbre y enviada al SII exitosamente.')
                else:
                    messages.warning(request, f'{dte.get_tipo_dte_display()} #{dte.folio} emitida con timbre electrónico. Aviso SII: {envio.get("message") or "Pendiente de envío"}')
                
                return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)

            except Exception as e:
                import traceback
                print(f"[ERROR CONVERSION COTIZACION] {str(e)}")
                traceback.print_exc()
                messages.error(request, f'No se pudo generar el documento electrónico: {str(e)}')
                return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)
    
    # GET: fallback standalone view
    vehiculos = Vehiculo.objects.filter(empresa=request.empresa, activo=True).order_by('patente')
    choferes = Chofer.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    context = {
        'cotizacion': cotizacion,
        'detalles': cotizacion.ventadetalle_set.all(),
        'tipos_venta': [
            ('factura', 'Factura'),
            ('boleta', 'Boleta'),
            ('guia', 'Guía de Despacho'),
        ],
        'tipo_despacho_choices': Venta.TIPO_DESPACHO_CHOICES,
        'tipo_despacho_sii_choices': TIPO_DESPACHO_SII_CHOICES,
        'vehiculos': vehiculos,
        'choferes': choferes,
        'rut_empresa': request.empresa.rut or '',
        'hora_actual': timezone.localtime().strftime('%H:%M'),
        'today': timezone.localdate(),
    }
    return render(request, 'ventas/cotizacion_convertir_venta.html', context)


# ========================================
# GESTIÓN DE TICKETS/VALES
# ========================================

@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def ticket_list(request):
    """Lista de todos los tickets/vales facturables"""
    from datetime import datetime, timedelta
    
    print("=" * 80)
    print("[TICKET_LIST] INICIANDO VISTA ticket_list")
    print(f"[TICKET_LIST] URL: {request.path}")
    print(f"[TICKET_LIST] GET params: {request.GET}")
    print(f"[TICKET_LIST] Empresa: {request.empresa.nombre} (ID: {request.empresa.id})")
    
    # Obtener parámetros de filtro
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    estacion_id = request.GET.get('estacion')
    
    # Por defecto, mostrar tickets de los últimos 180 días (6 meses) para incluir más tickets
    if not fecha_desde:
        fecha_desde = timezone.localdate() - timedelta(days=180)
        print(f"[TICKET_LIST] fecha_desde NO proporcionada, usando por defecto: {fecha_desde}")
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        print(f"[TICKET_LIST] fecha_desde proporcionada: {fecha_desde}")
    
    if not fecha_hasta:
        fecha_hasta = timezone.localdate()
        print(f"[TICKET_LIST] fecha_hasta NO proporcionada, usando por defecto: {fecha_hasta}")
    else:
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
        print(f"[TICKET_LIST] fecha_hasta proporcionada: {fecha_hasta}")
    
    # Ajustar fecha_hasta para incluir todo el día
    fecha_hasta_datetime = timezone.make_aware(datetime.combine(fecha_hasta, datetime.max.time()))
    fecha_desde_datetime = timezone.make_aware(datetime.combine(fecha_desde, datetime.min.time()))
    print(f"[TICKET_LIST] Rango datetime: {fecha_desde_datetime} a {fecha_hasta_datetime}")
    
    # CORRECCIÓN: Primero corregir TODOS los tickets invertidos sin restricción de fecha
    tickets_invertidos = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento__in=['boleta', 'factura', 'guia'],
        tipo_documento_planeado__in=['vale', 'ticket'], # Incluir ambos para corrección
        facturado=False,
        estado__in=['borrador', 'confirmada']
    )
    
    if tickets_invertidos.exists():
        for ticket in tickets_invertidos:
            tipo_original = ticket.tipo_documento
            ticket.tipo_documento = 'ticket'
            ticket.tipo_documento_planeado = tipo_original
            ticket.save()

    # CORRECCIÓN EXTRA: Si hay tickets guardados como 'vale' (vieja lógica), 
    # pasarlos a 'ticket' con planeado 'vale' para que aparezcan en la lista
    vales_antiguos = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        facturado=False
    )
    if vales_antiguos.exists():
        vales_antiguos.update(tipo_documento='ticket', tipo_documento_planeado='vale')
    
    # CONSULTA FINAL SIMPLIFICADA: Solo condiciones esenciales
    # Un ticket es facturable si:
    # 1. Es un ticket (tipo_documento='ticket')
    # 2. No está facturado (facturado=False)
    # 3. No está anulado (estado != 'anulada')
    # 4. Tiene tipo_documento_planeado válido (no 'vale' ni 'ticket')
    
    # Primero corregir tickets sin tipo_documento_planeado válido (sin restricción de fecha)
    tickets_a_corregir = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='ticket',
        facturado=False,
        estado__in=['borrador', 'confirmada']
    ).filter(
        Q(tipo_documento_planeado__isnull=True) | 
        Q(tipo_documento_planeado='') |
        Q(tipo_documento_planeado='ticket')
    )
    if tickets_a_corregir.exists():
        tickets_a_corregir.update(tipo_documento_planeado='boleta')
    
    # CONSULTA SIMPLIFICADA AL MÁXIMO: Solo condiciones esenciales
    print(f"[TICKET_LIST] Construyendo consulta...")
    tickets = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='ticket',
        facturado=False,
        fecha_creacion__gte=fecha_desde_datetime,
        fecha_creacion__lte=fecha_hasta_datetime
    ).exclude(
        tipo_documento_planeado='ticket'
    ).exclude(
        tipo_documento_planeado__isnull=True
    ).exclude(
        tipo_documento_planeado=''
    )
    
    print(f"[TICKET_LIST] Consulta inicial (sin select_related): {tickets.count()} tickets")
    
    from empresas.middleware import resolver_sucursal_operativa
    sucursal_tickets = resolver_sucursal_operativa(request)
    if sucursal_tickets:
        tickets = tickets.filter(Q(sucursal=sucursal_tickets) | Q(sucursal__isnull=True))
        print(f"[TICKET_LIST] Después de filtrar por sucursal {sucursal_tickets.id}: {tickets.count()} tickets")
    
    # Filtrar por estación si se especifica
    if estacion_id:
        from ventas.aislamiento import estacion_de_empresa
        if estacion_de_empresa(request.empresa, estacion_id) is None:
            estacion_id = None
        else:
            tickets = tickets.filter(estacion_trabajo_id=estacion_id)
            print(f"[TICKET_LIST] Después de filtrar por estación {estacion_id}: {tickets.count()} tickets")
    
    # Obtener estaciones para el filtro
    estaciones = _estaciones_operativas(request, sucursal_tickets)
    
    # Ordenar y seleccionar relaciones
    tickets = tickets.select_related('cliente', 'vendedor', 'estacion_trabajo').order_by('-fecha_creacion')
    
    print(f"[TICKET_LIST] Consulta final antes de evaluar: {tickets.count()} tickets")
    
    # CRÍTICO: Evaluar el queryset ANTES de calcular totales
    print(f"[TICKET_LIST] Evaluando queryset a lista...")
    tickets_list = list(tickets)
    print(f"[TICKET_LIST] Lista evaluada: {len(tickets_list)} tickets")
    
    # Calcular totales
    total_tickets = len(tickets_list)
    total_monto = sum(float(ticket.total) for ticket in tickets_list)
    
    context = {
        'tickets': tickets_list,
        'estaciones': estaciones,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'fecha_desde_display': fecha_desde_obj.strftime('%d-%m-%Y') if 'fecha_desde_obj' in locals() else fecha_desde,
        'fecha_hasta_display': fecha_hasta_obj.strftime('%d-%m-%Y') if 'fecha_hasta_obj' in locals() else fecha_hasta,
        'estacion_id': estacion_id,
        'total_tickets': total_tickets,
        'total_monto': total_monto,
    }
    
    return render(request, 'ventas/ticket_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def vale_list(request):
    """Lista de vales internos (no tributarios)"""
    from datetime import datetime, timedelta
    
    # Obtener parámetros de filtro
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde:
        fecha_desde = timezone.localdate() - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    
    if not fecha_hasta:
        fecha_hasta = timezone.localdate()
    else:
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    fecha_hasta_datetime = timezone.make_aware(datetime.combine(fecha_hasta, datetime.max.time()))
    fecha_desde_datetime = timezone.make_aware(datetime.combine(fecha_desde, datetime.min.time()))
    
    # Documentos de tipo Vale Interno - Mostrar los PROCESADOS
    # Caso 1: tipo_documento='vale' (guardados directamente como vale)
    # Caso 2: tipo_documento='ticket' con tipo_documento_planeado='vale' y facturado=True
    #         (tickets procesados en caja que eran vales internos)
    vales = Venta.objects.filter(
        empresa=request.empresa,
        fecha_creacion__gte=fecha_desde_datetime,
        fecha_creacion__lte=fecha_hasta_datetime
    ).filter(
        Q(tipo_documento='vale') |
        Q(tipo_documento='ticket', tipo_documento_planeado='vale', facturado=True)
    ).select_related('cliente', 'vendedor').order_by('-fecha_creacion')
    
    # Calcular totales
    total_vales = vales.count()
    total_monto = sum(float(v.total) for v in vales)
    
    context = {
        'vales': vales,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'total_vales': total_vales,
        'total_monto': total_monto,
    }
    
    return render(request, 'ventas/vale_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def ticket_detail(request, pk):
    """Detalle de un ticket o vale"""
    ticket = get_object_or_404(
        Venta, 
        Q(tipo_documento='ticket') | Q(tipo_documento='vale'),
        pk=pk, 
        empresa=request.empresa
    )
    
    detalles = VentaDetalle.objects.filter(venta=ticket).select_related('articulo')
    
    context = {
        'ticket': ticket,
        'detalles': detalles,
    }
    
    return render(request, 'ventas/ticket_detail.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def ticket_reimprimir(request, pk):
    """Reimprimir un ticket o vale (redirige al HTML del vale/ticket)"""
    ticket = get_object_or_404(
        Venta, 
        Q(tipo_documento='ticket') | Q(tipo_documento='vale'),
        pk=pk, 
        empresa=request.empresa
    )
    url = reverse('ventas:vale_html', args=[ticket.pk])
    qs = request.GET.urlencode()
    if qs:
        return redirect(f'{url}?{qs}')
    return redirect(url)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def pos_tickets_hoy(request):
    """API JSON: documentos del turno de caja (emitidos e impresos), no solo tickets pendientes."""
    from django.core.exceptions import ObjectDoesNotExist
    from django.http import JsonResponse
    from empresas.middleware import resolver_sucursal_operativa

    sucursal = resolver_sucursal_operativa(request)
    estacion = None
    estacion_id = request.session.get('pos_estacion_id')
    if estacion_id:
        estacion = EstacionTrabajo.objects.filter(id=estacion_id, empresa=request.empresa).first()

    apertura = _apertura_caja_estacion(request.empresa, estacion, sucursal)
    fecha_dia = fecha_documento_caja(apertura)
    tz = timezone.get_current_timezone()
    if apertura and apertura.fecha_apertura:
        inicio_turno = apertura.fecha_apertura
        if timezone.is_naive(inicio_turno):
            inicio_turno = timezone.make_aware(inicio_turno, tz)
    else:
        inicio_turno = timezone.make_aware(datetime.combine(fecha_dia, time.min), tz)

    q_turno = (
        Q(fecha=fecha_dia)
        | Q(fecha_creacion__gte=inicio_turno)
        | Q(dte__fecha_emision=fecha_dia)
        | Q(dte__fecha_creacion__gte=inicio_turno)
    )
    if apertura:
        q_turno |= Q(venta_final__apertura_caja=apertura) | Q(venta_preventa__apertura_caja=apertura)

    # En cierre directo la boleta impresa sigue siendo tipo 'ticket' + facturado + DTE.
    emitidos = (
        Q(tipo_documento__in=['boleta', 'factura', 'guia', 'vale'])
        | Q(dte__isnull=False)
        | Q(tipo_documento='ticket', facturado=True, tipo_documento_planeado__in=['boleta', 'factura', 'guia'])
    )
    pendientes = Q(tipo_documento='ticket', facturado=False)

    tickets = Venta.objects.filter(
        empresa=request.empresa,
    ).filter(
        q_turno,
    ).filter(
        emitidos | pendientes,
    ).exclude(
        estado='anulada',
    ).exclude(
        tipo_documento='cotizacion',
    ).select_related(
        'cliente', 'vendedor', 'estacion_trabajo', 'dte',
    ).distinct().order_by('-id')

    if sucursal:
        tickets = tickets.filter(Q(sucursal=sucursal) | Q(sucursal__isnull=True))

    tickets_data = []
    total_monto = Decimal('0.00')
    for ticket in tickets:
        try:
            dte = ticket.dte
        except ObjectDoesNotExist:
            dte = None

        if ticket.tipo_documento in ('boleta', 'factura', 'guia'):
            tipo_doc = ticket.tipo_documento
            pendiente = False
            numero = ticket.numero_venta
        elif dte or ticket.facturado:
            tipo_doc = ticket.tipo_documento_planeado or ticket.tipo_documento
            pendiente = False
            numero = f"{dte.folio:06d}" if dte and dte.folio else ticket.numero_venta
        else:
            tipo_doc = ticket.tipo_documento_planeado or ticket.tipo_documento
            pendiente = True
            numero = ticket.numero_venta

        tipo_doc_display = {
            'boleta': 'BOL',
            'factura': 'FACT',
            'guia': 'GUÍA',
            'nota_credito': 'N/C',
            'nota_debito': 'N/D',
            'cotizacion': 'COT',
            'vale': 'VALE',
            'ticket': 'TKT',
        }.get(tipo_doc, (tipo_doc or '').upper())

        if dte:
            imprimir_url = reverse('facturacion_electronica:ver_factura_electronica', args=[dte.pk])
        elif ticket.tipo_documento in ('vale', 'ticket'):
            imprimir_url = reverse('ventas:vale_html', args=[ticket.pk])
        else:
            imprimir_url = reverse('ventas:venta_html', args=[ticket.pk])

        fecha_local = timezone.localtime(ticket.fecha_creacion)
        total_monto += ticket.total or Decimal('0.00')

        tickets_data.append({
            'id': ticket.id,
            'numero': numero,
            'fecha': fecha_local.strftime('%H:%M'),
            'cliente': ticket.cliente.nombre if ticket.cliente else 'Sin cliente',
            'vendedor': ticket.vendedor.nombre if ticket.vendedor else 'Sin vendedor',
            'estacion': ticket.estacion_trabajo.nombre if ticket.estacion_trabajo else 'Sin estación',
            'total': float(ticket.total),
            'estado': ticket.get_estado_display(),
            'tipo_documento': tipo_doc_display,
            'pendiente': pendiente,
            'imprimir_url': imprimir_url,
        })

    return JsonResponse({
        'success': True,
        'tickets': tickets_data,
        'total_count': len(tickets_data),
        'total_monto': float(total_monto),
        'fecha_dia': fecha_dia.strftime('%d-%m-%Y'),
    })


# ========== LIBRO DE VENTAS ==========

def _rango_fechas_libro(request):
    """
    Rango de fechas para libros (Ventas, Guías, etc.):
    Por defecto, siempre del primer día al último día del mes actual.
    Si se indican fechas explícitas por GET, se respeta ese rango.
    """
    import calendar
    hoy = timezone.localdate()
    primer = hoy.replace(day=1)
    ultimo = hoy.replace(day=calendar.monthrange(hoy.year, hoy.month)[1])
    raw_desde = (request.GET.get('fecha_desde') or '').strip()
    raw_hasta = (request.GET.get('fecha_hasta') or '').strip()
    if not raw_desde and not raw_hasta:
        return primer.strftime('%Y-%m-%d'), ultimo.strftime('%Y-%m-%d'), primer, ultimo
    fecha_desde = raw_desde or primer.strftime('%Y-%m-%d')
    fecha_hasta = raw_hasta or ultimo.strftime('%Y-%m-%d')
    try:
        d1 = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        d2 = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    except ValueError:
        d1, d2 = primer, ultimo
        fecha_desde, fecha_hasta = d1.strftime('%Y-%m-%d'), d2.strftime('%Y-%m-%d')
    if d2 < d1:
        d1, d2 = d2, d1
        fecha_desde, fecha_hasta = d1.strftime('%Y-%m-%d'), d2.strftime('%Y-%m-%d')
    return fecha_desde, fecha_hasta, d1, d2


def _q_periodo_libro(fecha_desde_obj, fecha_hasta_obj):
    """
    Filtro estricto por fecha de emisión/documento para el libro.
    Garantiza que sólo ingresen documentos cuya fecha tributaria esté dentro del período.
    """
    q_ventas = Q(fecha__gte=fecha_desde_obj, fecha__lte=fecha_hasta_obj)
    q_dtes = (
        Q(fecha_emision__gte=fecha_desde_obj, fecha_emision__lte=fecha_hasta_obj)
        | (Q(fecha_emision__isnull=True) & Q(fecha__gte=fecha_desde_obj, fecha__lte=fecha_hasta_obj))
    )
    return q_ventas, q_dtes


def _fecha_documento_libro(doc, es_dte=False):
    """Fecha que se muestra y ordena: día de emisión / documento."""
    if es_dte:
        return getattr(doc, 'fecha_emision', None) or getattr(doc, 'fecha', None) or (getattr(doc, 'venta', None) and getattr(doc.venta, 'fecha', None))
    return getattr(doc, 'fecha', None)


def _dtes_sin_track_libro(request):
    """Pendientes reales del período del Libro: sin Track, más recientes primero."""
    from facturacion_electronica.validacion_envio import obtener_dtes_pendientes_envio

    _fecha_desde, _fecha_hasta, fecha_desde_obj, fecha_hasta_obj = _rango_fechas_libro(request)
    _q_ventas, q_dtes = _q_periodo_libro(fecha_desde_obj, fecha_hasta_obj)
    pendientes = obtener_dtes_pendientes_envio(request.empresa).filter(q_dtes)
    tipo = (request.GET.get('tipo_documento') or '').strip()
    if tipo.isdigit():
        pendientes = pendientes.filter(tipo_dte=tipo)
    return pendientes.order_by('-fecha_emision', '-folio', '-id')


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def libro_ventas(request):
    """
    Libro de Ventas - Listado completo de documentos emitidos (Ventas + DTEs)
    con filtros avanzados por tipo, fecha, cliente, vendedor y forma de pago
    """
    from facturacion_electronica.models import DocumentoTributarioElectronico
    from .models import NotaCredito, NotaDebito
    from itertools import chain

    fecha_desde, fecha_hasta, fecha_desde_obj, fecha_hasta_obj = _rango_fechas_libro(request)
    
    # Obtener parámetros de filtros
    tipo_documento = request.GET.get('tipo_documento', '')
    cliente_id = request.GET.get('cliente', '').strip()
    vendedor_id = request.GET.get('vendedor', '')
    forma_pago_id = request.GET.get('forma_pago', '')
    estado = request.GET.get('estado', '')
    search = request.GET.get('search', '')
    
    # Consulta base: ventas confirmadas y facturadas/cobradas SIN DTE asociado
    # (Excluimos todas las ventas del POS que no han sido convertidas a DTE para que el Libro de Ventas sea oficial)
    # EXCLUIMOS Guías de Despacho ya que ahora tienen su propio libro
    ventas = Venta.objects.filter(
        empresa=request.empresa,
        estado='confirmada',
        dte__isnull=True,
        tipo_documento__in=['boleta', 'factura', 'factura_electronica']
    ).exclude(
        Q(numero_venta__icontains='test') | 
        Q(tipo_documento__in=['cotizacion', 'guia', 'vale', 'ticket'])
    ).select_related('cliente', 'vendedor', 'forma_pago', 'estacion_trabajo')

    
    # Consulta DTEs (Documentos Tributarios Electrónicos)
    # EXCLUIMOS Guías de Despacho (Tipo 52)
    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa
    ).exclude(
        Q(folio__icontains='test') |
        Q(tipo_dte='52')
    ).select_related(
        'caf_utilizado', 'usuario_creacion', 'venta', 'venta__cliente', 'venta__vendedor', 'venta__forma_pago'
    ).prefetch_related(
        Prefetch('notas_credito', queryset=NotaCredito.objects.only('id')),
        Prefetch('notas_debito', queryset=NotaDebito.objects.only('id')),
    ).defer(
        'xml_dte', 'xml_firmado', 'timbre_electronico', 'timbre_pdf417',
        'respuesta_sii', 'datos_pdf417'
    )
    
    q_ventas_periodo, q_dtes_periodo = _q_periodo_libro(fecha_desde_obj, fecha_hasta_obj)
    ventas = ventas.filter(q_ventas_periodo)
    dtes = dtes.filter(q_dtes_periodo)
    
    # Filtrar por tipo de documento
    if tipo_documento:
        if tipo_documento == '33':
            dtes = dtes.filter(tipo_dte='33')
            ventas = ventas.filter(tipo_documento__in=['factura', 'factura_electronica'])
        elif tipo_documento == '34':
            dtes = dtes.filter(tipo_dte='34')
            ventas = ventas.filter(tipo_documento='factura_exenta')
        elif tipo_documento == '39':
            dtes = dtes.filter(tipo_dte='39')
            ventas = ventas.filter(tipo_documento='boleta')
        elif tipo_documento == '41':
            dtes = dtes.filter(tipo_dte='41')
            ventas = ventas.filter(tipo_documento='boleta_exenta')
        elif tipo_documento == '52':
            dtes = dtes.filter(tipo_dte='52')
            ventas = ventas.filter(tipo_documento='guia')
        elif tipo_documento in ['56', '61']:
            dtes = dtes.filter(tipo_dte=tipo_documento)
            ventas = ventas.none()
        elif tipo_documento in ['factura', 'factura_electronica']:
            ventas = ventas.filter(tipo_documento__in=['factura', 'factura_electronica'])
            dtes = dtes.filter(tipo_dte='33')
        elif tipo_documento == 'boleta':
            ventas = ventas.filter(tipo_documento='boleta')
            dtes = dtes.filter(tipo_dte='39')
        else:
            ventas = ventas.filter(tipo_documento=tipo_documento)
            dtes = dtes.none()
    
    # Filtros adicionales para ventas y DTEs
    if cliente_id:
        ventas = ventas.filter(
            Q(cliente__nombre__icontains=cliente_id) |
            Q(cliente__rut__icontains=cliente_id)
        )
    
    if vendedor_id:
        ventas = ventas.filter(vendedor_id=vendedor_id)
    
    if forma_pago_id:
        ventas = ventas.filter(forma_pago_id=forma_pago_id)
    
    if estado:
        ventas = ventas.filter(estado=estado)
    
    # Filtros para DTEs (usar venta asociada si existe)
    if cliente_id:
        dtes = dtes.filter(
            Q(venta__cliente__nombre__icontains=cliente_id) |
            Q(venta__cliente__rut__icontains=cliente_id) |
            Q(razon_social_receptor__icontains=cliente_id) |
            Q(rut_receptor__icontains=cliente_id)
        )
    
    if vendedor_id:
        dtes = dtes.filter(venta__vendedor_id=vendedor_id)
    
    if forma_pago_id:
        dtes = dtes.filter(venta__forma_pago_id=forma_pago_id)
    
    # Búsqueda en ambos tipos
    if search:
        ventas = ventas.filter(
            Q(numero_venta__icontains=search) |
            Q(cliente__nombre__icontains=search) |
            Q(cliente__rut__icontains=search) |
            Q(observaciones__icontains=search)
        )
        dtes = dtes.filter(
            Q(folio__icontains=search) |
            Q(razon_social_receptor__icontains=search) |
            Q(rut_receptor__icontains=search) |
            Q(glosa_sii__icontains=search)
        )
    
    # Combinar ventas y DTEs
    ventas_list = list(ventas)
    dtes_list = list(dtes)
    
    # Por defecto, las últimas impresas primero (alta en el sistema), no por fecha de caja.
    sort = request.GET.get('sort') or 'reciente'
    direction = request.GET.get('direction', 'desc')
    
    for venta in ventas_list:
        venta.fecha_documento = _fecha_documento_libro(venta, es_dte=False)
        venta.es_dte = False
        # Mapeo de tipos para ordenamiento consistente
        tipo_map = {'factura': '33', 'factura_electronica': '33', 'boleta': '39', 'guia': '52', 'nota_credito': '61', 'nota_debito': '56'}
        venta.sort_tipo = tipo_map.get(venta.tipo_documento, '99')
        try:
            import re
            venta.sort_folio = int(re.sub(r'\D', '', str(venta.numero_venta))) if venta.numero_venta else 0
        except:
            venta.sort_folio = 0
    
    for dte in dtes_list:
        if str(getattr(dte, 'estado_sii', '') or '').strip().lower() in {'rechazado', 'error_envio', 'error'}:
            try:
                dte.corregir_falso_rechazo_espera()
            except Exception:
                pass
        dte.fecha_documento = _fecha_documento_libro(dte, es_dte=True)
        dte.es_dte = True
        dte.sort_tipo = getattr(dte, 'tipo_dte', '99')
        try:
            dte.sort_folio = int(dte.folio) if dte.folio else 0
        except:
            dte.sort_folio = 0
        # Marcar y ajustar montos para Notas de Crédito (tipo 61) como negativos
        dte.es_nota_credito = (getattr(dte, 'tipo_dte', '') == '61')
        dte.es_nota_debito = (getattr(dte, 'tipo_dte', '') == '56')
        if dte.es_nota_credito:
            dte.monto_neto = -(dte.monto_neto or 0)
            dte.monto_iva = -(dte.monto_iva or 0)
            dte.monto_total = -(dte.monto_total or 0)
            # Exponer ID de Nota de Crédito asociada (si existe) para el template
            try:
                nc = dte.notas_credito.all()[0] if hasattr(dte, 'notas_credito') and dte.notas_credito.all() else None
                dte.notacredito_id = nc.id if nc else None
            except Exception:
                dte.notacredito_id = None
        if dte.es_nota_debito:
            try:
                nd = dte.notas_debito.all()[0] if hasattr(dte, 'notas_debito') and dte.notas_debito.all() else None
                dte.notadebito_id = nd.id if nd else None
            except Exception:
                dte.notadebito_id = None
    
    fecha_min = datetime.min.date()

    def _ts_creacion(doc):
        fc = getattr(doc, 'fecha_creacion', None)
        if fc is None:
            return 0.0
        try:
            if timezone.is_aware(fc):
                fc = timezone.localtime(fc)
            return fc.timestamp()
        except Exception:
            return 0.0

    def get_sort_key(doc):
        if sort == 'tipo_folio':
            return (doc.sort_tipo, doc.sort_folio)
        elif sort == 'fecha':
            return (doc.fecha_documento or fecha_min, doc.sort_folio)
        elif sort == 'folio':
            return doc.sort_folio
        elif sort == 'cliente':
            if hasattr(doc, 'razon_social_receptor'):
                return (doc.razon_social_receptor or '').lower()
            return (doc.cliente.nombre if doc.cliente else '').lower()
        elif sort == 'total':
            return getattr(doc, 'monto_total', getattr(doc, 'total', 0))
        return (_ts_creacion(doc), doc.sort_folio)

    reverse_sort = direction == 'desc'
    # Si es tipo_folio y asc, normalmente queremos tipo asc y folio asc.
    
    documentos = sorted(
        chain(ventas_list, dtes_list),
        key=get_sort_key,
        reverse=reverse_sort
    )
    
    # Estadísticas del período (solo si hay datos)
    stats_ventas = ventas.aggregate(
        total_neto=Sum('neto'),
        total_iva=Sum('iva'),
        total_general=Sum('total')
    )
    
    # Calcular stats DTE desde la lista ajustada (NC negativas)
    if dtes_list:
        from decimal import Decimal as _Dec
        stats_dtes = {
            'total_neto': sum((d.monto_neto or 0) for d in dtes_list) or _Dec('0'),
            'total_iva': sum((d.monto_iva or 0) for d in dtes_list) or _Dec('0'),
            'total_general': sum((d.monto_total or 0) for d in dtes_list) or _Dec('0'),
        }
    else:
        stats_dtes = {'total_neto': 0, 'total_iva': 0, 'total_general': 0}
    
    estadisticas = {
        'total_documentos': len(documentos),
        'total_neto': (stats_ventas['total_neto'] or 0) + (stats_dtes['total_neto'] or 0),
        'total_iva': (stats_ventas['total_iva'] or 0) + (stats_dtes['total_iva'] or 0),
        'total_general': (stats_ventas['total_general'] or 0) + (stats_dtes['total_general'] or 0),
    }
    
    # Estadísticas por tipo
    stats_ventas_tipo = ventas.values('tipo_documento').annotate(
        cantidad=Count('id'),
        total=Sum('total')
    )
    
    # Construir stats por tipo DTE desde la lista (NC como negativas)
    from collections import defaultdict
    from decimal import Decimal as _Dec
    dte_stats_map = defaultdict(lambda: {'cantidad': 0, 'total': _Dec('0')})
    for d in dtes_list:
        t = getattr(d, 'tipo_dte', None)
        if not t:
            continue
        dte_stats_map[t]['cantidad'] += 1
        dte_stats_map[t]['total'] += (d.monto_total or _Dec('0'))

    tipo_map_stats = {'factura': '33', 'factura_electronica': '33', 'boleta': '39', 'guia': '52'}
    for sv in stats_ventas_tipo:
        td = sv['tipo_documento']
        codigo_sii = tipo_map_stats.get(td, td)
        dte_stats_map[codigo_sii]['cantidad'] += sv['cantidad']
        dte_stats_map[codigo_sii]['total'] += (sv['total'] or _Dec('0'))

    stats_por_tipo = [
        {'tipo_documento': k, 'cantidad': v['cantidad'], 'total': v['total']}
        for k, v in dte_stats_map.items()
    ]
    
    # Paginación. En modo impresión se incluyen todos los documentos
    # filtrados para generar un libro completo y no solo la página visible.
    print_mode = request.GET.get('imprimir') == '1'
    paginator = Paginator(documentos, max(len(documentos), 1) if print_mode else 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opciones para filtros
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    # Tipos de documento: Solo DTEs con códigos SII + tipos POS sin equivalente DTE
    tipos_documento_dict = {
        # DTEs (Documentos Tributarios Electrónicos)
        '33': 'Factura Electrónica (33)',
        '34': 'Factura Exenta Electrónica (34)',
        '39': 'Boleta Electrónica (39)',
        '41': 'Boleta Exenta Electrónica (41)',
        '52': 'Guía de Despacho Electrónica (52)',
        '56': 'Nota de Débito Electrónica (56)',
        '61': 'Nota de Crédito Electrónica (61)',
    }

    orden_grupos = ['39', '41', '33', '34', '56', '61', '52', 'factura', 'boleta', 'guia', 'vale', '99']
    nombres_grupo = {
        '33': 'Facturas electrónicas',
        '34': 'Facturas exentas electrónicas',
        '39': 'Boletas electrónicas',
        '41': 'Boletas exentas electrónicas',
        '56': 'Notas de débito electrónicas',
        '61': 'Notas de crédito electrónicas',
        '52': 'Guías de despacho',
        'factura': 'Facturas POS',
        'boleta': 'Boletas POS',
        'guia': 'Guías POS',
        'vale': 'Vales',
        '99': 'Otros documentos',
    }
    badges_grupo = {
        '33': 'FE', '34': 'FEX', '39': 'BE', '41': 'BEX',
        '56': 'ND', '61': 'NC', '52': 'GD',
        'factura': 'F', 'boleta': 'BP', 'guia': 'G', 'vale': 'V', '99': 'OT',
    }

    def _monto_doc(doc, campo_dte, campo_venta):
        if getattr(doc, 'es_dte', False):
            return getattr(doc, campo_dte, 0) or 0
        return getattr(doc, campo_venta, 0) or 0

    grupos_tmp = defaultdict(list)
    for doc in documentos:
        key = str(getattr(doc, 'sort_tipo', '99') or '99')
        doc.row_dom_id = f"{'dte' if getattr(doc, 'es_dte', False) else 'venta'}-{doc.id}"
        grupos_tmp[key].append(doc)

    grupos_documento = []
    keys_usadas = [k for k in orden_grupos if k in grupos_tmp]
    keys_usadas += [k for k in grupos_tmp.keys() if k not in orden_grupos]
    for key in keys_usadas:
        docs_grupo = grupos_tmp[key]
        grupos_documento.append({
            'codigo': key,
            'nombre': nombres_grupo.get(key, tipos_documento_dict.get(key, f'Tipo {key}')),
            'badge': badges_grupo.get(key, key),
            'cantidad': len(docs_grupo),
            'neto': sum(_monto_doc(d, 'monto_neto', 'neto') for d in docs_grupo),
            'iva': sum(_monto_doc(d, 'monto_iva', 'iva') for d in docs_grupo),
            'total': sum(_monto_doc(d, 'monto_total', 'total') for d in docs_grupo),
            'documentos': docs_grupo,
        })

    pendientes_envio = 0
    envio_idle_auto = True
    try:
        from facturacion_electronica.background_sender import get_background_sender
        sender = get_background_sender()
        pendientes_envio = _dtes_sin_track_libro(request).count()
        envio_idle_auto = sender.is_idle_auto(request.empresa.id)
    except Exception:
        pass
    
    context = {
        'page_obj': page_obj,
        'estadisticas': estadisticas,
        'stats_por_tipo': stats_por_tipo,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'fecha_desde_display': fecha_desde_obj.strftime('%d-%m-%Y'),
        'fecha_hasta_display': fecha_hasta_obj.strftime('%d-%m-%Y'),
        'tipo_documento': tipo_documento,
        'cliente_id': cliente_id,
        'vendedor_id': vendedor_id,
        'forma_pago_id': forma_pago_id,
        'estado': estado,
        'search': search,
        'sort': sort,
        'direction': direction,
        'vendedores': vendedores,
        'formas_pago': formas_pago,
        'tipos_documento': tipos_documento_dict,
        'print_mode': print_mode,
        'grupos_documento': grupos_documento,
        'pendientes_envio': pendientes_envio,
        'envio_idle_auto': envio_idle_auto,
    }
    
    return render(request, 'ventas/libro_ventas.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def libro_ventas_envio_background(request):
    """
    Encola al SII solo DTEs del período del Libro que aún no tienen Track.
    No consulta ni reenvía documentos que ya fueron subidos.
    """
    import logging
    from facturacion_electronica.background_sender import get_background_sender

    logger = logging.getLogger(__name__)
    es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    def _json(payload, status=200):
        return JsonResponse(payload, status=status)

    try:
        sender = get_background_sender()
        empresa_id = request.empresa.id
        pendientes_qs = _dtes_sin_track_libro(request)
        pendientes_count = pendientes_qs.count()
        stats = sender.get_stats()
    except Exception as e:
        logger.exception("No se pudo iniciar el envío de pendientes")
        return _json({'success': False, 'count': 0, 'message': f'No se pudo iniciar el envío: {e}'}, 500)

    accion = (request.GET.get('accion') or request.POST.get('accion') or '').strip()
    enviar = bool(request.GET.get('enviar')) or accion == 'enviar' or (
        request.method == 'POST' and accion != 'auto_idle'
    )
    auto_req = accion == 'auto_idle' or request.GET.get('auto_idle') is not None

    if auto_req and request.method in ('GET', 'POST'):
        raw = request.GET.get('enabled', request.POST.get('enabled', '1'))
        enabled = str(raw) in ('1', 'true', 'True', 'on')
        auto_idle = sender.set_idle_auto(empresa_id, enabled)
        return _json({
            'success': True,
            'auto_idle': auto_idle,
            'pendientes': pendientes_count,
            'en_cola': stats.get('en_cola', 0),
            'message': 'Envío automático activado.' if auto_idle else 'Envío automático desactivado. Puede enviar con el botón cuando quiera.',
        })

    if request.method == 'GET' and not enviar:
        return _json({
            'success': True,
            'pendientes': pendientes_count,
            'en_cola': stats.get('en_cola', 0),
            'en_proceso': stats.get('en_proceso', 0),
            'enviados': stats.get('enviados', 0),
            'errores': stats.get('errores', 0),
            'auto_idle': sender.is_idle_auto(empresa_id),
        })

    try:
        dte_ids = list(pendientes_qs.values_list('id', flat=True)[:8])
        enviados, fallidos = sender.enviar_ahora(dte_ids, empresa_id) if dte_ids else ([], [])
        stats = sender.get_stats()
    except Exception as e:
        logger.exception("Error al enviar DTEs pendientes")
        return _json({'success': False, 'count': 0, 'message': f'Error al enviar: {e}'}, 500)

    restantes = _dtes_sin_track_libro(request).count()
    count = len(enviados)
    partes = []
    if enviados:
        detalle = ', '.join(
            f"{item['folio']}" + (f" Track {item['track']}" if item.get('track') else '')
            for item in enviados
        )
        partes.append(f'Se envió {detalle}' if count == 1 else f'Se enviaron {count}: {detalle}')
    if fallidos:
        partes.append(
            'No se pudo enviar '
            + ', '.join(f"{item['folio']} ({item['error']})" for item in fallidos)
        )
    if partes:
        mensaje = '. '.join(partes) + '.'
    elif restantes:
        mensaje = f'Hay {restantes} del período sin Track; el envío continúa en segundo plano.'
    else:
        mensaje = 'No hay documentos del período sin enviar al SII.'
    payload = {
        'success': bool(enviados) or not fallidos,
        'count': count,
        'consultados': 0,
        'pendientes': restantes,
        'en_cola': stats.get('en_cola', 0),
        'en_proceso': stats.get('en_proceso', 0),
        'message': mensaje,
    }
    if es_ajax:
        return _json(payload)
    from django.contrib import messages as django_messages
    if count:
        django_messages.success(request, mensaje)
    else:
        django_messages.info(request, mensaje)
    return redirect(request.GET.get('return_url') or reverse('ventas:libro_ventas'))


# ============================================
# CRUD PRECIOS ESPECIALES CLIENTES
# ============================================

@login_required
@requiere_empresa
@permission_required('ventas.view_precioclientearticulo', raise_exception=True)
def precio_cliente_list(request):
    """Lista de precios especiales por cliente"""
    from .models import PrecioClienteArticulo
    from clientes.models import Cliente
    from articulos.models import Articulo
    from datetime import date
    
    # Base queryset
    precios = PrecioClienteArticulo.objects.filter(empresa=request.empresa).select_related('cliente', 'articulo').order_by('cliente__nombre', 'articulo__nombre')
    
    # Filtros GET
    q = request.GET.get('q', '').strip()
    cliente_id = request.GET.get('cliente', '').strip()
    articulo_id = request.GET.get('articulo', '').strip()
    estado = request.GET.get('estado', '').strip()  # 'activo' | 'inactivo'
    vigencia = request.GET.get('vigencia', '').strip()  # 'vigente' | 'futura' | 'vencida'

    # Limpiar IDs de posibles caracteres no numéricos (como espacios de miles: \xa0)
    if cliente_id:
        cliente_id = ''.join(filter(str.isdigit, cliente_id))
    if articulo_id:
        articulo_id = ''.join(filter(str.isdigit, articulo_id))
    
    if q:
        precios = precios.filter(
            Q(cliente__nombre__icontains=q) |
            Q(articulo__nombre__icontains=q) |
            Q(articulo__codigo__icontains=q)
        )
    if cliente_id:
        precios = precios.filter(cliente_id=cliente_id)
    if articulo_id:
        precios = precios.filter(articulo_id=articulo_id)
    if estado in ['activo', 'inactivo']:
        precios = precios.filter(activo=(estado == 'activo'))
    if vigencia:
        hoy = date.today()
        if vigencia == 'vigente':
            precios = precios.filter(
                Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=hoy),
                Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy)
            )
        elif vigencia == 'futura':
            precios = precios.filter(fecha_inicio__gt=hoy)
        elif vigencia == 'vencida':
            precios = precios.filter(fecha_fin__lt=hoy)
    
    # Paginación
    paginator = Paginator(precios, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para filtros (listas)
    clientes_list = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')
    articulos_list = Articulo.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')[:500]
    
    context = {
        'page_obj': page_obj,
        'precios': page_obj.object_list,
        'q': q,
        'cliente_id': cliente_id,
        'articulo_id': articulo_id,
        'estado': estado,
        'vigencia': vigencia,
        'clientes_list': clientes_list,
        'articulos_list': articulos_list,
    }
    
    return render(request, 'ventas/precio_cliente_list.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.add_precioclientearticulo', raise_exception=True)
def precio_cliente_create(request):
    """Crear precio especial"""
    from .models import PrecioClienteArticulo
    from .forms import PrecioClienteArticuloForm
    from clientes.models import Cliente
    from articulos.models import Articulo
    from django.http import JsonResponse
    
    if request.method == 'POST':
        form = PrecioClienteArticuloForm(request.POST)
        if form.is_valid():
            precio = form.save(commit=False)
            precio.empresa = request.empresa
            precio.creado_por = request.user
            precio.save()
            return JsonResponse({'success': True, 'message': 'Precio especial creado exitosamente'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    
    # GET: Retornar formulario
    form = PrecioClienteArticuloForm()
    form.fields['cliente'].queryset = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')
    
    # Preparar artículos con sus precios BASE NETOS para JavaScript
    articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    articulos_precios = {str(a.id): int(round(float(a._string_to_decimal(a.precio_venta)))) for a in articulos}
    
    form.fields['articulo'].queryset = articulos
    
    return render(request, 'ventas/precio_cliente_form.html', {
        'form': form,
        'articulos_precios': articulos_precios
    })


@login_required
@requiere_empresa
@permission_required('ventas.change_precioclientearticulo', raise_exception=True)
def precio_cliente_edit(request, pk):
    """Editar precio especial"""
    from .models import PrecioClienteArticulo
    from .forms import PrecioClienteArticuloForm
    from clientes.models import Cliente
    from articulos.models import Articulo
    from django.http import JsonResponse
    
    try:
        precio = PrecioClienteArticulo.objects.get(pk=pk, empresa=request.empresa)
        
        if request.method == 'POST':
            form = PrecioClienteArticuloForm(request.POST, instance=precio)
            if form.is_valid():
                form.save()
                return JsonResponse({'success': True, 'message': 'Precio especial actualizado exitosamente'})
            else:
                return JsonResponse({'success': False, 'errors': form.errors})
        
        # GET: Retornar formulario
        form = PrecioClienteArticuloForm(instance=precio)
        form.fields['cliente'].queryset = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')
        
        # Preparar artículos con sus precios BASE NETOS para JavaScript
        articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
        articulos_precios = {str(a.id): int(round(float(a._string_to_decimal(a.precio_venta)))) for a in articulos}
        
        form.fields['articulo'].queryset = articulos
        
        return render(request, 'ventas/precio_cliente_form.html', {
            'form': form, 
            'precio': precio,
            'articulos_precios': articulos_precios
        })
    
    except PrecioClienteArticulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Precio especial no encontrado'})


@login_required
@requiere_empresa
@permission_required('ventas.delete_precioclientearticulo', raise_exception=True)
def precio_cliente_delete(request, pk):
    """Eliminar precio especial"""
    from .models import PrecioClienteArticulo
    from django.http import JsonResponse
    
    try:
        precio = PrecioClienteArticulo.objects.get(pk=pk, empresa=request.empresa)
        precio.delete()
        return JsonResponse({'success': True, 'message': 'Precio especial eliminado exitosamente'})
    except PrecioClienteArticulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Precio especial no encontrado'})


@login_required
@requiere_empresa_json
def precio_cliente_articulo_api(request, cliente_id, articulo_id):
    """API para obtener precio especial de un artículo para un cliente"""
    from .models import PrecioClienteArticulo
    from django.http import JsonResponse
    from django.db.models import Q
    from django.utils import timezone
    
    try:
        hoy = timezone.localdate()
        # Buscar precio especial activo y vigente (fechas nulas = vigencia abierta)
        precio_especial = PrecioClienteArticulo.objects.filter(
            empresa=request.empresa,
            cliente_id=cliente_id,
            articulo_id=articulo_id,
            activo=True
        ).filter(
            Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=hoy),
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy)
        ).select_related('articulo', 'articulo__categoria').first()
        
        if precio_especial and precio_especial.esta_vigente():
            return JsonResponse({
                'success': True,
                'precio_especial': float(precio_especial.precio_especial),
                'precio_final': float(precio_especial.get_precio_final()),
                'precio_neto': float(round(precio_especial.get_precio_neto(), 2)),
                'precio_con_iva': float(round(precio_especial.get_precio_con_iva(), 2)),
                'descuento_porcentaje': float(precio_especial.descuento_porcentaje or 0)
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No hay precio especial para este cliente'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@requiere_empresa_json
def precios_cliente_todos_api(request, cliente_id):
    """
    API para obtener todos los precios especiales activos y vigentes de un cliente.
    Retorna un diccionario {articulo_id: {precio_especial, precio_final, precio_neto, precio_con_iva, descuento_porcentaje}}
    """
    from .models import PrecioClienteArticulo
    from django.http import JsonResponse
    from django.db.models import Q
    from django.utils import timezone
    
    try:
        hoy = timezone.localdate()
        precios_qs = PrecioClienteArticulo.objects.filter(
            empresa=request.empresa,
            cliente_id=cliente_id,
            activo=True
        ).filter(
            Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=hoy),
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy)
        ).select_related('articulo', 'articulo__categoria')
        
        precios_dict = {}
        for p in precios_qs:
            if p.esta_vigente():
                precios_dict[p.articulo_id] = {
                    'precio_especial': float(p.precio_especial),
                    'precio_final': float(p.get_precio_final()),
                    'precio_neto': float(round(p.get_precio_neto(), 2)),
                    'precio_con_iva': float(round(p.get_precio_con_iva(), 2)),
                    'descuento_porcentaje': float(p.descuento_porcentaje or 0)
                }
        
        return JsonResponse({
            'success': True,
            'cliente_id': cliente_id,
            'precios': precios_dict
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'precios': {}
        })


@login_required
@requiere_empresa
def articulo_precio_api(request, pk):
    """API para obtener el precio de un artículo"""
    from articulos.models import Articulo
    from django.http import JsonResponse
    
    try:
        articulo = Articulo.objects.get(pk=pk, empresa=request.empresa)
        return JsonResponse({
            'success': True,
            'precio_venta': float(articulo.precio_venta),
            'nombre': articulo.nombre,
            'codigo': articulo.codigo
        })
    except Articulo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Artículo no encontrado'})
# ========== VENTAS MÓVILES (MOBILE APP) ==========

@login_required
@requiere_empresa
@never_cache
def mobile_sales_app(request):
    """
    Vista que carga el contenedor de la Aplicación Móvil (PWA).
    Esta vista es la que el vendedor abrirá en su teléfono.
    """
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    print(f"[DEBUG] Mobile App - Empresa: {request.empresa.nombre}, Vendedores encontrados: {vendedores.count()}")
    for v in vendedores:
        print(f"  - {v.codigo}: {v.nombre}")
    
    context = {
        'vendedores': vendedores,
        'empresa': request.empresa,
    }

    response = render(request, 'ventas/mobile_sales.html', context)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def mobile_sales_manifest(request):
    """Manifest PWA de la app móvil."""
    manifest = {
        "name": "GestionCloud Movil",
        "short_name": "GC Movil",
        "start_url": "/ventas/movil/",
        "scope": "/ventas/movil/",
        "display": "standalone",
        "background_color": "#F1EEE9",
        "theme_color": "#8D7B68",
        "description": "Notas de venta y cotizaciones moviles con soporte offline.",
        "icons": [
            {
                "src": "/static/image/LogoCloud.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/image/LogoCloud.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return JsonResponse(manifest)


def mobile_sales_service_worker(request):
    js = """
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method === 'GET') {
    event.respondWith(fetch(request));
  }
});
"""
    response = HttpResponse(js, content_type="application/javascript")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

    """Service worker de la app móvil."""
    js = """
const CACHE_NAME = 'gc-mobile-v3';
const APP_SHELL = [
  '/ventas/movil/manifest.webmanifest',
  '/static/image/LogoCloud.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  if (url.pathname.startsWith('/ventas/movil/api/')) {
    event.respondWith(
      fetch(request).catch(() => new Response(JSON.stringify({ success: false, offline: true }), {
        headers: { 'Content-Type': 'application/json' }
      }))
    );
    return;
  }

  const isMobilePage = request.mode === 'navigate' || url.pathname === '/ventas/movil/' || url.pathname.startsWith('/ventas/movil/');

  if (isMobilePage) {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          return networkResponse;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match('/ventas/movil/')))
    );
    return;
  }

  event.respondWith(
    fetch(request)
      .then((networkResponse) => {
        const clone = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        return networkResponse;
      })
      .catch(() => caches.match(request))
  );
});
"""
    response = HttpResponse(js, content_type="application/javascript")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@login_required
@requiere_empresa
@never_cache
def mobile_sales_gestion(request):
    """
    Vista de administración para gestionar las ventas enviadas desde el móvil
    que quedaron pendientes de procesamiento (Preventas).
    """
    from caja.models import VentaProcesada
    from .models import DispositivoMovil
    from django.utils import timezone
    from datetime import datetime, time
    
    if request.method == 'POST' and request.POST.get('action') == 'save_mobile_config':
        request.empresa.venta_movil_permite_sin_stock = request.POST.get('venta_movil_permite_sin_stock') == 'on'
        request.empresa.save(update_fields=['venta_movil_permite_sin_stock'])
        messages.success(request, 'Configuracion de ventas moviles actualizada correctamente.')
        return redirect('ventas:mobile_sales_gestion')

    if request.method == 'POST' and request.POST.get('action') == 'register_mobile_device':
        codigo_dispositivo = (request.POST.get('device_code') or '').strip().upper()
        vendedor_id = request.POST.get('device_vendedor_id') or None
        modelo = (request.POST.get('device_model') or 'Registro manual').strip()[:100]

        if not codigo_dispositivo:
            messages.error(request, 'Debe ingresar el codigo del dispositivo que muestra la tablet.')
            return redirect('ventas:mobile_sales_gestion')

        vendedor = None
        if vendedor_id:
            vendedor = Vendedor.objects.filter(pk=vendedor_id, empresa=request.empresa, activo=True).first()

        dispositivo, created = DispositivoMovil.objects.update_or_create(
            empresa=request.empresa,
            unique_id=codigo_dispositivo,
            defaults={
                'nombre_dispositivo': f"Dispositivo {codigo_dispositivo[4:9] if len(codigo_dispositivo) >= 9 else codigo_dispositivo[:8]}",
                'modelo': modelo or 'Registro manual',
                'autorizado': True,
                'vendedor': vendedor,
            }
        )

        estado = 'registrado' if created else 'actualizado'
        messages.success(request, f'Dispositivo {codigo_dispositivo} {estado} y autorizado correctamente.')
        return redirect('ventas:mobile_sales_gestion')

    # Obtener fechas del filtro o usar HOY por defecto
    fecha_desde_str = request.GET.get('desde')
    fecha_hasta_str = request.GET.get('hasta')
    
    hoy = timezone.localdate()
    
    try:
        if fecha_desde_str:
            fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
        else:
            fecha_desde = hoy
            
        if fecha_hasta_str:
            fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
        else:
            fecha_hasta = hoy
    except:
        fecha_desde = hoy
        fecha_hasta = hoy

    # Convertir a datetime para filtros precisos si es necesario
    dt_inicio = datetime.combine(fecha_desde, time.min)
    dt_fin = datetime.combine(fecha_hasta, time.max)
    
    # 1. Ventas Pendientes (Tickets/Vales móviles no facturados aún)
    ventas_pendientes = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento__in=['vale', 'ticket'],
        facturado=False,
        observaciones__icontains='[MOVIL]',
        fecha__range=[fecha_desde, fecha_hasta]
    ).order_by('-fecha_creacion')
    
    # 2. Ventas Procesadas (Trazabilidad de lo facturado realmente)
    ventas_facturadas = VentaProcesada.objects.filter(
        venta_preventa__empresa=request.empresa,
        venta_preventa__observaciones__icontains='[MOVIL]',
        fecha_proceso__range=[dt_inicio, dt_fin]
    ).select_related('venta_preventa', 'venta_final', 'usuario_proceso', 'venta_final__vendedor').order_by('-fecha_proceso')
    
    dispositivos = DispositivoMovil.objects.filter(empresa=request.empresa).order_by('-fecha_registro')
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    context = {
        'ventas': ventas_pendientes,
        'ventas_facturadas': ventas_facturadas,
        'dispositivos': dispositivos,
        'vendedores': vendedores,
        'fecha_desde': fecha_desde.strftime('%Y-%m-%d'),
        'fecha_hasta': fecha_hasta.strftime('%Y-%m-%d'),
        'titulo': 'Gestión de Ventas Móviles',
        'venta_movil_permite_sin_stock': request.empresa.venta_movil_permite_sin_stock,
    }
    
    return render(request, 'ventas/mobile_sales_gestion.html', context)

@login_required
@requiere_empresa
def venta_detail(request, pk):
    """Vista genérica para redirigir al detalle correcto de una venta"""
    venta = get_object_or_404(Venta, pk=pk, empresa=request.empresa)
    if venta.tipo_documento in ['ticket', 'vale']:
        return redirect('ventas:ticket_detail', pk=pk)
    elif venta.tipo_documento == 'cotizacion':
        return redirect('ventas:cotizacion_detail', pk=pk)
    else:
        # Para documentos finales, mostramos el HTML de impresión/vista
        return redirect('ventas:venta_html', pk=pk)


@login_required
@requiere_empresa
def mobile_api_toggle_device(request, pk):
    """API para alternar la autorización de un dispositivo desde la gestión."""
    from .models import DispositivoMovil
    dispositivo = get_object_or_404(DispositivoMovil, pk=pk, empresa=request.empresa)
    dispositivo.autorizado = not dispositivo.autorizado
    dispositivo.save()
    return JsonResponse({'success': True, 'authorized': dispositivo.autorizado})


@login_required
@requiere_empresa
def mobile_api_set_device_auth(request, pk):
    """Autoriza o cancela el acceso de un celular de vendedor."""
    import json
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    vendedor = get_object_or_404(Vendedor, pk=pk, empresa=request.empresa)
    try:
        data = json.loads(request.body or '{}')
    except Exception:
        data = {}

    if 'autorizado' not in data:
        return JsonResponse({'success': False, 'error': 'Indique si autoriza o cancela el acceso.'}, status=400)

    autorizado = bool(data.get('autorizado'))
    if autorizado and not vendedor.telefono_app:
        return JsonResponse({'success': False, 'error': 'Registre primero el número de celular.'}, status=400)

    vendedor.app_movil_activa = autorizado
    if autorizado:
        vendedor.app_movil_activado_en = timezone.now()
        vendedor.app_movil_revocado_en = None
    else:
        vendedor.app_movil_revocado_en = timezone.now()
    vendedor.save(update_fields=[
        'app_movil_activa', 'app_movil_activado_en', 'app_movil_revocado_en', 'fecha_modificacion'
    ])
    return JsonResponse({'success': True, 'authorized': vendedor.app_movil_activa})


@login_required
@requiere_empresa
def mobile_api_assign_vendedor(request, pk):
    """API para asignar/cambiar el vendedor de un dispositivo móvil"""
    from .models import DispositivoMovil, Vendedor
    dispositivo = get_object_or_404(DispositivoMovil, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            vendedor_id = data.get('vendedor_id')
            
            if vendedor_id:
                vendedor = get_object_or_404(Vendedor, pk=vendedor_id, empresa=request.empresa)
                dispositivo.vendedor = vendedor
            else:
                dispositivo.vendedor = None
                
            dispositivo.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)


@login_required
@requiere_empresa
def mobile_api_sync(request):
    """
    API que retorna toda la data necesaria para que el móvil trabaje offline.
    """
    print(f"[DEBUG] Sync Request - User: {request.user.username}, Empresa ID: {request.empresa.id}")
    from articulos.models import Articulo, CategoriaArticulo
    from clientes.models import Cliente
    
    # Obtener el vendedor seleccionado si viene en el query
    vendedor_codigo = request.GET.get('vendedor_codigo')
    
    try:
        # Data de la Empresa
        empresa_data = {
            'id': request.empresa.id,
            'nombre': request.empresa.nombre,
            'rut': request.empresa.rut,
        }
        
        # Categorías (Ordenadas alfabéticamente para mejor navegación móvil)
        categorias = CategoriaArticulo.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
        categorias_data = [{
            'id': cat.id,
            'nombre': cat.nombre,
            'exenta_iva': cat.exenta_iva
        } for cat in categorias]
        
        # Artículos (Solo los activos y que sean productos de venta)
        articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).select_related('categoria')
        articulos_data = []
        for art in articulos:
            try:
                # Limpiar strings de precios de manera robusta
                def clean_price(val):
                    if not val: return Decimal('0')
                    s_val = str(val).strip()
                    # Si tiene coma, es formato chileno (1.234,56)
                    if ',' in s_val:
                        s_val = s_val.replace('.', '').replace(',', '.')
                    # Si no tiene coma, el punto ya es el decimal o no hay.
                    try:
                        return Decimal(s_val)
                    except:
                        return Decimal('0')

                p_final = clean_price(art.precio_final)
                p_venta = clean_price(art.precio_venta)
                
                # Si el precio final es 0, usamos el de venta directamente
                if p_final == 0:
                    p_final = p_venta
                
                articulos_data.append({
                    'id': art.id,
                    'codigo': art.codigo,
                    'codigo_barras': art.codigo_barras,
                    'nombre': art.nombre,
                    'precio': int(p_final.quantize(Decimal('1'), rounding='ROUND_HALF_UP')),
                    'categoria_id': art.categoria_id,
                    'stock': art.stock_actual,
                    'control_stock': art.control_stock,
                })
            except Exception as e_art:
                print(f"[ERROR] Sync Articulo {art.id}: {e_art}")
                continue

        # Clientes: si el vendedor no tiene cartera asignada, no bloquear la app.
        vendedor_id_sync = request.GET.get('vendedor_id')
        clientes_query = Cliente.objects.filter(empresa=request.empresa, estado='activo').order_by('nombre')
        
        if vendedor_id_sync:
            clientes_filtrados = clientes_query.filter(vendedor_id=vendedor_id_sync)
            clientes_query = clientes_filtrados if clientes_filtrados.exists() else clientes_query

        clientes = clientes_query[:2000]
        clientes_data = [{
            'id': cli.id,
            'nombre': cli.nombre,
            'rut': cli.rut,
            'giro': cli.giro,
            'direccion': cli.direccion,
            'comuna': cli.comuna,
            'ciudad': cli.ciudad,
            'telefono': cli.telefono,
            'email': cli.email,
        } for cli in clientes]
        
        # Vendedores
        vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True)
        vendedores_data = [{
            'id': v.id,
            'codigo': v.codigo,
            'nombre': v.nombre,
        } for v in vendedores]
        
        # Formas de Pago
        formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True)
        formas_pago_data = [{
            'id': fp.id,
            'nombre': fp.nombre,
            'codigo': fp.codigo,
        } for fp in formas_pago]

        print(f"[DEBUG] Sync Data Summary for {request.empresa.nombre}:")
        print(f"  - Articulos: {len(articulos_data)}")
        print(f"  - Categorias: {len(categorias_data)}")
        print(f"  - Clientes: {len(clientes_data)}")
        print(f"  - Vendedores: {len(vendedores_data)}")

        return JsonResponse({
            'success': True,
            'empresa': empresa_data,
            'categorias': categorias_data,
            'articulos': articulos_data,
            'clientes': clientes_data,
            'vendedores': vendedores_data,
            'formas_pago': formas_pago_data,
            'configuracion': {
                'permite_sin_stock': request.empresa.venta_movil_permite_sin_stock,
                'intervalo_sync_minutos': 5,
            },
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        print(f"[CRITICAL ERROR] Sync API Failed: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@requiere_empresa
def mobile_api_verify_device(request):
    """
    Autoriza la app por número de celular del vendedor.
    El número debe estar registrado y activo. Devuelve un token para trabajar offline.
    """
    import json

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body or '{}')
        telefono = normalizar_telefono_cl(data.get('telefono') or data.get('deviceId') or '')

        if not telefono:
            return JsonResponse({
                'success': False,
                'error': 'Ingrese un celular chileno, por ejemplo +56 9 63697225.',
            }, status=400)

        user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:250]
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        vendedor = Vendedor.objects.filter(
            empresa=request.empresa,
            telefono_app=telefono,
        ).first()

        if not vendedor:
            # Registrar o actualizar solicitud de acceso pendiente
            solicitud, created = SolicitudAccesoMovil.objects.get_or_create(
                empresa=request.empresa,
                telefono=telefono,
                defaults={
                    'dispositivo_info': user_agent,
                    'ip_origen': ip if ip else None,
                    'intentos': 1,
                    'estado': 'pendiente',
                }
            )
            if not created:
                solicitud.intentos = F('intentos') + 1
                solicitud.estado = 'pendiente'
                if user_agent:
                    solicitud.dispositivo_info = user_agent
                if ip:
                    solicitud.ip_origen = ip
                solicitud.save(update_fields=['intentos', 'estado', 'dispositivo_info', 'ip_origen', 'fecha_ultimo_intento'])

            return JsonResponse({
                'success': True,
                'authorized': False,
                'telefono': formatear_telefono_cl(telefono),
                'error': 'Número no registrado. Pida a administración que lo active en Vendedores.',
                'vendedor': None,
            })

        autorizado = bool(vendedor.activo and vendedor.app_movil_activa and vendedor.telefono_app)
        if autorizado:
            # Actualizar solicitud como aprobada si existía
            SolicitudAccesoMovil.objects.filter(
                empresa=request.empresa,
                telefono=telefono,
                estado='pendiente'
            ).update(estado='aprobada', vendedor_asignado=vendedor)

        token = emitir_token_app(request.empresa.id, vendedor.id, telefono) if autorizado else ''

        return JsonResponse({
            'success': True,
            'authorized': autorizado,
            'telefono': formatear_telefono_cl(telefono),
            'authToken': token,
            'offlineHours': AUTH_OFFLINE_HOURS,
            'vendedor': {
                'id': vendedor.id,
                'nombre': vendedor.nombre,
                'codigo': vendedor.codigo,
            } if autorizado else None,
            'error': None if autorizado else 'Este celular no está activo para vender.',
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@requiere_empresa
def mobile_api_save_client(request):
    """
    API para recibir un nuevo cliente desde el dispositivo móvil.
    """
    import json
    from clientes.models import Cliente
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        nombre = data.get('nombre')
        rut = data.get('rut')
        giro = data.get('giro', '')
        direccion = data.get('direccion', '')
        comuna = data.get('comuna', '')
        ciudad = data.get('ciudad', '')
        telefono = data.get('telefono', '')
        email = data.get('email', '')
        vendedor_id = data.get('vendedor_id')
        
        # Validaciones básicas
        if not nombre or not rut:
            return JsonResponse({'success': False, 'error': 'Nombre y RUT son obligatorios'}, status=400)
            
        # Verificar si ya existe
        cliente_existente = Cliente.objects.filter(empresa=request.empresa, rut=rut).first()
        if cliente_existente:
            return JsonResponse({
                'success': True,
                'cliente_id': cliente_existente.id,
                'nombre': cliente_existente.nombre,
                'message': 'El cliente ya existía en el sistema.'
            })
            
        # Crear cliente
        cliente = Cliente.objects.create(
            empresa=request.empresa,
            nombre=nombre,
            rut=rut,
            giro=giro,
            direccion=direccion,
            comuna=comuna,
            ciudad=ciudad,
            telefono=telefono,
            email=email,
            vendedor_id=vendedor_id,
            creado_por=request.user
        )
        
        return JsonResponse({
            'success': True,
            'cliente_id': cliente.id,
            'nombre': cliente.nombre
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _mobile_cotizacion_share_payload(request, venta):
    es_cotizacion = (
        venta.tipo_documento == 'cotizacion' or
        venta.tipo_documento_planeado == 'cotizacion'
    )
    if not es_cotizacion:
        return None

    share_url = request.build_absolute_uri(reverse('ventas:cotizacion_html', args=[venta.id]))
    cliente_nombre = venta.get_cliente_nombre()
    empresa_nombre = getattr(venta.empresa, 'nombre', 'GestionCloud')
    total = int(venta.total or 0)
    email = getattr(venta.cliente, 'email', '') if venta.cliente else ''
    telefono = getattr(venta.cliente, 'telefono', '') if venta.cliente else ''
    subject = f"Cotizacion {venta.numero_venta} - {empresa_nombre}"
    body = (
        f"Hola {cliente_nombre},\n\n"
        f"Te enviamos la cotizacion {venta.numero_venta} por ${total:,}.\n\n"
        f"Puedes revisarla aqui:\n{share_url}\n\n"
        f"Saludos,\n{empresa_nombre}"
    )

    return {
        'es_cotizacion': True,
        'url': share_url,
        'email': email or '',
        'telefono': telefono or '',
        'subject': subject,
        'body': body,
    }


@login_required
@requiere_empresa
def mobile_api_save_sale(request):
    """
    API para recibir una venta desde el dispositivo móvil.
    """
    import json
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        cliente_id = data.get('cliente_id')
        vendedor_id = data.get('vendedor_id')
        forma_pago_id = data.get('forma_pago_id')
        tipo_documento_solicitado = str(data.get('tipo_documento') or 'boleta').strip().lower()
        modo_documento = str(data.get('modo_documento') or '').strip().lower()
        tipo_doc_local = str(data.get('tipo_doc') or '').strip().lower()
        tipo_documento_planeado = str(data.get('tipo_documento_planeado') or '').strip().lower()
        if 'cotizacion' in {tipo_documento_solicitado, modo_documento, tipo_doc_local, tipo_documento_planeado}:
            tipo_documento_solicitado = 'cotizacion'
        total_movil = Decimal(str(data.get('total', 0)))
        fecha_movil = data.get('fecha') # Fecha enviada desde el móvil
        device_id = data.get('deviceId')
        telefono_venta = normalizar_telefono_cl(data.get('telefono') or '')
        auth_token = str(data.get('authToken') or '').strip()
        local_id = str(data.get('localId', '')).strip()
        comentario_cierre = (data.get('comentario_cierre') or '').strip()
        cliente_rut = data.get('cliente_rut')
        cliente_nombre_movil = data.get('cliente_nombre', '').strip()
        
        vendedor_por_tel = None
        if telefono_venta:
            vendedor_por_tel = Vendedor.objects.filter(
                empresa=request.empresa,
                telefono_app=telefono_venta,
                activo=True,
                app_movil_activa=True,
            ).first()
            token_ok = bool(
                vendedor_por_tel
                and verificar_token_app(auth_token, request.empresa.id, vendedor_por_tel.id, telefono_venta)
            )
            if not token_ok:
                return JsonResponse({
                    'success': False,
                    'error': 'CELULAR NO AUTORIZADO. Debe activarse en Vendedores con internet.',
                }, status=403)
        else:
            from .models import DispositivoMovil
            dispositivo = DispositivoMovil.objects.filter(
                empresa=request.empresa, unique_id=device_id, autorizado=True
            ).first()
            if not dispositivo:
                return JsonResponse({
                    'success': False,
                    'error': 'DISPOSITIVO NO AUTORIZADO. Contacte al administrador.',
                }, status=403)

        if local_id:
            marca_local = f"[MOVIL-ID:{local_id}]"
            venta_existente = Venta.objects.filter(
                empresa=request.empresa,
                observaciones__icontains=marca_local
            ).first()
            if venta_existente:
                share = _mobile_cotizacion_share_payload(request, venta_existente)
                return JsonResponse({
                    'success': True,
                    'venta_id': venta_existente.id,
                    'numero': venta_existente.numero_venta,
                    'tipo_documento': venta_existente.tipo_documento,
                    'share': share,
                    'message': 'Documento ya recibido previamente'
                })

        vendedor = None
        if vendedor_id and str(vendedor_id).isdigit():
            vendedor = Vendedor.objects.filter(id=vendedor_id, empresa=request.empresa).first()
        if not vendedor and vendedor_por_tel:
            vendedor = vendedor_por_tel
        
        # 1. Buscar objetos relacionados
        cliente = None
        if cliente_id:
            try:
                # Si el ID es numérico, buscar por ID
                if str(cliente_id).isdigit():
                    cliente = Cliente.objects.filter(id=cliente_id, empresa=request.empresa).first()
            except:
                pass
        
        # Fallback: Buscar por RUT si aún no tenemos cliente
        if not cliente and cliente_rut:
            try:
                # Normalizar RUT (quitar puntos, guiones y espacios)
                rut_busqueda = cliente_rut.replace('.', '').replace('-', '').replace(' ', '').upper()
                
                # Búsqueda optimizada: Primero exacta
                cliente = Cliente.objects.filter(rut=cliente_rut, empresa=request.empresa).first()
                
                if not cliente:
                    # Búsqueda manual tolerante a formatos
                    cands = Cliente.objects.filter(empresa=request.empresa).exclude(rut__isnull=True)
                    for cand in cands:
                        if cand.rut.replace('.', '').replace('-', '').replace(' ', '').upper() == rut_busqueda:
                            cliente = cand
                            break
                
                # ULTIMO RECURSO: ¡CREAR EL CLIENTE SI NO EXISTE!
                if not cliente and cliente_nombre_movil and len(rut_busqueda) > 5:
                    try:
                        cliente = Cliente.objects.create(
                            empresa=request.empresa,
                            nombre=cliente_nombre_movil,
                            rut=cliente_rut, # Usar el RUT enviado tal cual
                            vendedor=vendedor,
                            estado='activo',
                            giro='CLIENTE MOVIL'
                        )
                        print(f"[DEBUG-SAVE-SALE] Cliente Autocreado por Fallback: {cliente.nombre} (ID: {cliente.id})")
                    except Exception as e_create:
                        print(f"[DEBUG-SAVE-SALE] Error autocreando cliente: {e_create}")

            except Exception as e_rut:
                print(f"[DEBUG-SAVE-SALE] Error en fallback de RUT: {e_rut}")

        if cliente_id and not cliente:
             print(f"[ERROR-SAVE-SALE] Se envió ClienteID {cliente_id} (RUT: {cliente_rut}) pero NO SE ENCONTRÓ en DB.")

        forma_pago = None
        if forma_pago_id and str(forma_pago_id).isdigit():
            forma_pago = FormaPago.objects.filter(id=forma_pago_id, empresa=request.empresa).first()

        # 1.5 Validaciones base
        if not items:
            return JsonResponse({'success': False, 'error': 'Debe enviar al menos un articulo.'}, status=400)

        permite_sin_stock = request.empresa.venta_movil_permite_sin_stock
        articulos_cache = {}
        for item in items:
            articulo = Articulo.objects.get(id=item['id'], empresa=request.empresa)
            articulos_cache[item['id']] = articulo
            cantidad = Decimal(str(item.get('cantidad', 0)))
            if cantidad <= 0:
                return JsonResponse({'success': False, 'error': f"Cantidad invalida para {articulo.nombre}."}, status=400)
            if articulo.control_stock and not permite_sin_stock and Decimal(str(articulo.stock_actual)) < cantidad:
                return JsonResponse({
                    'success': False,
                    'error': f"Stock insuficiente para {articulo.nombre}. Disponible: {articulo.stock_actual}"
                }, status=400)
        
        # 2. Generar correlativo temporal de preventa
        from .models import EstacionTrabajo
        # Usamos una estación genérica para ventas móviles o la primera que encontremos
        estacion = EstacionTrabajo.objects.filter(empresa=request.empresa, activo=True).first()
        numero_ticket = 0
        if estacion:
            numero_ticket = estacion.incrementar_correlativo_ticket()
        else:
            # Fallback si no hay estación
            numero_ticket = Venta.objects.filter(empresa=request.empresa).count() + 1
            
        numero_vale = f"M{numero_ticket:05d}"
        
        # 3. Crear la Venta (como TICKET / COTIZACION según corresponda)
        # Determinar tipo real de documento en el sistema
        tipo_final = 'ticket' # Por defecto preventa facturable
        estado_cot = None
        
        if tipo_documento_solicitado == 'cotizacion':
            tipo_final = 'cotizacion'
            estado_cot = 'pendiente'

        # Intentar usar la fecha del móvil si es válida, sino usar hoy
        fecha_final = timezone.localdate()
        if fecha_movil:
            try:
                # El móvil envía ISO string completo o solo fecha
                from django.utils.dateparse import parse_datetime, parse_date
                parsed_dt = parse_datetime(fecha_movil)
                if parsed_dt:
                    fecha_final = parsed_dt.date()
                else:
                    parsed_d = parse_date(fecha_movil)
                    if parsed_d:
                        fecha_final = parsed_d
            except:
                pass

        observaciones_lineas = []
        if cliente_nombre_movil:
            observaciones_lineas.append(f"[MOVIL] Cliente: {cliente_nombre_movil}")
        observaciones_lineas.append(f"[MOVIL] Doc Solicitado: {tipo_documento_solicitado}")
        observaciones_lineas.append(f"[MOVIL] Recibido: {timezone.localtime(timezone.now()).strftime('%d-%m-%Y %H:%M')}")
        if local_id:
            observaciones_lineas.append(f"[MOVIL-ID:{local_id}]")
        if comentario_cierre:
            observaciones_lineas.append(f"[CIERRE] {comentario_cierre}")

        venta = Venta.objects.create(
            empresa=request.empresa,
            numero_venta=numero_vale,
            fecha=fecha_final,
            cliente=cliente,
            vendedor=vendedor,
            forma_pago=forma_pago,
            estacion_trabajo=estacion,
            tipo_documento=tipo_final,
            tipo_documento_planeado=tipo_documento_solicitado,
            total=total_movil,
            estado='confirmada',
            estado_cotizacion=estado_cot,
            facturado=False,
            usuario_creacion=request.user,
            observaciones="\n".join(observaciones_lineas)
        )
        
        # 4. Crear Detalles
        for item in items:
            VentaDetalle.objects.create(
                venta=venta,
                articulo=articulos_cache[item['id']],
                cantidad=Decimal(str(item['cantidad'])),
                precio_unitario=Decimal(str(item['precio'])),
                precio_total=Decimal(str(item['total'])),
                comentario=(item.get('comentario') or '').strip()
            )
            
        # Recalcular totales para asegurar consistencia
        venta.calcular_totales()
        
        share = _mobile_cotizacion_share_payload(request, venta)
        return JsonResponse({
            'success': True,
            'venta_id': venta.id,
            'numero': numero_vale,
            'tipo_documento': venta.tipo_documento,
            'share': share,
            'message': 'Venta recibida correctamente como Preventa Móvil'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@requiere_empresa
def mobile_api_sales_history(request):
    """
    API para obtener el historial de ventas de un vendedor en un periodo.
    """
    vendedor_id = request.GET.get('vendedor_id')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    if not vendedor_id:
        return JsonResponse({'success': False, 'error': 'Vendedor ID requerido'}, status=400)
        
    try:
        from django.utils.dateparse import parse_date
        from datetime import date, timedelta
        
        # Por defecto hoy
        hoy = timezone.localdate()
        date_inicio = parse_date(fecha_inicio) if fecha_inicio else hoy
        date_fin = parse_date(fecha_fin) if fecha_fin else hoy
        
        # Filtrar ventas de la empresa y del vendedor logeado.
        ventas_qs = Venta.objects.filter(
            empresa=request.empresa,
            vendedor_id=vendedor_id,
            fecha__range=[date_inicio, date_fin]
        ).select_related('cliente')

        print(f"[DEBUG-MOBILE-HISTORY] Vendedor: {vendedor_id}, Rango: {date_inicio} - {date_fin}, Encontradas: {ventas_qs.count()}")
        
        ventas = ventas_qs.order_by('-fecha_creacion', '-id')[:200]
        
        ventas_data = []
        for v in ventas:
            cliente_name = v.get_cliente_nombre()
            share = _mobile_cotizacion_share_payload(request, v)
            
            # Intentar obtener info de la venta final si ya fue procesada
            proceso = v.venta_preventa.first() if v.facturado else None
            doc_final = None
            if proceso:
                doc_final = f"{proceso.venta_final.get_tipo_documento_display().upper()} {proceso.venta_final.numero_venta}"
                    
            ventas_data.append({
                'id': v.id,
                'numero': v.numero_venta,
                'fecha': v.fecha_creacion.isoformat(),
                'total': int(v.total),
                'cliente': cliente_name,
                'tipo_doc': v.tipo_documento_planeado or v.tipo_documento,
                'estado': v.estado,
                'facturado': v.facturado,
                'doc_final': doc_final,
                'share': share
            })
            
        return JsonResponse({
            'success': True,
            'ventas': ventas_data,
            'count': len(ventas_data),
            'vendedor_id': vendedor_id,
            'periodo': {
                'inicio': date_inicio.isoformat(),
                'fin': date_fin.isoformat()
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@requiere_empresa
def mobile_api_register_location(request):
    """
    API para recibir la ubicación de un vendedor.
    """
    import json
    from decimal import Decimal
    from .models import Vendedor, VendedorUbicacion
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        vendedor_id = data.get('vendedor_id')
        lat = data.get('lat')
        lng = data.get('lng')
        
        if not vendedor_id or lat is None or lng is None:
            return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)
            
        vendedor = get_object_or_404(Vendedor, id=vendedor_id, empresa=request.empresa)
        
        VendedorUbicacion.objects.create(
            empresa=request.empresa,
            vendedor=vendedor,
            latitud=Decimal(str(lat)),
            longitud=Decimal(str(lng))
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        print(f"Error registrando ubicación: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@requiere_empresa
def ventas_mapa_vendedores(request):
    """
    Vista web para ver la ubicación de los vendedores en un mapa.
    """
    from django.db.models import OuterRef, Subquery
    from .models import Vendedor, VendedorUbicacion
    
    # Obtener la última ubicación registrada de cada vendedor activo de la empresa
    ultima_ubicacion = VendedorUbicacion.objects.filter(
        vendedor=OuterRef('pk')
    ).order_by('-fecha_registro')
    
    vendedores_con_ubicacion = Vendedor.objects.filter(
        empresa=request.empresa, 
        activo=True
    ).annotate(
        lat=Subquery(ultima_ubicacion.values('latitud')[:1]),
        lng=Subquery(ultima_ubicacion.values('longitud')[:1]),
        fecha_pos=Subquery(ultima_ubicacion.values('fecha_registro')[:1])
    ).filter(lat__isnull=False)
    
    context = {
        'vendedores': vendedores_con_ubicacion,
    }
    return render(request, 'ventas/mapa_vendedores.html', context)
@login_required
@requiere_empresa
def mobile_api_cliente_historial(request):
    """
    API para obtener el historial de ventas de un cliente específico.
    """
    cliente_id = request.GET.get('cliente_id')
    if not cliente_id:
        return JsonResponse({'success': False, 'error': 'Cliente ID requerido'}, status=400)
    
    try:
        ventas = Venta.objects.filter(
            empresa=request.empresa,
            cliente_id=cliente_id
        ).order_by('-fecha_creacion')[:20]
        
        historial = []
        for v in ventas:
            historial.append({
                'id': v.id,
                'numero': v.numero_venta,
                'fecha': v.fecha_creacion.isoformat(),
                'total': int(v.total),
                'tipo_doc': v.tipo_documento_planeado or v.tipo_documento,
                'estado': v.estado
            })
            
        return JsonResponse({
            'success': True,
            'historial': historial
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@requiere_empresa
def libro_ventas_excel(request):
    """Exporta el Libro de Ventas: detalle del período, subtotales por tipo y total general."""
    from collections import defaultdict
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from core.excel_utils import (
        build_excel_response,
        format_excel_date,
        set_column_widths,
        setup_corporate_sheet,
        style_data_row,
        write_table_headers,
    )
    from facturacion_electronica.models import DocumentoTributarioElectronico
    import re

    fecha_desde, fecha_hasta, f_desde, f_hasta = _rango_fechas_libro(request)
    tipo_documento = request.GET.get('tipo_documento', '')
    cliente_id = (request.GET.get('cliente') or '').strip()
    vendedor_id = request.GET.get('vendedor', '')
    forma_pago_id = request.GET.get('forma_pago', '')
    search = (request.GET.get('search') or '').strip()

    q_ventas_periodo, q_dtes_periodo = _q_periodo_libro(f_desde, f_hasta)

    ventas = Venta.objects.filter(
        empresa=request.empresa,
        estado='confirmada',
        tipo_documento__in=['boleta', 'factura', 'factura_electronica'],
        dte__isnull=True,
    ).filter(q_ventas_periodo).exclude(
        Q(numero_venta__icontains='test') |
        Q(tipo_documento__in=['cotizacion', 'guia', 'vale', 'ticket'])
    ).select_related('cliente', 'vendedor', 'forma_pago', 'sucursal')

    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa,
    ).filter(q_dtes_periodo).exclude(
        Q(folio__icontains='test') | Q(tipo_dte='52')
    ).select_related('venta', 'venta__cliente', 'venta__vendedor', 'venta__sucursal')

    if tipo_documento:
        if tipo_documento == '33':
            dtes = dtes.filter(tipo_dte='33')
            ventas = ventas.filter(tipo_documento__in=['factura', 'factura_electronica'])
        elif tipo_documento == '34':
            dtes = dtes.filter(tipo_dte='34')
            ventas = ventas.filter(tipo_documento='factura_exenta')
        elif tipo_documento == '39':
            dtes = dtes.filter(tipo_dte='39')
            ventas = ventas.filter(tipo_documento='boleta')
        elif tipo_documento == '41':
            dtes = dtes.filter(tipo_dte='41')
            ventas = ventas.filter(tipo_documento='boleta_exenta')
        elif tipo_documento == '52':
            dtes = dtes.filter(tipo_dte='52')
            ventas = ventas.filter(tipo_documento='guia')
        elif tipo_documento in ['56', '61']:
            dtes = dtes.filter(tipo_dte=tipo_documento)
            ventas = ventas.none()
        elif tipo_documento in ['factura', 'factura_electronica']:
            ventas = ventas.filter(tipo_documento__in=['factura', 'factura_electronica'])
            dtes = dtes.filter(tipo_dte='33')
        elif tipo_documento == 'boleta':
            ventas = ventas.filter(tipo_documento='boleta')
            dtes = dtes.filter(tipo_dte='39')
        else:
            ventas = ventas.filter(tipo_documento=tipo_documento)
            dtes = dtes.none()

    if cliente_id:
        ventas = ventas.filter(
            Q(cliente__nombre__icontains=cliente_id) |
            Q(cliente__rut__icontains=cliente_id)
        )
        dtes = dtes.filter(
            Q(venta__cliente__nombre__icontains=cliente_id) |
            Q(venta__cliente__rut__icontains=cliente_id) |
            Q(razon_social_receptor__icontains=cliente_id) |
            Q(rut_receptor__icontains=cliente_id)
        )

    if vendedor_id:
        ventas = ventas.filter(vendedor_id=vendedor_id)
        dtes = dtes.filter(venta__vendedor_id=vendedor_id)

    if forma_pago_id:
        ventas = ventas.filter(forma_pago_id=forma_pago_id)
        dtes = dtes.filter(venta__forma_pago_id=forma_pago_id)

    if search:
        ventas = ventas.filter(
            Q(numero_venta__icontains=search) |
            Q(cliente__nombre__icontains=search) |
            Q(cliente__rut__icontains=search)
        )
        dtes = dtes.filter(
            Q(folio__icontains=search) |
            Q(razon_social_receptor__icontains=search) |
            Q(rut_receptor__icontains=search)
        )

    nombres_tipo = {
        '33': 'FACTURAS ELECTRÓNICAS (33)',
        '34': 'FACTURAS EXENTAS ELECTRÓNICAS (34)',
        '39': 'BOLETAS ELECTRÓNICAS (39)',
        '41': 'BOLETAS EXENTAS ELECTRÓNICAS (41)',
        '56': 'NOTAS DE DÉBITO ELECTRÓNICAS (56)',
        '61': 'NOTAS DE CRÉDITO ELECTRÓNICAS (61)',
        'factura': 'FACTURAS POS',
        'boleta': 'BOLETAS POS',
        '99': 'OTROS DOCUMENTOS',
    }
    orden_tipos = ['39', '41', '33', '34', '56', '61', 'boleta', 'factura', '99']

    def _folio_num(val):
        try:
            return int(re.sub(r'\D', '', str(val or '')) or 0)
        except (TypeError, ValueError):
            return 0

    def _estado_dte(dte):
        try:
            return (dte.get_estado_sii_real_display() or 'GENERADO').upper()
        except Exception:
            return str(getattr(dte, 'estado_sii', None) or 'GENERADO').upper()

    documentos = []
    for v in ventas:
        documentos.append({
            'tipo_key': v.tipo_documento or '99',
            'fecha': v.fecha,
            'tipo': v.get_tipo_documento_display(),
            'folio': v.numero_venta,
            'rut': v.cliente.rut if v.cliente else '-',
            'nombre': v.cliente.nombre if v.cliente else 'Cliente General',
            'neto': v.neto or 0,
            'iva': v.iva or 0,
            'total': v.total or 0,
            'estado': (v.estado or '').upper(),
            'vendedor': v.vendedor.nombre if v.vendedor else 'Sin asignar',
            'vendedor_cod': v.vendedor.codigo if v.vendedor else '-',
            'sucursal': v.sucursal.nombre if v.sucursal else 'Casa Matriz',
        })

    for d in dtes:
        factor = -1 if d.tipo_dte == '61' else 1
        documentos.append({
            'tipo_key': d.tipo_dte or '99',
            'fecha': _fecha_documento_libro(d, es_dte=True),
            'tipo': d.get_tipo_dte_display(),
            'folio': d.folio or '-',
            'rut': d.rut_receptor or '-',
            'nombre': d.razon_social_receptor or 'Cliente General',
            'neto': (d.monto_neto or 0) * factor,
            'iva': (d.monto_iva or 0) * factor,
            'total': (d.monto_total or 0) * factor,
            'estado': _estado_dte(d),
            'vendedor': (d.venta.vendedor.nombre if d.venta and d.venta.vendedor else 'Sin asignar'),
            'vendedor_cod': (d.venta.vendedor.codigo if d.venta and d.venta.vendedor else '-'),
            'sucursal': (d.venta.sucursal.nombre if d.venta and d.venta.sucursal else 'Casa Matriz'),
        })

    grupos = defaultdict(list)
    for doc in documentos:
        grupos[doc['tipo_key']].append(doc)
    for docs_grupo in grupos.values():
        docs_grupo.sort(key=lambda x: (x['fecha'] or datetime.min.date(), _folio_num(x['folio'])), reverse=True)

    keys = [k for k in orden_tipos if k in grupos]
    keys += [k for k in grupos.keys() if k not in orden_tipos]

    wb = Workbook()
    ws = wb.active
    ws.title = "Libro de Ventas"
    headers = [
        "FECHA", "TIPO DOCTO", "FOLIO", "RUT CLIENTE", "CLIENTE / RAZÓN SOCIAL",
        "NETO", "IVA", "TOTAL", "ESTADO SII", "VENDEDOR", "COD. VENDEDOR", "SUCURSAL",
    ]
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "LIBRO DE VENTAS",
        f"Período: {format_excel_date(f_desde)} al {format_excel_date(f_hasta)}  ·  {len(documentos)} documento(s)",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    fill_grupo = PatternFill(start_color="E8DCC8", end_color="E8DCC8", fill_type="solid")
    fill_sub = PatternFill(start_color="D7CCC8", end_color="D7CCC8", fill_type="solid")
    fill_total = PatternFill(start_color="6F5B44", end_color="6F5B44", fill_type="solid")
    font_grupo = Font(bold=True, color="5D4037", size=10)
    font_sub = Font(bold=True, color="5D4037", size=10)
    font_total = Font(bold=True, color="FFFFFF", size=11)

    def _write_montos(row, neto, iva, total, font, fill):
        for col, valor in ((6, neto), (7, iva), (8, total)):
            cell = ws.cell(row=row, column=col, value=float(valor or 0))
            cell.number_format = '#,##0'
            cell.alignment = styles["right"]
            cell.font = font
            if fill:
                cell.fill = fill

    current_row = branding["data_row"]
    total_neto = Decimal('0')
    total_iva = Decimal('0')
    total_gral = Decimal('0')

    for key in keys:
        docs_grupo = grupos[key]
        cant = len(docs_grupo)
        sub_neto = sum(Decimal(str(d['neto'] or 0)) for d in docs_grupo)
        sub_iva = sum(Decimal(str(d['iva'] or 0)) for d in docs_grupo)
        sub_total = sum(Decimal(str(d['total'] or 0)) for d in docs_grupo)
        total_neto += sub_neto
        total_iva += sub_iva
        total_gral += sub_total

        nombre = nombres_tipo.get(key, (docs_grupo[0]['tipo'] if docs_grupo else key)).upper()
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=5)
        cell_g = ws.cell(row=current_row, column=1, value=f"{nombre}  ·  {cant} documento(s)")
        cell_g.font = font_grupo
        cell_g.alignment = styles["left"]
        for col in range(1, len(headers) + 1):
            c = ws.cell(row=current_row, column=col)
            c.fill = fill_grupo
            c.border = styles["border"]
        _write_montos(current_row, sub_neto, sub_iva, sub_total, font_grupo, fill_grupo)
        current_row += 1

        for idx, doc in enumerate(docs_grupo):
            ws.cell(row=current_row, column=1, value=format_excel_date(doc['fecha'])).alignment = styles["center"]
            ws.cell(row=current_row, column=2, value=str(doc['tipo'] or '').upper())
            ws.cell(row=current_row, column=3, value=doc['folio']).alignment = styles["center"]
            ws.cell(row=current_row, column=4, value=doc['rut']).alignment = styles["center"]
            ws.cell(row=current_row, column=5, value=str(doc['nombre'] or '').upper())
            _write_montos(current_row, doc['neto'], doc['iva'], doc['total'], styles["data_font"], None)
            ws.cell(row=current_row, column=9, value=doc['estado']).alignment = styles["center"]
            ws.cell(row=current_row, column=10, value=str(doc['vendedor'] or '').upper())
            ws.cell(row=current_row, column=11, value=doc['vendedor_cod']).alignment = styles["center"]
            ws.cell(row=current_row, column=12, value=str(doc['sucursal'] or '').upper())
            style_data_row(ws, current_row, len(headers), styles, zebra=(idx % 2 == 1))
            current_row += 1

        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=5)
        cell_s = ws.cell(row=current_row, column=1, value=f"SUBTOTAL {nombre}")
        cell_s.font = font_sub
        cell_s.alignment = styles["right"]
        for col in range(1, len(headers) + 1):
            c = ws.cell(row=current_row, column=col)
            c.fill = fill_sub
            c.border = styles["border"]
            c.font = font_sub
        _write_montos(current_row, sub_neto, sub_iva, sub_total, font_sub, fill_sub)
        current_row += 2

    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=5)
    cell_t = ws.cell(
        row=current_row,
        column=1,
        value=f"TOTAL GENERAL DEL PERÍODO  ·  {len(documentos)} documento(s)  ·  {format_excel_date(f_desde)} al {format_excel_date(f_hasta)}",
    )
    cell_t.font = font_total
    cell_t.alignment = styles["left"]
    for col in range(1, len(headers) + 1):
        c = ws.cell(row=current_row, column=col)
        c.fill = fill_total
        c.border = styles["border"]
        c.font = font_total
    _write_montos(current_row, total_neto, total_iva, total_gral, font_total, fill_total)

    empresa_nom = (getattr(request.empresa, 'nombre', None) or 'empresa').replace(' ', '_')
    filename = f"LibroVentas_{empresa_nom}_{f_desde.strftime('%Y%m%d')}_{f_hasta.strftime('%Y%m%d')}.xlsx"
    set_column_widths(ws, [12, 28, 10, 15, 45, 14, 14, 14, 15, 25, 15, 20])
    return build_excel_response(wb, filename)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def libro_guias(request):
    """
    Libro de Guías - Listado exclusivo de Guías de Despacho (tipo 52)
    por empresa y sucursal operativa.
    """
    import calendar
    import re
    from decimal import Decimal as _Dec
    from facturacion_electronica.models import DocumentoTributarioElectronico
    from empresas.middleware import resolver_sucursal_operativa

    fecha_desde, fecha_hasta, f_desde, f_hasta = _rango_fechas_libro(request)
    cliente_id = request.GET.get('cliente', '').strip()
    vendedor_id = request.GET.get('vendedor', '')
    search = request.GET.get('search', '')
    sucursal_activa = resolver_sucursal_operativa(request)

    ventas = Venta.objects.filter(
        empresa=request.empresa,
        estado='confirmada',
        tipo_documento='guia',
        dte__isnull=True
    ).exclude(numero_venta__icontains='test').select_related(
        'cliente', 'vendedor', 'sucursal', 'estacion_trabajo'
    )

    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa,
        tipo_dte='52'
    ).select_related(
        'venta', 'venta__cliente', 'venta__vendedor', 'venta__sucursal',
        'vendedor', 'caf_utilizado', 'caf_utilizado__sucursal'
    ).prefetch_related(
        Prefetch('transferencias', queryset=TransferenciaInventario.objects.only('id'))
    ).defer(
        'xml_dte', 'xml_firmado', 'timbre_electronico', 'timbre_pdf417',
        'respuesta_sii', 'datos_pdf417'
    )

    if sucursal_activa:
        ventas = ventas.filter(Q(sucursal=sucursal_activa) | Q(sucursal__isnull=True))
        dtes = dtes.filter(
            Q(venta__sucursal=sucursal_activa) |
            Q(caf_utilizado__sucursal=sucursal_activa) |
            Q(venta__sucursal__isnull=True, caf_utilizado__sucursal__isnull=True)
        )

    ventas = ventas.filter(fecha__gte=f_desde, fecha__lte=f_hasta)
    dtes = dtes.filter(
        Q(fecha_emision__gte=f_desde, fecha_emision__lte=f_hasta) |
        (Q(fecha_emision__isnull=True) & Q(fecha__gte=f_desde, fecha__lte=f_hasta))
    )

    if cliente_id:
        ventas = ventas.filter(
            Q(cliente__nombre__icontains=cliente_id) |
            Q(cliente__rut__icontains=cliente_id)
        )
        dtes = dtes.filter(
            Q(venta__cliente__nombre__icontains=cliente_id) |
            Q(venta__cliente__rut__icontains=cliente_id) |
            Q(razon_social_receptor__icontains=cliente_id) |
            Q(rut_receptor__icontains=cliente_id)
        )

    if vendedor_id:
        ventas = ventas.filter(vendedor_id=vendedor_id)
        dtes = dtes.filter(Q(vendedor_id=vendedor_id) | Q(venta__vendedor_id=vendedor_id))

    if search:
        ventas = ventas.filter(Q(numero_venta__icontains=search) | Q(cliente__nombre__icontains=search))
        dte_q = Q(razon_social_receptor__icontains=search) | Q(rut_receptor__icontains=search)
        if str(search).isdigit():
            dte_q |= Q(folio=int(search))
        dtes = dtes.filter(dte_q)

    documentos = []
    for v in ventas:
        v.fecha_documento = v.fecha
        v.es_dte = False
        v.sort_tipo = '52'
        try:
            v.sort_folio = int(re.sub(r'\D', '', str(v.numero_venta)))
        except (TypeError, ValueError):
            v.sort_folio = 0
        v.sucursal_nombre = v.sucursal.nombre if v.sucursal else 'Sin sucursal'
        documentos.append(v)

    dtes_list = list(dtes)
    for d in dtes_list:
        if str(getattr(d, 'estado_sii', '') or '').strip().lower() in {'rechazado', 'error_envio', 'error'}:
            try:
                d.corregir_falso_rechazo_espera()
            except Exception:
                pass
        d.fecha_documento = d.fecha_emision or d.fecha
        d.es_dte = True
        d.sort_tipo = '52'
        try:
            d.sort_folio = int(d.folio)
        except (TypeError, ValueError):
            d.sort_folio = 0
        transferencias_prefetch = list(getattr(d, '_prefetched_objects_cache', {}).get('transferencias', []))
        d.transferencia_pk = transferencias_prefetch[0].pk if transferencias_prefetch else None
        if d.venta and d.venta.sucursal:
            d.sucursal_nombre = d.venta.sucursal.nombre
        elif d.caf_utilizado and d.caf_utilizado.sucursal:
            d.sucursal_nombre = d.caf_utilizado.sucursal.nombre
        else:
            d.sucursal_nombre = 'Sin sucursal'
        d.vendedor_nombre = (
            d.vendedor.nombre if d.vendedor_id and d.vendedor
            else (d.venta.vendedor.nombre if d.venta and d.venta.vendedor else '-')
        )
        documentos.append(d)

    guias_sin_track = sum(1 for d in dtes_list if d.puede_enviarse_al_sii)
    guias_por_consultar = sum(1 for d in dtes_list if d.requiere_consulta_estado_sii())

    documentos.sort(key=lambda doc: (doc.fecha_documento or hoy, doc.sort_folio), reverse=True)

    dtes_pendientes_sii = [
        d for d in documentos
        if getattr(d, 'es_dte', False) and d.requiere_consulta_estado_sii()
    ]
    if dtes_pendientes_sii:
        DocumentoTributarioElectronico.refrescar_estados_visibles(dtes_pendientes_sii, limit=8)

    total_general = _Dec('0')
    for doc in documentos:
        if getattr(doc, 'es_dte', False):
            total_general += _Dec(str(doc.monto_total or 0))
        else:
            total_general += _Dec(str(doc.total or 0))

    paginator = Paginator(documentos, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'cliente_id': cliente_id,
        'vendedor_id': vendedor_id,
        'search': search,
        'vendedores': Vendedor.objects.filter(empresa=request.empresa, activo=True),
        'sucursal_activa': sucursal_activa,
        'guias_sin_track': guias_sin_track,
        'guias_por_consultar': guias_por_consultar,
        'estadisticas': {
            'total_documentos': len(documentos),
            'total_general': total_general,
        },
    }

    return render(request, 'ventas/libro_guias.html', context)


@login_required
@requiere_empresa
@permission_required('ventas.view_venta', raise_exception=True)
def libro_guias_excel(request):
    """
    Exporta el Libro de Guías a Excel
    """
    import calendar
    from facturacion_electronica.models import DocumentoTributarioElectronico
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from core.excel_utils import (
        build_excel_response,
        finalize_excel_table,
        format_excel_date,
        set_column_widths,
        setup_corporate_sheet,
        style_data_row,
        write_table_headers,
    )
    from empresas.middleware import resolver_sucursal_operativa

    fecha_desde, fecha_hasta, f_desde, f_hasta = _rango_fechas_libro(request)
    sucursal_activa = resolver_sucursal_operativa(request)

    ventas = Venta.objects.filter(
        empresa=request.empresa,
        estado='confirmada',
        tipo_documento='guia',
        dte__isnull=True
    ).select_related('cliente', 'vendedor', 'sucursal')
    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa,
        tipo_dte='52'
    ).select_related(
        'venta', 'venta__cliente', 'venta__vendedor', 'venta__sucursal',
        'vendedor', 'caf_utilizado', 'caf_utilizado__sucursal'
    )

    if sucursal_activa:
        ventas = ventas.filter(Q(sucursal=sucursal_activa) | Q(sucursal__isnull=True))
        dtes = dtes.filter(
            Q(venta__sucursal=sucursal_activa) |
            Q(caf_utilizado__sucursal=sucursal_activa) |
            Q(venta__sucursal__isnull=True, caf_utilizado__sucursal__isnull=True)
        )

    ventas = ventas.filter(fecha__gte=f_desde, fecha__lte=f_hasta)
    dtes = dtes.filter(
        Q(fecha_emision__gte=f_desde, fecha_emision__lte=f_hasta) |
        (Q(fecha_emision__isnull=True) & Q(fecha__gte=f_desde, fecha__lte=f_hasta))
    )

    documentos = []
    for v in ventas:
        documentos.append({
            'fecha': v.fecha, 'tipo': 'GUÍA DESPACHO', 'folio': v.numero_venta,
            'rut': v.cliente.rut if v.cliente else '-', 'nombre': v.cliente.nombre if v.cliente else 'CLIENTE GENERAL',
            'neto': v.subtotal or 0, 'iva': v.iva or 0, 'total': v.total or 0, 'estado': v.estado.upper(),
            'vendedor': v.vendedor.nombre if v.vendedor else 'SIN ASIGNAR', 'vendedor_cod': v.vendedor.codigo if v.vendedor else '-',
            'sucursal': v.sucursal.nombre if v.sucursal else 'CASA MATRIZ'
        })
    for d in dtes:
        if d.venta and d.venta.sucursal:
            suc_nombre = d.venta.sucursal.nombre
        elif d.caf_utilizado and d.caf_utilizado.sucursal:
            suc_nombre = d.caf_utilizado.sucursal.nombre
        else:
            suc_nombre = 'CASA MATRIZ'
        vendedor_obj = d.vendedor or (d.venta.vendedor if d.venta else None)
        documentos.append({
            'fecha': d.fecha_emision, 'tipo': 'GUÍA DESPACHO ELECTRÓNICA', 'folio': d.folio or '-',
            'rut': d.rut_receptor or '-', 'nombre': d.razon_social_receptor or 'CLIENTE GENERAL',
            'neto': d.monto_neto or 0, 'iva': d.monto_iva or 0, 'total': d.monto_total or 0,
            'estado': (d.get_estado_sii_real_display() or 'GENERADO').upper(),
            'vendedor': vendedor_obj.nombre if vendedor_obj else 'SIN ASIGNAR',
            'vendedor_cod': vendedor_obj.codigo if vendedor_obj else '-',
            'sucursal': suc_nombre
        })
    
    documentos.sort(key=lambda x: (x['fecha'] or hoy), reverse=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Libro de Guías"
    headers = ["FECHA", "TIPO DOCTO", "FOLIO", "RUT CLIENTE", "CLIENTE / RAZÓN SOCIAL", "NETO", "IVA", "TOTAL", "ESTADO", "VENDEDOR", "COD. VENDEDOR", "SUCURSAL"]
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "LIBRO DE GUIAS DE DESPACHO",
        f"Periodo: {format_excel_date(f_desde) if 'f_desde' in locals() else fecha_desde} al {format_excel_date(f_hasta) if 'f_hasta' in locals() else fecha_hasta}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row_idx = branding["data_row"]
    for doc in documentos:
        ws.cell(row=row_idx, column=1, value=format_excel_date(doc['fecha'])).alignment = styles["center"]
        ws.cell(row=row_idx, column=2, value=doc['tipo'])
        ws.cell(row=row_idx, column=3, value=doc['folio']).alignment = styles["center"]
        ws.cell(row=row_idx, column=4, value=doc['rut']).alignment = styles["center"]
        ws.cell(row=row_idx, column=5, value=doc['nombre'].upper())
        ws.cell(row=row_idx, column=6, value=float(doc['neto'])).alignment = styles["right"]
        ws.cell(row=row_idx, column=6).number_format = '#,##0'
        ws.cell(row=row_idx, column=7, value=float(doc['iva'])).alignment = styles["right"]
        ws.cell(row=row_idx, column=7).number_format = '#,##0'
        ws.cell(row=row_idx, column=8, value=float(doc['total'])).alignment = styles["right"]
        ws.cell(row=row_idx, column=8).number_format = '#,##0'
        ws.cell(row=row_idx, column=9, value=doc['estado']).alignment = styles["center"]
        ws.cell(row=row_idx, column=10, value=doc['vendedor'].upper())
        ws.cell(row=row_idx, column=11, value=doc['vendedor_cod']).alignment = styles["center"]
        ws.cell(row=row_idx, column=12, value=doc['sucursal'].upper())
        style_data_row(ws, row_idx, len(headers), styles, zebra=((row_idx - branding["data_row"]) % 2 == 1))
        row_idx += 1
    
    # Fila de Totales
    ws.cell(row=row_idx+1, column=5, value="TOTALES GENERALES:").font = Font(bold=True)
    ws.cell(row=row_idx+1, column=5).alignment = styles["right"]
    
    for col_idx, col_let in enumerate(['F', 'G', 'H'], 6):
        formula = f"=SUM({col_let}{branding['data_row']}:{col_let}{row_idx-1})"
        cell_sum = ws.cell(row=row_idx+1, column=col_idx, value=formula)
        cell_sum.font = Font(bold=True)
        cell_sum.number_format = '#,##0'
        cell_sum.alignment = styles["right"]
    style_data_row(ws, row_idx + 1, len(headers), styles)

    set_column_widths(ws, [12, 22, 10, 15, 45, 14, 14, 14, 15, 25, 15, 20])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row_idx - 1, len(headers))
    return build_excel_response(wb, f"LibroGuias_{datetime.now().strftime('%Y%m%d')}.xlsx")

# ========== FACTURACIÓN CONSOLIDADA DE GUÍAS ==========

def _decimal_from_payload(value, default='0'):
    if value is None or value == '':
        return Decimal(default)
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip().replace('$', '').replace(' ', '')
    text = text.replace('\xa0', '')
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.') if text.rfind(',') > text.rfind('.') else text.replace(',', '')
    elif ',' in text:
        partes = text.split(',')
        text = text.replace(',', '') if len(partes) == 2 and len(partes[1]) == 3 else text.replace(',', '.')
    elif '.' in text:
        partes = text.split('.')
        if len(partes) > 2:
            text = ''.join(partes)
        elif len(partes) == 2 and len(partes[1]) == 3 and len(partes[0]) <= 3:
            text = ''.join(partes)
    try:
        return Decimal(text)
    except Exception:
        return Decimal(default)


def _id_from_payload(value):
    if value is None or value == '':
        return None
    text = str(value).replace('\xa0', '').replace(' ', '').replace('.', '').strip()
    return int(text) if text.isdigit() else None


def _registrar_factura_directa_cuenta_corriente(venta, dte, monto_pagado, usuario):
    from tesoreria.services import sincronizar_venta_credito_en_tesoreria

    registrado = sincronizar_venta_credito_en_tesoreria(
        venta,
        dte=dte,
        usuario=usuario,
        descripcion=f"Factura directa DTE {dte.tipo_dte}-{dte.folio}",
    )

    if not registrado:
        return False

    try:
        saldo_pendiente = venta.total - monto_pagado
        from clientes.models import CuentaCorrienteCliente as MovimientoCliente
        existe_movimiento = MovimientoCliente.objects.filter(
            empresa=venta.empresa,
            cliente=venta.cliente,
            fecha=venta.fecha,
            tipo_movimiento='venta',
            monto=saldo_pendiente,
            descripcion=f"Factura directa folio {dte.folio}",
        ).exists()
        if not existe_movimiento:
            MovimientoCliente.objects.create(
                empresa=venta.empresa,
                cliente=venta.cliente,
                fecha=venta.fecha,
                tipo_movimiento='venta',
                monto=saldo_pendiente,
                descripcion=f"Factura directa folio {dte.folio}",
                observaciones=venta.observaciones,
                creado_por=usuario,
            )
    except Exception as exc:
        print(f"[FACTURA DIRECTA] No se pudo registrar movimiento legacy cliente: {exc}")

    return True


@login_required
@requiere_empresa
@permission_required('ventas.add_venta', raise_exception=True)
@ensure_csrf_cookie
def facturar_directo(request):
    from empresas.models import Sucursal
    from facturacion_electronica.validacion_envio import errores_emisor_para_dte

    empresa = request.empresa
    estacion_id = request.session.get('pos_estacion_id')
    estacion_activa = None
    if estacion_id:
        estacion_activa = EstacionTrabajo.objects.filter(id=estacion_id, empresa=empresa, activo=True).first()
    if not estacion_activa:
        estacion_activa = EstacionTrabajo.objects.filter(empresa=empresa, activo=True).order_by('numero').first()

    if request.method == 'POST':
        import json
        from facturacion_electronica.dte_service import DTEService
        try:
            data = json.loads(request.body.decode('utf-8') if request.body else '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Solicitud invalida.'}, status=400)

        try:
            dte_service = DTEService(empresa)
        except ValueError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=400)
        except Exception as exc:
            return JsonResponse({'success': False, 'message': f'Error al inicializar servicio DTE: {exc}'}, status=400)

        from facturacion_electronica.models import DocumentoTributarioElectronico

        reenviar_id = _id_from_payload(data.get('reenviar_dte_id') or data.get('dte_id_existente'))
        if reenviar_id:
            dte = DocumentoTributarioElectronico.objects.filter(pk=reenviar_id, empresa=empresa).first()
            if not dte:
                return JsonResponse({'success': False, 'message': 'No se encontró el DTE para reenviar.'}, status=404)
            envio = {'success': False, 'message': 'No enviado'}
            try:
                envio = dte_service.enviar_dte_al_sii(dte)
            except Exception as exc:
                envio = {'success': False, 'message': str(exc)}
            return JsonResponse({
                'success': bool(envio.get('success')),
                'reenviado': True,
                'message': (
                    f"{dte.get_tipo_dte_display()} folio {dte.folio} enviado al SII."
                    if envio.get('success')
                    else f"No se reenvió el folio {dte.folio}: {envio.get('message') or 'error de envío'}."
                ),
                'dte_id': dte.id,
                'folio': dte.folio,
                'tipo_dte': dte.tipo_dte,
                'envio': envio,
                'print_url': reverse('facturacion_electronica:ver_factura_electronica', kwargs={'dte_id': dte.id}),
            }, status=200 if envio.get('success') else 400)

        tipo_dte = data.get('tipo_dte') or '33'
        tipos_dte_permitidos = ['33', '34', '39', '41', '52']
        etiquetas_dte = {
            '33': 'Factura Electrónica',
            '34': 'Factura Exenta Electrónica',
            '39': 'Boleta Electrónica',
            '41': 'Boleta Exenta Electrónica',
            '52': 'Guía de Despacho Electrónica',
        }
        if tipo_dte not in tipos_dte_permitidos:
            return JsonResponse({'success': False, 'message': 'Tipo de documento no valido.'}, status=400)
        errores_emisor = errores_emisor_para_dte(empresa, tipo_dte)
        if errores_emisor:
            return JsonResponse({'success': False, 'message': errores_emisor[0]}, status=400)
        es_factura = tipo_dte in ['33', '34']
        es_boleta = tipo_dte in ['39', '41']
        es_guia = tipo_dte == '52'
        es_documento_exento = tipo_dte in ['34', '41']

        cliente_id = _id_from_payload(data.get('cliente_id'))
        if not cliente_id:
            return JsonResponse({'success': False, 'message': 'Selecciona un cliente.'}, status=400)
        cliente = Cliente.objects.filter(pk=cliente_id, empresa=empresa).first()
        if not cliente:
            return JsonResponse({'success': False, 'message': 'Cliente no encontrado para la empresa actual.'}, status=404)

        errores_cliente = []
        campos_cliente_obligatorios = [('rut', 'RUT'), ('direccion', 'direccion'), ('comuna', 'comuna')]
        if es_factura or es_guia:
            campos_cliente_obligatorios.append(('giro', 'giro'))
        for campo, etiqueta in campos_cliente_obligatorios:
            if not getattr(cliente, campo, None):
                errores_cliente.append(etiqueta)
        if errores_cliente:
            return JsonResponse({
                'success': False,
                'message': 'El cliente debe tener ' + ', '.join(errores_cliente) + f' para emitir {etiquetas_dte[tipo_dte].lower()}.'
            }, status=400)

        lineas = data.get('items') or []
        if not lineas:
            return JsonResponse({'success': False, 'message': 'Agrega al menos un producto.'}, status=400)

        forma_pago = None
        forma_pago_id = _id_from_payload(data.get('forma_pago_id'))
        if forma_pago_id:
            forma_pago = FormaPago.objects.filter(pk=forma_pago_id, empresa=empresa).first()
            if not forma_pago:
                return JsonResponse({'success': False, 'message': 'Forma de pago no encontrada para la empresa actual.'}, status=404)
        if forma_pago and forma_pago.es_cuenta_corriente and not es_factura:
            return JsonResponse({
                'success': False,
                'message': 'El crédito / cuenta corriente solo se permite en facturas. La boleta se cobra al contado.',
            }, status=400)

        vendedor = None
        vendedor_id = _id_from_payload(data.get('vendedor_id'))
        if vendedor_id:
            vendedor = Vendedor.objects.filter(pk=vendedor_id, empresa=empresa).first()
            if not vendedor:
                return JsonResponse({'success': False, 'message': 'Vendedor no encontrado para la empresa actual.'}, status=404)

        sucursal = None
        sucursal_id = _id_from_payload(data.get('sucursal_id'))
        if sucursal_id:
            sucursal = Sucursal.objects.filter(pk=sucursal_id, empresa=empresa).first()
            if not sucursal:
                return JsonResponse({'success': False, 'message': 'Sucursal no encontrada para la empresa actual.'}, status=404)
        else:
            sucursal = Sucursal.objects.filter(empresa=empresa, estado='activa', es_principal=True).first()

        if not sucursal:
            return JsonResponse({'success': False, 'message': 'No hay una sucursal activa disponible para emitir el documento.'}, status=400)

        tipo_documento_venta = 'guia' if es_guia else ('boleta' if es_boleta else 'factura')
        max_items_permitidos = 50
        if estacion_activa:
            max_items_permitidos = estacion_activa.get_max_items_por_tipo(tipo_documento_venta)
        if len(lineas) > max_items_permitidos:
            return JsonResponse({
                'success': False,
                'message': f'El máximo permitido para {tipo_documento_venta} es {max_items_permitidos} ítems y seleccionaste {len(lineas)}.',
                'max_items': max_items_permitidos,
                'cantidad_items': len(lineas),
                'tipo_documento': tipo_documento_venta,
            }, status=400)

        tipo_despacho = (data.get('tipo_despacho') or '').strip()
        tipo_despacho_sii = (data.get('tipo_despacho_sii') or '2').strip()
        patente_carro = (data.get('patente_carro') or '').strip().upper().replace('-', '')[:8]
        fecha_salida = data.get('fecha_salida') or data.get('fecha')
        hora_salida = (data.get('hora_salida') or '').strip()
        fecha_llegada = data.get('fecha_llegada') or fecha_salida
        vehiculo = None
        chofer = None
        vehiculo_id = _id_from_payload(data.get('vehiculo_id'))
        chofer_id = _id_from_payload(data.get('chofer_id'))
        from pedidos.models_transporte import Vehiculo, Chofer
        if vehiculo_id:
            vehiculo = Vehiculo.objects.filter(pk=vehiculo_id, empresa=empresa, activo=True).first()
        if chofer_id:
            chofer = Chofer.objects.filter(pk=chofer_id, empresa=empresa, activo=True).first()

        # Fallback inteligente para guías
        if es_guia:
            if not chofer and vehiculo and vehiculo.chofer:
                chofer = vehiculo.chofer
            if not vehiculo and chofer:
                vehiculo = Vehiculo.objects.filter(empresa=empresa, chofer=chofer, activo=True).first()
            if not vehiculo:
                un_vehiculo = Vehiculo.objects.filter(empresa=empresa, activo=True)
                if un_vehiculo.count() == 1:
                    vehiculo = un_vehiculo.first()
            if not chofer:
                un_chofer = Chofer.objects.filter(empresa=empresa, activo=True)
                if un_chofer.count() == 1:
                    chofer = un_chofer.first()

        patente_transporte = (vehiculo.patente if vehiculo else '') or (data.get('patente_transporte') or '').strip()
        rut_transportista = (data.get('rut_transportista') or '').strip() or (empresa.rut or '')
        nombre_chofer = (chofer.nombre if chofer else '') or (data.get('nombre_chofer') or '').strip()
        if es_guia and not tipo_despacho:
            return JsonResponse({'success': False, 'message': 'Selecciona el tipo de traslado para la guía.'}, status=400)
        if es_guia and tipo_despacho_sii not in ('1', '2', '3'):
            return JsonResponse({'success': False, 'message': 'Selecciona el tipo de despacho (1, 2 o 3) para la guía.'}, status=400)
        if es_guia and not vehiculo:
            return JsonResponse({'success': False, 'message': 'Selecciona el vehículo desde el maestro para la guía.'}, status=400)
        if es_guia and not chofer:
            return JsonResponse({'success': False, 'message': 'Selecciona el chofer desde el maestro para la guía.'}, status=400)

        items_procesados = []
        neto = Decimal('0.00')
        exento = Decimal('0.00')
        iva = Decimal('0.00')
        total = Decimal('0.00')

        for idx, linea in enumerate(lineas, start=1):
            articulo_id = _id_from_payload(linea.get('articulo_id'))
            articulo = Articulo.objects.filter(pk=articulo_id, empresa=empresa).first() if articulo_id else None
            if not articulo:
                return JsonResponse({'success': False, 'message': f'La linea {idx} tiene un producto invalido.'}, status=400)

            cantidad = _decimal_from_payload(linea.get('cantidad'))
            if cantidad <= 0:
                return JsonResponse({'success': False, 'message': f'La linea {idx} debe tener cantidad mayor a cero.'}, status=400)

            linea_neto = _decimal_from_payload(linea.get('neto'))
            linea_exento = _decimal_from_payload(linea.get('exento'))
            linea_iva = _decimal_from_payload(linea.get('iva'))
            linea_total = _decimal_from_payload(linea.get('total'))

            linea_es_exenta = es_documento_exento or bool(getattr(articulo.categoria, 'exenta_iva', False))

            if linea_es_exenta:
                linea_exento = linea_total if linea_total > 0 else linea_exento
                linea_neto = Decimal('0.00')
                linea_iva = Decimal('0.00')
                linea_total = linea_exento
            else:
                if linea_total <= 0:
                    linea_total = linea_neto + linea_exento + linea_iva
                if linea_iva <= 0 and linea_neto > 0:
                    linea_iva = (linea_neto * Decimal('0.19')).quantize(Decimal('1'))
                    linea_total = linea_neto + linea_exento + linea_iva

            if not linea_es_exenta and linea_neto <= 0 and linea_total > 0:
                linea_neto = (linea_total / Decimal('1.19')).quantize(Decimal('0.01'))
                linea_iva = linea_total - linea_neto
                linea_total = linea_neto + linea_iva

            base_linea = linea_exento if linea_es_exenta else (linea_neto + linea_exento)
            precio_unitario = (base_linea / cantidad).quantize(Decimal('0.01')) if cantidad else Decimal('0.00')
            descripcion = (linea.get('descripcion') or articulo.descripcion or articulo.nombre or '').strip()

            from facturacion_electronica.validacion_envio import documento_exige_precio, traslado_guia_omite_precio
            if documento_exige_precio(tipo_dte, tipo_despacho) and (
                precio_unitario <= 0 or base_linea <= 0 or (not traslado_guia_omite_precio(tipo_despacho) and linea_total <= 0)
            ):
                return JsonResponse({
                    'success': False,
                    'message': (
                        f'El producto "{articulo.nombre}" tiene precio o total 0. '
                        'No se puede emitir así. Corrija el precio del artículo.'
                    ),
                }, status=400)

            items_procesados.append({
                'articulo': articulo,
                'descripcion': descripcion,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario,
                'precio_total': base_linea,
            })
            neto += linea_neto
            exento += linea_exento
            iva += linea_iva
            total += linea_total

        if es_documento_exento:
            neto = Decimal('0.00')
            iva = Decimal('0.00')
            total = exento
        else:
            # El SII exige IVA = round(19% * neto del documento), no la suma de IVA por línea.
            iva = (neto * Decimal('0.19')).quantize(Decimal('1'))
            total = neto + exento + iva

        fecha_documento = timezone.localdate()
        if data.get('fecha'):
            try:
                fecha_documento = datetime.strptime(data.get('fecha'), '%Y-%m-%d').date()
            except Exception:
                fecha_documento = timezone.localdate()
        if tipo_documento_venta in ['factura', 'guia']:
            fecha_vencimiento = resolver_fecha_vencimiento(
                fecha_documento,
                getattr(cliente, 'plazo_pago', 0),
                data.get('fecha_vencimiento'),
            )
        else:
            fecha_vencimiento = None

        monto_pagado = _decimal_from_payload(data.get('monto_pagado'))
        if not forma_pago or not forma_pago.es_cuenta_corriente:
            monto_pagado = total
        elif monto_pagado > total:
            monto_pagado = total

        # Obtener dirección de despacho seleccionada
        direccion_receptor = (data.get('direccion_receptor') or '').strip()
        comuna_receptor = (data.get('comuna_receptor') or '').strip()
        ciudad_receptor = (data.get('ciudad_receptor') or '').strip()
        direccion_cliente_id = data.get('direccion_cliente_id')
        direccion_cliente = None
        if direccion_cliente_id and str(direccion_cliente_id).isdigit():
            from clientes.models import DireccionCliente
            direccion_cliente = DireccionCliente.objects.filter(pk=direccion_cliente_id, cliente=cliente).first()
            if direccion_cliente:
                direccion_receptor = direccion_receptor or direccion_cliente.direccion
                comuna_receptor = comuna_receptor or direccion_cliente.comuna or ''
                ciudad_receptor = ciudad_receptor or direccion_cliente.ciudad or ''

        if not direccion_receptor:
            direccion_receptor = cliente.direccion or ''
            comuna_receptor = cliente.comuna or ''
            ciudad_receptor = getattr(cliente, 'ciudad', '') or ''

        with transaction.atomic():
            temp_numero = 'FD' + timezone.now().strftime('%y%m%d%H%M%S%f')[:18]
            venta = Venta.objects.create(
                empresa=empresa,
                sucursal=sucursal,
                numero_venta=temp_numero,
                fecha=fecha_documento,
                fecha_vencimiento=fecha_vencimiento,
                cliente=cliente,
                vendedor=vendedor,
                forma_pago=forma_pago,
                tipo_documento=tipo_documento_venta,
                tipo_documento_planeado=tipo_documento_venta,
                tipo_despacho=tipo_despacho or None,
                direccion_despacho=direccion_receptor,
                comuna_despacho=comuna_receptor,
                ciudad_despacho=ciudad_receptor,
                direccion_cliente=direccion_cliente,
                vehiculo=vehiculo,
                chofer=chofer,
                subtotal=neto + exento,
                descuento=Decimal('0.00'),
                neto=neto,
                iva=iva,
                impuesto_especifico=Decimal('0.00'),
                total=total,
                estado='confirmada',
                observaciones='[FACTURADOR_DIRECTO] ' + (data.get('observaciones') or ''),
                monto_pagado=monto_pagado,
                saldo_pendiente=total - monto_pagado,
                usuario_creacion=request.user,
            )

            for item in items_procesados:
                VentaDetalle.objects.create(
                    venta=venta,
                    articulo=item['articulo'],
                    comentario=item['descripcion'],
                    cantidad=item['cantidad'],
                    precio_unitario=item['precio_unitario'],
                    precio_total=item['precio_total'],
                    impuesto_especifico=Decimal('0.00'),
                )

            venta.subtotal = neto + exento
            venta.neto = neto
            venta.iva = iva
            venta.total = total
            venta.monto_pagado = monto_pagado
            venta.saldo_pendiente = total - monto_pagado
            venta.save(update_fields=['subtotal', 'neto', 'iva', 'total', 'monto_pagado', 'saldo_pendiente'])

            try:
                dte = dte_service.generar_dte_desde_venta(
                    venta,
                    tipo_dte,
                    patente_transporte=patente_transporte,
                    rut_transportista=rut_transportista,
                    nombre_chofer=nombre_chofer,
                    tipo_despacho_sii=tipo_despacho_sii,
                    patente_carro=patente_carro,
                    fecha_salida=fecha_salida,
                    hora_salida=hora_salida,
                    fecha_llegada=fecha_llegada,
                    direccion_receptor=direccion_receptor,
                    comuna_receptor=comuna_receptor,
                    ciudad_receptor=ciudad_receptor,
                )
            except ValueError as exc:
                transaction.set_rollback(True)
                return JsonResponse({'success': False, 'message': str(exc)}, status=400)
            except Exception as exc:
                transaction.set_rollback(True)
                return JsonResponse({'success': False, 'message': f'Error al generar DTE: {exc}'}, status=500)

            numero_final = f"{dte.folio:06d}"
            if not Venta.objects.filter(empresa=empresa, tipo_documento=tipo_documento_venta, numero_venta=numero_final).exclude(pk=venta.pk).exists():
                venta.numero_venta = numero_final
                venta.save(update_fields=['numero_venta'])

            cuenta_corriente = False
            if es_factura and forma_pago and forma_pago.es_cuenta_corriente and venta.saldo_pendiente > 0:
                cuenta_corriente = _registrar_factura_directa_cuenta_corriente(venta, dte, monto_pagado, request.user)

        envio = {'success': False, 'message': 'No enviado'}
        try:
            envio = dte_service.enviar_dte_al_sii(dte)
        except Exception as exc:
            envio = {'success': False, 'message': str(exc)}

        enviado = bool(envio.get('success'))
        return JsonResponse({
            'success': enviado,
            'emitido': True,
            'message': (
                f"{etiquetas_dte.get(tipo_dte, 'Documento')} folio {dte.folio} generado y enviado al SII."
                if enviado
                else (
                    f"{etiquetas_dte.get(tipo_dte, 'Documento')} folio {dte.folio} ya fue emitido. "
                    f"No se envió al SII: {envio.get('message') or 'error de envío'}. "
                    'No vuelva a emitir: use Reenviar al SII para no gastar otro folio.'
                )
            ),
            'dte_id': dte.id,
            'folio': dte.folio,
            'tipo_dte': tipo_dte,
            'envio': envio,
            'cuenta_corriente': cuenta_corriente,
            'print_url': reverse('facturacion_electronica:ver_factura_electronica', kwargs={'dte_id': dte.id}),
        }, status=200 if enviado else 400)

    clientes = Cliente.objects.filter(empresa=empresa, estado='activo').prefetch_related('direcciones').order_by('nombre')
    articulos = Articulo.objects.filter(empresa=empresa, activo=True).select_related('categoria', 'unidad_medida').order_by('nombre')[:1000]
    formas_pago = FormaPago.objects.filter(empresa=empresa, activo=True).order_by('nombre')
    vendedores = Vendedor.objects.filter(empresa=empresa, activo=True).order_by('nombre')
    sucursales = Sucursal.objects.filter(empresa=empresa, estado='activa').order_by('-es_principal', 'nombre')
    from bodegas.models import Bodega
    from inventario.models import Stock
    from pedidos.models_transporte import Vehiculo, Chofer
    bodegas = Bodega.objects.filter(empresa=empresa, activa=True).order_by('nombre')
    vehiculos = Vehiculo.objects.filter(empresa=empresa, activo=True).select_related('chofer').order_by('patente')
    choferes = Chofer.objects.filter(empresa=empresa, activo=True).order_by('nombre')

    articulo_ids = [articulo.id for articulo in articulos]
    stock_total_por_articulo = {
        row['articulo_id']: row['total'] or Decimal('0.00')
        for row in Stock.objects.filter(empresa=empresa, articulo_id__in=articulo_ids)
        .values('articulo_id')
        .annotate(total=Sum('cantidad'))
    }
    stock_por_bodega = {}
    for row in Stock.objects.filter(empresa=empresa, articulo_id__in=articulo_ids).values('articulo_id', 'bodega_id', 'cantidad'):
        stock_por_bodega.setdefault(row['articulo_id'], {})[str(row['bodega_id'])] = float(row['cantidad'] or 0)

    articulos_json = []
    for articulo in articulos:
        precio = _decimal_from_payload(getattr(articulo, 'precio_venta', 0))
        stock_total = stock_total_por_articulo.get(articulo.id, Decimal('0.00'))
        articulos_json.append({
            'id': articulo.id,
            'codigo': articulo.codigo or '',
            'nombre': articulo.nombre or '',
            'descripcion': articulo.descripcion or articulo.nombre or '',
            'precio': float(precio),
            'stock': float(stock_total),
            'stock_bodegas': stock_por_bodega.get(articulo.id, {}),
            'exento': bool(articulo.categoria.exenta_iva) if articulo.categoria else False,
        })

    clientes_json = [{
        'id': cliente.id,
        'rut': cliente.rut or '',
        'nombre': cliente.nombre or '',
        'giro': cliente.giro or '',
        'direccion': cliente.direccion or '',
        'comuna': cliente.comuna or '',
        'ciudad': cliente.ciudad or '',
        'plazo_pago': int(str(cliente.plazo_pago).strip()) if str(cliente.plazo_pago or '').strip().isdigit() else 0,
        'forma_pago_defecto_id': cliente.forma_pago_defecto_id,
        'direcciones': cliente.get_direcciones_list(),
    } for cliente in clientes]

    return render(request, 'ventas/facturar_directo.html', {
        'clientes': clientes,
        'clientes_json': clientes_json,
        'articulos': articulos,
        'articulos_json': articulos_json,
        'formas_pago': formas_pago,
        'vendedores': vendedores,
        'sucursales': sucursales,
        'bodegas': bodegas,
        'today': timezone.localdate(),
        'estacion_activa': estacion_activa,
        'max_items_config': {
            'factura': estacion_activa.max_items_factura if estacion_activa else 20,
            'boleta': estacion_activa.max_items_boleta if estacion_activa else 35,
            'guia': estacion_activa.max_items_guia if estacion_activa else 50,
        },
        'tipo_despacho_choices': Venta.TIPO_DESPACHO_CHOICES,
        'tipo_despacho_sii_choices': TIPO_DESPACHO_SII_CHOICES,
        'vehiculos': vehiculos,
        'choferes': choferes,
        'rut_empresa': empresa.rut or '',
        'hora_actual': timezone.localtime().strftime('%H:%M'),
        'errores_emisor_factura': errores_emisor_para_dte(empresa, '33'),
    })


@login_required
@requiere_empresa
@permission_required('ventas.add_venta', raise_exception=True)
def facturar_guias_list(request):
    """
    Lista de clientes con opción de filtrar los que tienen guías pendientes
    """
    from facturacion_electronica.models import DocumentoTributarioElectronico
    
    empresa = request.empresa
    search = request.GET.get('search', '').strip()
    solo_pendientes = request.GET.get('solo_pendientes', '1') == '1' # Por defecto solo pendientes
    estacion_id = request.session.get('pos_estacion_id')
    estacion_activa = None
    if estacion_id:
        estacion_activa = EstacionTrabajo.objects.filter(id=estacion_id, empresa=empresa, activo=True).first()
    if not estacion_activa:
        estacion_activa = EstacionTrabajo.objects.filter(empresa=empresa, activo=True).order_by('numero').first()
    
    # 1. Obtener IDs de ventas que YA están en facturas
    invoiced_ventas_ids = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa,
        tipo_dte__in=['33', '34'],
        orden_despacho__isnull=False
    ).values_list('orden_despacho__id', flat=True)
    
    # 2. Guías pendientes globalmente (para el contador y filtro rápido)
    # Una venta es facturable si: es tipo 'guia' O tiene un DTE de tipo '52' asociado
    guias_pendientes_qs = Venta.objects.filter(
        empresa=empresa,
        estado='confirmada'
    ).filter(
        Q(tipo_documento='guia') | Q(dte__tipo_dte='52')
    ).exclude(id__in=invoiced_ventas_ids).distinct()
    
    clientes_con_pendientes_ids = guias_pendientes_qs.values_list('cliente_id', flat=True).distinct()
    total_clientes_pendientes = len(clientes_con_pendientes_ids)
    
    # 3. Filtrar clientes
    if solo_pendientes:
        clientes = Cliente.objects.filter(id__in=clientes_con_pendientes_ids, empresa=empresa)
    else:
        clientes = Cliente.objects.filter(empresa=empresa)
    
    if search:
        clientes = clientes.filter(Q(nombre__icontains=search) | Q(rut__icontains=search))
    
    clientes = clientes.order_by('nombre')
    
    # 4. Enriquecer datos de clientes (Solo si es necesario para el listado actual)
    for cliente in clientes:
        cliente_pendientes = guias_pendientes_qs.filter(cliente=cliente)
        cliente.cant_guias_pendientes = cliente_pendientes.count()
        cliente.total_pendiente = cliente_pendientes.aggregate(Sum('total'))['total__sum'] or 0
        cliente.tiene_pendientes = cliente.id in clientes_con_pendientes_ids
    
    # Paginación
    paginator = Paginator(clientes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    vendedores = Vendedor.objects.filter(empresa=empresa, activo=True).order_by('nombre')
    formas_pago = FormaPago.objects.filter(empresa=empresa, activo=True).order_by('nombre')

    context = {
        'page_obj': page_obj,
        'search': search,
        'solo_pendientes': solo_pendientes,
        'total_clientes_pendientes': total_clientes_pendientes,
        'estacion_activa': estacion_activa,
        'vendedores': vendedores,
        'formas_pago': formas_pago,
        'max_items_config': {
            'factura': estacion_activa.max_items_factura if estacion_activa else 20,
            'boleta': estacion_activa.max_items_boleta if estacion_activa else 35,
            'guia': estacion_activa.max_items_guia if estacion_activa else 50,
            'cotizacion': estacion_activa.max_items_cotizacion if estacion_activa else 50,
            'vale': estacion_activa.max_items_vale if estacion_activa else 30,
        }
    }
    
    return render(request, 'ventas/facturar_guias_list.html', context)

@login_required
@requiere_empresa
def api_guias_pendientes_cliente(request, cliente_id):
    """
    Retorna las guías pendientes de un cliente específico en JSON
    """
    from facturacion_electronica.models import DocumentoTributarioElectronico
    
    empresa = request.empresa
    cliente = Cliente.objects.filter(id=cliente_id, empresa=empresa).first()
    
    # Usar EXACTAMENTE la misma lógica que el queryset de pendientes global
    invoiced_ventas_ids = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa,
        tipo_dte__in=['33', '34'],
        orden_despacho__isnull=False
    ).values_list('orden_despacho__id', flat=True)
    
    guias = Venta.objects.filter(
        empresa=empresa,
        cliente_id=cliente_id,
        estado='confirmada'
    ).filter(
        Q(tipo_documento='guia') | Q(dte__tipo_dte='52')
    ).exclude(id__in=invoiced_ventas_ids).distinct().order_by('fecha', 'numero_venta')
    
    vendedor_sugerido_id = guias.filter(vendedor__isnull=False).values_list('vendedor_id', flat=True).last()
    forma_pago_sugerida_id = None
    if cliente and cliente.forma_pago_defecto_id:
        forma_pago_sugerida_id = cliente.forma_pago_defecto_id
    elif guias.filter(forma_pago__isnull=False).exists():
        forma_pago_sugerida_id = guias.filter(forma_pago__isnull=False).values_list('forma_pago_id', flat=True).last()

    data = []
    for g in guias:
        try:
            # Buscar DTE de forma directa (campo dte es el related_name del OneToOne)
            dte = getattr(g, 'dte', None)
            
            # Fallback a dte_asociado solo si dte es None
            if not dte:
                dte = g.dte_asociado
            
            folio = dte.folio if dte else g.numero_venta
            
            articulo_ids = list(g.ventadetalle_set.values_list('articulo_id', flat=True).distinct())
            data.append({
                'id': g.id,
                'numero': folio,
                'fecha': g.fecha.strftime('%d-%m-%Y'),
                'total': float(g.total),
                'observaciones': g.observaciones,
                'es_dte': dte is not None,
                'cantidad_items': len(articulo_ids),
                'articulo_ids': articulo_ids,
            })
        except Exception as e:
            print(f"[ERROR API GUIAS] Guía ID {g.id}: {str(e)}")
            # Fallback mínimo para no romper el listado
            articulo_ids = list(g.ventadetalle_set.values_list('articulo_id', flat=True).distinct())
            data.append({
                'id': g.id,
                'numero': g.numero_venta,
                'fecha': g.fecha.strftime('%d-%m-%Y'),
                'total': float(g.total),
                'observaciones': g.observaciones,
                'es_dte': False,
                'cantidad_items': len(articulo_ids),
                'articulo_ids': articulo_ids,
            })
    
    return JsonResponse({
        'success': True,
        'guias': data,
        'count': len(data),
        'vendedor_sugerido_id': vendedor_sugerido_id,
        'forma_pago_sugerida_id': forma_pago_sugerida_id,
        'cliente_nombre': cliente.nombre if cliente else '',
        'cliente_rut': cliente.rut if cliente else '',
    })

@login_required
@requiere_empresa
@transaction.atomic
def api_procesar_factura_consolidada(request):
    """
    Crea una factura consolidada a partir de múltiples guías
    """
    import json
    from facturacion_electronica.dte_service import DTEService
    from django.db import transaction
    
    try:
        data = json.loads(request.body)
        guia_ids = data.get('guia_ids', [])
        cliente_id = data.get('cliente_id')
        tipo_factura = data.get('tipo_documento', '33') # 33: Factura, 39: Boleta
        
        if not guia_ids:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar al menos una guía.'})
        
        guias = Venta.objects.filter(id__in=guia_ids, empresa=request.empresa)
        cliente = Cliente.objects.get(id=cliente_id, empresa=request.empresa)
        
        # Consolidados de ítems
        items_consolidados = {} # {articulo_id: {'articulo': obj, 'cantidad': X, 'precio_unitario': Y}}
        
        for guia in guias:
            for detalle in guia.ventadetalle_set.all():
                art_id = detalle.articulo_id
                if art_id in items_consolidados:
                    items_consolidados[art_id]['cantidad'] += detalle.cantidad
                    # Podríamos promediar precio o usar el último, asumiendo mismos para el mismo cliente
                else:
                    items_consolidados[art_id] = {
                        'articulo': detalle.articulo,
                        'cantidad': detalle.cantidad,
                        'precio_unitario': detalle.precio_unitario
                    }
        cantidad_items_consolidados = len(items_consolidados)
        
        # Obtener estación de trabajo para el correlativo
        estacion_id = request.session.get('pos_estacion_id')
        estacion = None
        if estacion_id:
            estacion = EstacionTrabajo.objects.filter(id=estacion_id, empresa=request.empresa).first()
        
        if not estacion:
            estacion = EstacionTrabajo.objects.filter(empresa=request.empresa, activo=True).first()
        
        if not estacion:
            return JsonResponse({'success': False, 'message': 'No hay estaciones de trabajo configuradas.'})

        tipo_documento_venta = 'factura' if tipo_factura == '33' else 'boleta'
        max_items_permitidos = estacion.get_max_items_por_tipo(tipo_documento_venta)
        if cantidad_items_consolidados > max_items_permitidos:
            return JsonResponse({
                'success': False,
                'message': (
                    f'Las guías seleccionadas generan {cantidad_items_consolidados} ítems consolidados y '
                    f'el máximo permitido para {tipo_documento_venta} es {max_items_permitidos}.'
                ),
                'cantidad_items': cantidad_items_consolidados,
                'max_items': max_items_permitidos,
                'tipo_documento': tipo_documento_venta,
            })

        # Generar identificador temporal único para la venta consolidada
        temp_numero = 'FC' + timezone.now().strftime('%y%m%d%H%M%S%f')[:18]

        # Resolver Vendedor y Forma de Pago
        vendedor_id = data.get('vendedor_id')
        forma_pago_id = data.get('forma_pago_id')

        vendedor = None
        if vendedor_id:
            vendedor = Vendedor.objects.filter(id=vendedor_id, empresa=request.empresa, activo=True).first()
        if not vendedor:
            v_id = guias.filter(vendedor__isnull=False).values_list('vendedor_id', flat=True).last()
            if v_id:
                vendedor = Vendedor.objects.filter(id=v_id).first()
        if not vendedor:
            vendedor = Vendedor.objects.filter(empresa=request.empresa, activo=True).first()

        forma_pago = None
        if forma_pago_id:
            forma_pago = FormaPago.objects.filter(id=forma_pago_id, empresa=request.empresa, activo=True).first()
        if not forma_pago and getattr(cliente, 'forma_pago_defecto', None):
            forma_pago = cliente.forma_pago_defecto
        if not forma_pago:
            fp_id = guias.filter(forma_pago__isnull=False).values_list('forma_pago_id', flat=True).last()
            if fp_id:
                forma_pago = FormaPago.objects.filter(id=fp_id).first()
        if not forma_pago:
            forma_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).first()

        folios_guias = []
        for g in guias:
            f = getattr(getattr(g, 'dte', None), 'folio', None) or g.numero_venta
            folios_guias.append(str(f))
        observaciones_consolidada = f"Factura consolidada de Guías: {', '.join(folios_guias)}"

        # Crear nueva Venta para la Factura (Consolidada)
        nueva_venta = Venta.objects.create(
            empresa=request.empresa,
            sucursal=guias[0].sucursal if guias.exists() else None,
            numero_venta=temp_numero,
            fecha=timezone.localdate(),
            cliente=cliente,
            tipo_documento=tipo_documento_venta,
            tipo_documento_planeado=tipo_documento_venta,
            estado='confirmada',
            observaciones=observaciones_consolidada,
            usuario_creacion=request.user,
            vendedor=vendedor,
            forma_pago=forma_pago,
            estacion_trabajo=estacion
        )

        # Crear detalles consolidados
        for item in items_consolidados.values():
            VentaDetalle.objects.create(
                venta=nueva_venta,
                articulo=item['articulo'],
                cantidad=item['cantidad'],
                precio_unitario=item['precio_unitario']
            )

        nueva_venta.calcular_totales()

        # Configurar cobro y estado financiero según la forma de pago
        es_credito = bool(forma_pago and getattr(forma_pago, 'es_credito', False))
        if es_credito:
            nueva_venta.monto_pagado = Decimal('0.00')
            nueva_venta.saldo_pendiente = nueva_venta.total
        else:
            nueva_venta.monto_pagado = nueva_venta.total
            nueva_venta.saldo_pendiente = Decimal('0.00')
        nueva_venta.save(update_fields=['monto_pagado', 'saldo_pendiente'])

        # Crear referencias tributarias a las guías consolidadas
        from .models import VentaReferencia
        import re
        for guia in guias:
            num_raw = str(getattr(getattr(guia, 'dte', None), 'folio', None) or guia.numero_venta or '')
            digits = re.sub(r'\D', '', num_raw).lstrip('0')
            g_folio = digits if digits else num_raw
            g_fecha = getattr(getattr(guia, 'dte', None), 'fecha_emision', None) or guia.fecha
            VentaReferencia.objects.create(
                venta=nueva_venta,
                tipo_referencia='52',
                folio_referencia=str(g_folio),
                fecha_referencia=g_fecha,
                razon_referencia=f"Guía de Despacho N° {g_folio}"
            )

        # Generar DTE
        dte_service = DTEService(request.empresa)
        dte = dte_service.generar_dte_desde_venta(nueva_venta, tipo_factura)

        if dte:
            # Actualizar numero_venta con el folio oficial si no colisiona
            numero_final = f"{dte.folio:06d}"
            if not Venta.objects.filter(empresa=request.empresa, tipo_documento=nueva_venta.tipo_documento, numero_venta=numero_final).exclude(pk=nueva_venta.pk).exists():
                nueva_venta.numero_venta = numero_final
                nueva_venta.save(update_fields=['numero_venta'])

            # Vincular guías originales en el many-to-many
            for guia in guias:
                dte.orden_despacho.add(guia)
            
            return JsonResponse({
                'success': True, 
                'message': f'Documento #{dte.folio} generado exitosamente.',
                'dte_id': dte.id,
                'print_url': reverse('facturacion_electronica:ver_factura_electronica', kwargs={'dte_id': dte.id}),
            })
        else:
            return JsonResponse({'success': False, 'message': 'Se creó el registro pero el servicio DTE no pudo generar el documento.'})

    except Exception as e:
        import traceback
        print(f"[ERROR CONSOLIDACION] {str(e)}")
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

