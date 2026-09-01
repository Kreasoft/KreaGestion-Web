import json
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from empresas.models import Empresa, Sucursal
from .models import (
    Caja, ColaImpresion, ImpresoraAgente,
    asignar_impresora_estacion_desde_agente, ensure_impresoras_agente,
)

_IMPRESORAS_VIRTUALES = (
    'rustdesk', 'anydesk', 'teamviewer', 'pdf', 'xps', 'onenote', 'fax',
    'microsoft print to pdf', 'microsoft pps', 'cutepdf', 'foxit', 'chrome',
    'send to',
)


def _es_impresora_virtual(nombre):
    n = (nombre or '').lower()
    return any(token in n for token in _IMPRESORAS_VIRTUALES)


def _parsear_impresoras(request):
    raw = (request.GET.get('impresoras') or '').strip()
    if not raw:
        return []
    if raw.startswith('['):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except (TypeError, ValueError):
            pass
    return [p.strip() for p in raw.replace('||', '|').split('|') if p.strip()]


def registrar_impresoras_agente(caja, nombres, seleccionada=''):
    if caja is None:
        return
    ensure_impresoras_agente()
    ahora = timezone.now()
    nombres = [n for n in (nombres or []) if n and not _es_impresora_virtual(n)]
    seleccionada = (seleccionada or '').strip()
    if seleccionada and not _es_impresora_virtual(seleccionada) and seleccionada not in nombres:
        nombres = list(nombres) + [seleccionada]
    for nombre in nombres:
        ImpresoraAgente.objects.update_or_create(
            caja=caja,
            nombre=nombre,
            defaults={
                'empresa': caja.empresa,
                'sucursal': caja.sucursal,
                'en_uso': nombre == seleccionada,
                'ultimo_reporte': ahora,
            },
        )
    if nombres:
        ImpresoraAgente.objects.filter(caja=caja).exclude(nombre__in=nombres).update(en_uso=False)
    asignar_impresora_estacion_desde_agente(caja, seleccionada)


def _int_param(value):
    try:
        if value is None or value == '':
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolver_caja_agente(empresa_id, sucursal_id, caja_id):
    if not empresa_id or not sucursal_id:
        return None, 'empresa_id y sucursal_id son requeridos'

    empresa = Empresa.objects.filter(id=empresa_id, estado='activa').first()
    if not empresa:
        return None, 'Empresa no activa o no encontrada'

    sucursal = Sucursal.objects.filter(id=sucursal_id, empresa=empresa, estado='activa').first()
    if not sucursal:
        return None, 'Sucursal no activa o no pertenece a la empresa'

    cajas = Caja.objects.filter(empresa=empresa, sucursal=sucursal, activo=True)
    if caja_id:
        caja = cajas.filter(id=caja_id).first()
        if not caja:
            return None, 'La caja no pertenece a esa empresa y sucursal'
        return caja, None

    return None, None


@csrf_exempt
@require_http_methods(["GET"])
def listar_destinos(request):
    """Empresas activas, sucursales activas y cajas para configurar el agente."""
    empresas_data = []
    empresas = Empresa.objects.filter(estado='activa').order_by('nombre')

    for empresa in empresas:
        sucursales_data = []
        sucursales = empresa.sucursales.filter(estado='activa').order_by('nombre')
        for sucursal in sucursales:
            cajas = Caja.objects.filter(
                empresa=empresa, sucursal=sucursal, activo=True
            ).order_by('numero', 'nombre')
            sucursales_data.append({
                'id': sucursal.id,
                'nombre': sucursal.nombre,
                'cajas': [
                    {
                        'id': caja.id,
                        'numero': caja.numero,
                        'nombre': caja.nombre,
                    }
                    for caja in cajas
                ],
            })
        empresas_data.append({
            'id': empresa.id,
            'nombre': empresa.nombre,
            'rut': empresa.rut or '',
            'sucursales': sucursales_data,
        })

    return JsonResponse({'empresas': empresas_data})


