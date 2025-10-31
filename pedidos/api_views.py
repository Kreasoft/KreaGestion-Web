"""
API endpoints para la app de pedidos
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .models_transporte import Vehiculo, Chofer


@login_required
@require_http_methods(["GET"])
def api_vehiculos(request):
    """
    API para obtener lista de vehículos activos de la empresa
    """
    # Obtener empresa_id de la sesión o del atributo request.empresa
    empresa_id = None
    if hasattr(request, 'empresa') and request.empresa:
        empresa_id = request.empresa.id
    else:
        empresa_id = request.session.get('empresa_activa_id') or request.session.get('empresa_activa')
    
    if not empresa_id:
        return JsonResponse({
            'success': False,
            'error': 'No hay empresa activa en la sesión'
        }, status=400)
    
    vehiculos = Vehiculo.objects.filter(
        empresa_id=empresa_id,
        activo=True
    ).values('id', 'patente', 'descripcion').order_by('patente')
    
    return JsonResponse({
        'success': True,
        'vehiculos': list(vehiculos)
    })


@login_required
@require_http_methods(["GET"])
def api_choferes(request):
    """
    API para obtener lista de choferes activos de la empresa
    """
    # Obtener empresa_id de la sesión o del atributo request.empresa
    empresa_id = None
    if hasattr(request, 'empresa') and request.empresa:
        empresa_id = request.empresa.id
    else:
        empresa_id = request.session.get('empresa_activa_id') or request.session.get('empresa_activa')
    
    if not empresa_id:
        return JsonResponse({
            'success': False,
            'error': 'No hay empresa activa en la sesión'
        }, status=400)
    
    choferes = Chofer.objects.filter(
        empresa_id=empresa_id,
        activo=True
    ).values('id', 'nombre', 'rut').order_by('nombre')
    
    return JsonResponse({
        'success': True,
        'choferes': list(choferes)
    })
