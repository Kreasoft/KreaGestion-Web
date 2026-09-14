"""Reimpresión desde el visor usando la cola del agente, sin el visor de Chrome."""
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

from core.decorators import requiere_empresa
from caja.models import Caja, ColaImpresion, ImpresoraAgente
from caja.impresion_utils import AGENTE_TIMEOUT_SEGUNDOS, generar_esc_pos_ticket
from .models import DocumentoTributarioElectronico

logger = logging.getLogger(__name__)
TIPOS = {'33': 'factura', '34': 'factura', '39': 'boleta', '41': 'boleta', '52': 'guia', '56': 'nota_debito', '61': 'nota_credito'}


def _cajas(request):
    qs = Caja.objects.filter(empresa=request.empresa, sucursal__empresa=request.empresa, activo=True)
    sucursal = getattr(request, 'sucursal_activa', None)
    if sucursal is None and not request.user.is_superuser:
        sucursal = getattr(getattr(request.user, 'perfil', None), 'sucursal', None)
    if sucursal is not None:
        qs = qs.filter(sucursal=sucursal)
    return qs.select_related('sucursal')


def _online(caja):
    return bool(caja.agente_ultimo_ping and caja.agente_ultimo_ping >=
                timezone.now() - timedelta(seconds=AGENTE_TIMEOUT_SEGUNDOS))


def _respuesta_trabajo(job):
    mensajes = {
        'pendiente': 'Trabajo en cola. Esperando al agente.',
        'imprimiendo': 'El agente recibió el trabajo y lo está procesando.',
        'impreso': 'El agente confirmó el envío a la impresora. Compruebe la salida en papel.',
        'error': 'El agente informó un error. Revise la impresora y el agente antes de repetir.',
    }
    return {'success': True, 'trabajo_id': job.pk, 'estado': job.estado,
            'message': mensajes.get(job.estado, 'Estado de impresión desconocido.')}


@login_required
@requiere_empresa
@require_http_methods(['GET', 'POST'])
@never_cache
def imprimir_dte_agente(request, dte_id):
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    if not request.user.has_perm('ventas.view_venta'):
        return JsonResponse({'success': False, 'message': 'No tiene permiso para imprimir ventas.'}, status=403)
    cajas = _cajas(request)
    if request.method == 'GET':
        if request.GET.get('trabajo_id'):
            try:
                trabajo_id = int(request.GET['trabajo_id'])
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'Trabajo inválido.'}, status=400)
            job = get_object_or_404(ColaImpresion, pk=trabajo_id,
                                   empresa=request.empresa, caja__in=cajas,
                                   documento_id=dte.pk, tipo_documento='dte')
            return JsonResponse(_respuesta_trabajo(job))
        destinos = []
        for c in cajas.order_by('sucursal_id', 'numero'):
            imp = ImpresoraAgente.objects.filter(empresa=request.empresa, caja=c, en_uso=True).order_by('-ultimo_reporte').first()
            nombre_imp = f" ({imp.nombre})" if imp and imp.nombre else ""
            destinos.append({
                'id': c.pk,
                'nombre': f"{c.sucursal.nombre} / {c.nombre}{nombre_imp}",
                'online': _online(c),
                'impresora': imp.nombre if imp else ''
            })
        return JsonResponse({'success': True, 'destinos': destinos})

    empresa_id_req = request.POST.get('empresa_id')
    if empresa_id_req and str(empresa_id_req) != str(request.empresa.pk):
        return JsonResponse({'success': False, 'message': 'La empresa activa cambió. Recargue el documento.'}, status=409)
    if dte.tipo_dte not in TIPOS or not dte.venta_id:
        return JsonResponse({'success': False, 'message': 'Este documento todavía no admite impresión directa por agente. Use la opción del navegador.'}, status=400)
    if not dte.puede_emitir_documento_tributario:
        return JsonResponse({'success': False, 'message': dte.get_mensaje_no_emitible()}, status=400)

    caja = None
    caja_id_param = request.POST.get('caja_id')
    if caja_id_param:
        try:
            caja = cajas.filter(pk=int(caja_id_param)).first()
        except (ValueError, TypeError):
            pass

    if not caja:
        # Prioridad 1: caja que esté online
        for c in cajas:
            if _online(c):
                caja = c
                break

    if not caja:
        # Prioridad 2: resolver caja habitual (estación o sucursal)
        from caja.impresion_utils import resolver_caja_cola_impresion
        caja = resolver_caja_cola_impresion(
            request.empresa,
            sucursal=getattr(request, 'sucursal_activa', None),
            tipo_documento='dte'
        )

    if not caja:
        caja = cajas.first()

    if not caja:
        return JsonResponse({'success': False, 'message': 'No hay cajas activas registradas para esta empresa.'}, status=400)

    if not _online(caja):
        return JsonResponse({
            'success': False,
            'agente_desconectado': True,
            'message': 'El agente de impresión local está desconectado. Inicie el agente en el equipo.'
        }, status=409)

    try:
        with transaction.atomic():
            # Serializa solicitudes simultáneas del mismo documento.
            dte = DocumentoTributarioElectronico.objects.select_for_update().get(pk=dte.pk, empresa=request.empresa)
            if not dte.puede_emitir_documento_tributario:
                return JsonResponse({'success': False, 'message': dte.get_mensaje_no_emitible()}, status=400)
            # Solo reutilizar si hay un trabajo activamente en cola ('pendiente' o 'imprimiendo')
            previo = ColaImpresion.objects.filter(
                empresa=request.empresa, caja=caja, documento_id=dte.pk, tipo_documento='dte',
                estado__in=['pendiente', 'imprimiendo']
            ).order_by('-pk').first()
            if previo:
                return JsonResponse(_respuesta_trabajo(previo))
            from ventas.models import Venta
            venta = get_object_or_404(Venta.objects.select_related('empresa', 'cliente', 'sucursal',
                'vendedor', 'estacion_trabajo').prefetch_related('ventadetalle_set__articulo', 'referencias'),
                pk=dte.venta_id, empresa=request.empresa)
            tipo = TIPOS[dte.tipo_dte]
            # Cambios solo en memoria: conserva el DTE y genera ticket ESC/POS para el agente
            venta._dte_para_ticket = dte
            venta.tipo_documento = tipo
            contenido = generar_esc_pos_ticket(venta)
            if not contenido:
                raise ValueError('Ticket vacío')
            impresora = ImpresoraAgente.objects.filter(empresa=request.empresa, caja=caja,
                en_uso=True).order_by('-ultimo_reporte').first()
            if not impresora:
                impresora = ImpresoraAgente.objects.filter(empresa=request.empresa, caja=caja
                    ).order_by('-ultimo_reporte').first()
            job = ColaImpresion.objects.create(empresa=request.empresa, caja=caja, venta=venta,
                documento_id=dte.pk, tipo_documento='dte', contenido_raw=contenido,
                nombre_impresora=impresora.nombre if impresora else '', estado='pendiente')
        return JsonResponse(_respuesta_trabajo(job), status=201)
    except (ValueError, RuntimeError):
        return JsonResponse({'success': False, 'message': 'No se pudo preparar el ticket. No se envió un trabajo nuevo.'}, status=500)

