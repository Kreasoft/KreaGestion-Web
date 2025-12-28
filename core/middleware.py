"""
Middleware centralizado para gestión de empresa y sesión
Este middleware asigna automáticamente la empresa al request, sin necesidad de decoradores
"""
from django.shortcuts import redirect
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)


class EmpresaMiddleware:
    """
    Middleware que asigna automáticamente la empresa al request.
    Esto elimina la necesidad de usar @requiere_empresa en cada vista.
    
    COMPORTAMIENTO:
    - Para superusuarios: Obtiene empresa de sesión o asigna por defecto
    - Para usuarios normales: Obtiene empresa del perfil
    - Asigna request.empresa en TODAS las requests autenticadas
    - Maneja sesión de forma robusta con session.modified
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Solo procesar si el usuario está autenticado
        if request.user.is_authenticated:
            self._asignar_empresa(request)
        
        response = self.get_response(request)
        return response
    
    def _asignar_empresa(self, request):
        """
        Asigna la empresa al request basándose en el tipo de usuario.
        """
        from empresas.models import Empresa
        
        empresa = None
        
        # CASO 1: Superusuario
        if request.user.is_superuser:
            # Intentar obtener de sesión
            empresa_id = request.session.get('empresa_activa')
            
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                    logger.debug(f"[MIDDLEWARE] Empresa desde sesión: {empresa.nombre}")
                except Empresa.DoesNotExist:
                    logger.warning(f"[MIDDLEWARE] Empresa ID {empresa_id} en sesión no existe")
                    empresa = None
            
            # Si no hay empresa en sesión, buscar empresa por defecto
            if not empresa:
                # Buscar Kreasoft primero
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
                
                # Si no existe, buscar cualquier empresa con nombre
                if not empresa:
                    empresa = Empresa.objects.exclude(nombre='').first()
                
                # Como último recurso, la primera empresa
                if not empresa:
                    empresa = Empresa.objects.first()
                
                if empresa:
                    logger.debug(f"[MIDDLEWARE] Empresa asignada por defecto: {empresa.nombre}")
            
            # Guardar en sesión de forma robusta
            if empresa:
                request.session['empresa_activa'] = empresa.id
                request.session.modified = True  # CRÍTICO: Forzar guardado
                request.empresa = empresa
        
        # CASO 2: Usuario normal
        else:
            try:
                # Obtener empresa del perfil
                if hasattr(request.user, 'perfil') and request.user.perfil:
                    empresa = request.user.perfil.empresa
                    
                    if empresa:
                        logger.debug(f"[MIDDLEWARE] Empresa del perfil: {empresa.nombre}")
                        request.empresa = empresa
                    else:
                        logger.warning(f"[MIDDLEWARE] Usuario {request.user.username} sin empresa asignada")
                else:
                    logger.warning(f"[MIDDLEWARE] Usuario {request.user.username} sin perfil")
                    
            except Exception as e:
                logger.exception(f"[MIDDLEWARE] Error al obtener empresa para {request.user.username}: {e}")
        
        # Validar que se asignó empresa
        if not hasattr(request, 'empresa') or not request.empresa:
            logger.warning(f"[MIDDLEWARE] No se pudo asignar empresa para {request.user.username}")
        else:
            logger.debug(f"[MIDDLEWARE] Empresa asignada: {request.empresa.nombre}")


class SucursalMiddleware:
    """
    Middleware que asigna la sucursal activa al request.
    Útil para usuarios que trabajan en sucursales específicas.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Solo procesar si hay empresa y usuario autenticado
        if request.user.is_authenticated and hasattr(request, 'empresa'):
            self._asignar_sucursal(request)
        
        response = self.get_response(request)
        return response
    
    def _asignar_sucursal(self, request):
        """
        Asigna la sucursal activa al request.
        """
        from empresas.models import Sucursal
        
        try:
            # Obtener sucursal de sesión
            sucursal_id = request.session.get('sucursal_activa')
            
            if sucursal_id:
                try:
                    sucursal = Sucursal.objects.get(id=sucursal_id, empresa=request.empresa)
                    request.sucursal_activa = sucursal
                    logger.debug(f"[MIDDLEWARE] Sucursal activa: {sucursal.nombre}")
                    return
                except Sucursal.DoesNotExist:
                    logger.warning(f"[MIDDLEWARE] Sucursal ID {sucursal_id} no existe")
            
            # Si no hay sucursal en sesión, buscar sucursal del usuario
            if hasattr(request.user, 'perfil') and request.user.perfil:
                if hasattr(request.user.perfil, 'sucursal') and request.user.perfil.sucursal:
                    sucursal = request.user.perfil.sucursal
                    request.sucursal_activa = sucursal
                    request.session['sucursal_activa'] = sucursal.id
                    request.session.modified = True
                    logger.debug(f"[MIDDLEWARE] Sucursal desde perfil: {sucursal.nombre}")
                    return
            
            # Si no hay sucursal del usuario, buscar sucursal casa matriz
            sucursal_casa_matriz = Sucursal.objects.filter(
                empresa=request.empresa,
                es_principal=True
            ).first()
            
            if sucursal_casa_matriz:
                request.sucursal_activa = sucursal_casa_matriz
                request.session['sucursal_activa'] = sucursal_casa_matriz.id
                request.session.modified = True
                logger.debug(f"[MIDDLEWARE] Sucursal casa matriz: {sucursal_casa_matriz.nombre}")
            
        except Exception as e:
            logger.exception(f"[MIDDLEWARE] Error al asignar sucursal: {e}")