@csrf_exempt
@require_http_methods(["GET"])
def obtener_pendientes(request):
    """
    El agente de esa caja reporta sus impresoras Windows y solo toma
    trabajos encolados a esa caja.
    """
    empresa_id = _int_param(request.GET.get('empresa_id'))
    sucursal_id = _int_param(request.GET.get('sucursal_id'))
    caja_id = _int_param(request.GET.get('caja_id'))

    caja, error = _resolver_caja_agente(empresa_id, sucursal_id, caja_id)
    if error:
        return JsonResponse({'error': error}, status=400)

    ahora = timezone.now()
    if caja is not None:
        Caja.objects.filter(pk=caja.pk).update(agente_ultimo_ping=ahora)
        registrar_impresoras_agente(
            caja,
            _parsear_impresoras(request),
            request.GET.get('impresora') or '',
        )
    else:
        Caja.objects.filter(
            empresa_id=empresa_id,
            sucursal_id=sucursal_id,
            activo=True,
        ).update(agente_ultimo_ping=ahora)

    filtros = {
        'caja__empresa_id': empresa_id,
        'caja__sucursal_id': sucursal_id,
    }
    if caja is not None:
        filtros['caja_id'] = caja.id

    alcance_empresa = Q(empresa_id=empresa_id) | Q(empresa__isnull=True)

    ColaImpresion.objects.filter(
        estado='imprimiendo',
        fecha_impresion__lt=ahora - timedelta(minutes=5),
        **filtros,
    ).filter(alcance_empresa).update(estado='pendiente', fecha_impresion=None)

    with transaction.atomic():
        pendientes = list(
            ColaImpresion.objects.select_for_update(skip_locked=True).filter(
                estado='pendiente',
                **filtros,
            ).filter(alcance_empresa).order_by('fecha_creacion')[:10]
        )

        for trabajo in pendientes:
            trabajo.estado = 'imprimiendo'
            trabajo.fecha_impresion = ahora
            trabajo.save(update_fields=['estado', 'fecha_impresion'])

    data = []
    for p in pendientes:
        data.append({
            'id': p.id,
            'contenido_raw': p.contenido_raw,
            'nombre_impresora': p.nombre_impresora or '',
            'fecha_creacion': p.fecha_creacion.isoformat(),
        })

    return JsonResponse({'pendientes': data})


@csrf_exempt
@require_http_methods(["POST"])
def marcar_impreso(request, trabajo_id=None):
    """
    Marca un trabajo como impreso o con error.
    """
    try:
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except (TypeError, ValueError):
            body = {}

        job_id = body.get('id') or trabajo_id
        status = body.get('status') or body.get('estado') or 'impreso'
        error_msg = body.get('error_msg') or body.get('error') or ''
        empresa_id = _int_param(body.get('empresa_id'))
        sucursal_id = _int_param(body.get('sucursal_id'))

        if not job_id or status not in ['impreso', 'error']:
            return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

        qs = ColaImpresion.objects.filter(id=job_id)
        if empresa_id:
            qs = qs.filter(Q(empresa_id=empresa_id) | Q(caja__empresa_id=empresa_id))
        if sucursal_id:
            qs = qs.filter(caja__sucursal_id=sucursal_id)

        job = qs.first()
        if not job:
            return JsonResponse({'error': 'Trabajo no encontrado'}, status=404)

        job.estado = status
        job.fecha_impresion = timezone.now()
        job.intentos += 1

        if error_msg:
            job.error_log = error_msg

        job.save()
        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Experiencia para usuario final: código de vinculación (sin IDs ni URLs)
# ---------------------------------------------------------------------------

import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.decorators import requiere_empresa
from empresas.middleware import resolver_sucursal_operativa
from .models import CodigoVinculoImpresion

_ALFABETO_CODIGO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def _nuevo_codigo():
    for _ in range(20):
        codigo = ''.join(secrets.choice(_ALFABETO_CODIGO) for _ in range(6))
        if not CodigoVinculoImpresion.objects.filter(codigo=codigo).exists():
            return codigo
    raise RuntimeError('No se pudo generar un código único')


def _url_api_impresion(request):
    return request.build_absolute_uri('/caja/api/impresion').rstrip('/')


