from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from .models import Sucursal
from django.contrib import messages
from django.urls import reverse

class EmpresaEstadoMiddleware(MiddlewareMixin):
    """
    Middleware para verificar el estado de la empresa (SaaS).
    Si la empresa está suspendida (por falta de pago), impide el acceso a vistas operativas.
    """
    
    def process_request(self, request):
        # 1. Ignorar si no ha iniciado sesión o no tiene empresa activa
        if not request.user.is_authenticated or not hasattr(request, 'empresa') or not request.empresa:
            return
            
        # 2. El Administrador Global (Django Admin) siempre debe tener acceso
        if request.path.startswith('/admin/'):
            return
            
        # 3. Lista de URLs que siempre deben funcionar (mantenimiento y login)
        # Usamos nombres parciales y rutas para mayor seguridad
        path = request.path
        whitelist = [
            '/accounts/logout/', 
            '/accounts/login/', 
            '/empresas/suspendida/', 
            '/empresas/seleccionar-plan/',
            '/empresas/seleccionar-empresa/',
        ]
        
        for item in whitelist:
            if item in path:
                return

        # 4. Verificar estado de la empresa
        if request.empresa.estado == 'suspendida':
            # Solo permitir ver la página de suspensión
            # Evitamos que superusuarios sean bloqueados SI están en el dashboard principal de admin
            # Pero los bloqueamos en el POS/Ventas para que puedan PROBAR la función
            if not request.user.is_superuser or '/admin/' not in path:
                 if '/empresas/suspendida/' not in path:
                    return redirect('empresas:empresa_suspendida')

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
