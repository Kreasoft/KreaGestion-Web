from django.utils.deprecation import MiddlewareMixin
from .models import Sucursal


class SucursalMiddleware(MiddlewareMixin):
    """
    Middleware para gestionar la sucursal activa del usuario.
    
    Comportamiento:
    - Usuarios normales (vendedores, cajeros): Usan su sucursal asignada en el perfil
    - Supervisores/Superusuarios: Pueden cambiar de sucursal manualmente
    """
    
    def process_request(self, request):
        # Inicializar sucursal_activa
        request.sucursal_activa = None
        request.puede_cambiar_sucursal = False
        
        # Solo procesar si el usuario está autenticado y tiene empresa
        if not request.user.is_authenticated or not hasattr(request, 'empresa'):
            return
        
        # Verificar si el usuario puede cambiar de sucursal manualmente
        puede_cambiar = (
            request.user.is_superuser or 
            (hasattr(request.user, 'perfil') and 
             hasattr(request.user.perfil, 'tipo_usuario') and 
             request.user.perfil.tipo_usuario in ['administrador'])
        )
        
        request.puede_cambiar_sucursal = puede_cambiar
        
        if puede_cambiar:
            # Superusuarios/Administradores: Pueden seleccionar sucursal manualmente
            sucursal_id = request.session.get('sucursal_filtro_id')
            
            if sucursal_id:
                try:
                    sucursal = Sucursal.objects.get(
                        id=sucursal_id,
                        empresa=request.empresa,
                        estado='activa'
                    )
                    request.sucursal_activa = sucursal
                except Sucursal.DoesNotExist:
                    # Limpiar sesión si la sucursal no existe
                    if 'sucursal_filtro_id' in request.session:
                        del request.session['sucursal_filtro_id']
        else:
            # Usuarios normales: Usar sucursal de su perfil automáticamente
            if hasattr(request.user, 'perfil') and request.user.perfil:
                sucursal_perfil = request.user.perfil.sucursal
                if sucursal_perfil and sucursal_perfil.estado == 'activa':
                    request.sucursal_activa = sucursal_perfil