@login_required
@requiere_empresa
@permission_required('caja.view_caja', raise_exception=True)
def conectar_impresora(request):
    """Pantalla simple: sucursal + caja → código para el agente."""
    empresa = request.empresa
    sucursales = empresa.sucursales.filter(estado='activa').order_by('nombre')
    sucursal_actual = resolver_sucursal_operativa(request)

    sucursal_id = request.POST.get('sucursal_id') or request.GET.get('sucursal_id')
    sucursal = sucursales.filter(id=sucursal_id).first() if sucursal_id else sucursal_actual
    if sucursal and sucursal.empresa_id != empresa.id:
        sucursal = sucursal_actual
    if sucursal is None:
        sucursal = sucursales.first()

    cajas = Caja.objects.filter(empresa=empresa, sucursal=sucursal, activo=True).order_by('numero', 'nombre') if sucursal else Caja.objects.none()

    codigo_mostrado = None
    caja_vinculada = None
    error = None

    if request.method == 'POST':
        caja_id = request.POST.get('caja_id')
        caja = cajas.filter(id=caja_id).first()
        if not sucursal:
            error = 'Seleccione una sucursal.'
        elif not caja:
            error = 'Seleccione la caja de esa sucursal.'
        else:
            codigo_mostrado = _nuevo_codigo()
            caja_vinculada = caja
            CodigoVinculoImpresion.objects.create(
                codigo=codigo_mostrado,
                empresa=empresa,
                sucursal=sucursal,
                caja=caja,
                api_base_url=_url_api_impresion(request),
                creado_por=request.user,
                fecha_expiracion=timezone.now() + timedelta(hours=24),
            )

    return render(request, 'caja/conectar_impresora.html', {
        'empresa': empresa,
        'sucursales': sucursales,
        'sucursal': sucursal,
        'cajas': cajas,
        'codigo': codigo_mostrado,
        'caja_vinculada': caja_vinculada,
        'error': error,
    })


@login_required
@requiere_empresa
@require_GET
def descargar_agente(request):
    """Entrega el programa Windows (.exe) listo para doble clic."""
    import io
    import json as json_mod
    import zipfile

    exe_candidatos = [
        Path(settings.BASE_DIR) / 'static' / 'descargas' / 'AgenteImpresion.exe',
        Path(settings.BASE_DIR) / 'dist' / 'AgenteImpresion.exe',
    ]
    ruta_exe = next((p for p in exe_candidatos if p.exists()), None)
    if not ruta_exe:
        raise Http404(
            'El programa de impresión aún no está generado. '
            'En el servidor ejecute: pyinstaller --noconfirm AgenteImpresion.spec'
        )

    config_inicial = json_mod.dumps({
        'impresora': '',
        'empresa_id': '',
        'sucursal_id': '',
        'caja_id': '',
        'empresa': '',
        'sucursal': '',
        'caja': '',
        'api_base_url': _url_api_impresion(request),
        'auto_start': True,
    }, indent=2)

    abrir_bat = (
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        'start "" "AgenteImpresion.exe"\r\n'
    )
    leer_txt = (
        '1. Descomprima esta carpeta.\r\n'
        '2. Haga doble clic en AgenteImpresion.exe (o en Abrir impresora.bat).\r\n'
        '3. Escriba el codigo de 6 letras que le mostro GestionCloud.\r\n'
        '4. Elija la impresora e Iniciar.\r\n'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(ruta_exe, arcname='AgenteImpresion.exe')
        zf.writestr('config_impresora.json', config_inicial)
        zf.writestr('Abrir impresora.bat', abrir_bat)
        zf.writestr('Leame.txt', leer_txt)
    buf.seek(0)

    from django.http import HttpResponse
    response = HttpResponse(buf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="ImpresoraGestionCloud.zip"'
    return response


@csrf_exempt
@require_http_methods(["GET"])
def vincular_agente(request):
    """El agente solo envía el código; recibe empresa, sucursal y caja ya resueltas."""
    codigo = (request.GET.get('codigo') or '').strip().upper()
    if len(codigo) < 4:
        return JsonResponse({'ok': False, 'mensaje': 'Ingrese el código que le mostró GestionCloud.'}, status=400)

    vinculo = (
        CodigoVinculoImpresion.objects
        .select_related('empresa', 'sucursal', 'caja')
        .filter(codigo=codigo)
        .first()
    )
    if not vinculo or not vinculo.vigente():
        return JsonResponse({
            'ok': False,
            'mensaje': 'Ese código no es válido o ya venció. Pida uno nuevo en GestionCloud.',
        }, status=400)

    return JsonResponse({
        'ok': True,
        'empresa_id': vinculo.empresa_id,
        'sucursal_id': vinculo.sucursal_id,
        'caja_id': vinculo.caja_id,
        'empresa': vinculo.empresa.nombre,
        'sucursal': vinculo.sucursal.nombre,
        'caja': f'{vinculo.caja.numero} — {vinculo.caja.nombre}',
        'api_base_url': vinculo.api_base_url,
    })
