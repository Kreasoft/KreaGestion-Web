"""
API endpoints para la app de ventas
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .models import Vendedor


@login_required
@require_http_methods(["GET"])
def api_vendedores(request):
    """
    API para obtener lista de vendedores activos de la empresa
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
    
    vendedores = Vendedor.objects.filter(
        empresa_id=empresa_id,
        activo=True
    ).values('id', 'nombre', 'codigo').order_by('nombre')
    
    # Obtener vendedor por defecto (usuario actual si tiene vendedor asignado)
    vendedor_defecto_id = None
    if hasattr(request.user, 'perfilusuario') and hasattr(request.user.perfilusuario, 'vendedor') and request.user.perfilusuario.vendedor:
        vendedor_defecto_id = request.user.perfilusuario.vendedor.id
    
    return JsonResponse({
        'success': True,
        'vendedores': list(vendedores),
        'vendedor_defecto_id': vendedor_defecto_id
    })




