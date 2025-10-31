"""
API endpoints para la app de empresas
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .models import Empresa


@login_required
@require_http_methods(["GET"])
def api_configuracion(request):
    """
    API para obtener la configuracion de la empresa activa
    """
    empresa_id = None
    if hasattr(request, 'empresa') and request.empresa:
        empresa_id = request.empresa.id
    else:
        empresa_id = request.session.get('empresa_activa_id') or request.session.get('empresa_activa')
    
    if not empresa_id:
        return JsonResponse({
            'success': False,
            'error': 'No hay empresa activa en la sesion'
        }, status=400)
    
    try:
        empresa = Empresa.objects.get(id=empresa_id)
        usa_despacho_movil = getattr(empresa, 'usa_despacho_movil', False)
        
        return JsonResponse({
            'success': True,
            'usa_produccion': empresa.usa_produccion,
            'usa_despacho_movil': usa_despacho_movil,
            'tipo_industria': empresa.tipo_industria
        })
    except Empresa.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Empresa no encontrada'
        }, status=404)


