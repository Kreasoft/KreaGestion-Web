"""Páginas de error con mensaje propio de GestionCloud."""
from django.shortcuts import render


def permiso_denegado(request, exception=None):
    """
    403: el usuario autenticado no tiene el permiso de la opción que abrió.
    Distinto de un fallo del sistema: es control de acceso por perfil/rol.
    """
    detalle = str(exception).strip() if exception else ''
    if detalle.lower() in ('', 'acceso denegado', 'forbidden', '403 forbidden'):
        detalle = ''
    return render(request, '403.html', {
        'es_csrf': False,
        'detalle_permiso': detalle,
    }, status=403)


def csrf_invalido(request, reason=''):
    """Token de seguridad vencido o envío inválido; no es falta de permiso."""
    return render(request, '403.html', {
        'es_csrf': True,
        'detalle_permiso': '',
        'csrf_reason': reason,
    }, status=403)
