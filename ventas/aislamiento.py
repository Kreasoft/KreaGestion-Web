"""Aislamiento SaaS: estación, caja e impresora no se comparten entre empresas."""

from django.db.models import F

POS_SESSION_KEYS = (
    'pos_estacion_id',
    'pos_estacion_nombre',
    'pos_vendedor_id',
    'pos_vendedor_nombre',
    'pos_nombre_estacion',
    'pos_bodega_id',
    'pos_cierre_directo',
    'pos_flujo_directo',
    'pos_enviar_sii_directo',
)

TENANT_SESSION_KEYS = POS_SESSION_KEYS + (
    'sucursal_activa',
    'sucursal_filtro_id',
    'dashboard_bodega_id',
)

COOKIE_TERMINAL_POS = 'gc_pos_terminal'

_SANEO_HECHO = False


def limpiar_sesion_pos(session):
    for clave in POS_SESSION_KEYS:
        session.pop(clave, None)


def limpiar_contexto_empresa(session):
    """Al cambiar de empresa se olvida sucursal, bodega y POS de la anterior."""
    for clave in TENANT_SESSION_KEYS:
        session.pop(clave, None)


def borrar_cookie_terminal(response):
    response.delete_cookie(COOKIE_TERMINAL_POS, path='/')
    return response


def asegurar_sesion_pos_de_empresa(request):
    """Si la estación de la sesión no es de la empresa activa, se olvida el POS."""
    empresa = getattr(request, 'empresa', None)
    estacion_id = request.session.get('pos_estacion_id')
    if not estacion_id:
        return
    if empresa is None:
        limpiar_sesion_pos(request.session)
        request.session.modified = True
        return
    from ventas.models import EstacionTrabajo
    if not EstacionTrabajo.objects.filter(pk=estacion_id, empresa=empresa).exists():
        limpiar_sesion_pos(request.session)
        request.session.modified = True


def estacion_de_empresa(empresa, estacion_id):
    if not empresa or not estacion_id:
        return None
    from ventas.models import EstacionTrabajo
    return EstacionTrabajo.objects.filter(pk=estacion_id, empresa=empresa).first()


def sanear_referencias_estaciones():
    """Quita FKs de estación/caja/impresora que apuntan a otra empresa."""
    global _SANEO_HECHO
    if _SANEO_HECHO:
        return 0
    from ventas.models import EstacionTrabajo, TerminalPOS
    from caja.models import Caja

    tocadas = 0
    tocadas += EstacionTrabajo.objects.filter(caja_impresion__isnull=False).exclude(
        caja_impresion__empresa_id=F('empresa_id')
    ).update(caja_impresion=None)
    tocadas += EstacionTrabajo.objects.filter(impresora_vales__isnull=False).exclude(
        impresora_vales__empresa_id=F('empresa_id')
    ).update(impresora_vales=None)
    tocadas += EstacionTrabajo.objects.filter(sucursal__isnull=False).exclude(
        sucursal__empresa_id=F('empresa_id')
    ).update(sucursal=None)
    tocadas += Caja.objects.filter(estacion_trabajo__isnull=False).exclude(
        estacion_trabajo__empresa_id=F('empresa_id')
    ).update(estacion_trabajo=None)
    tocadas += TerminalPOS.objects.filter(sucursal__isnull=False).exclude(
        sucursal__empresa_id=F('empresa_id')
    ).update(sucursal=None)
    tocadas += TerminalPOS.objects.filter(bodega__isnull=False).exclude(
        bodega__empresa_id=F('empresa_id')
    ).update(bodega=None)
    tocadas += TerminalPOS.objects.filter(vendedor__isnull=False).exclude(
        vendedor__empresa_id=F('empresa_id')
    ).update(vendedor=None)
    tocadas += TerminalPOS.objects.filter(estacion__isnull=False).exclude(
        estacion__empresa_id=F('empresa_id')
    ).update(activo=False)
    _SANEO_HECHO = True
    return tocadas
