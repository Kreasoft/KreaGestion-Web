"""
Decoradores centralizados para control de acceso y gestión de empresa
VERSIÓN CONSOLIDADA Y ROBUSTA - Usada por todos los módulos del sistema
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


def requiere_empresa(view_func):
    """
    Decorador centralizado que verifica y asigna empresa al request.
    
    COMPORTAMIENTO:
    - Para superusuarios: Obtiene empresa de sesión o asigna empresa por defecto
    - Para usuarios normales: Obtiene empresa del perfil del usuario
    - Siempre asigna request.empresa si es válida
    - Guarda empresa en sesión de forma robusta
    
    IMPORTANTE: Este es el ÚNICO decorador @requiere_empresa que debe usarse.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        from empresas.models import Empresa
        
        # Validar autenticación
        if not request.user.is_authenticated:
            logger.warning(f"Acceso no autenticado a {view_func.__name__}")
            return redirect('login')
        
        empresa = None
        
        # CASO 1: Superusuario
        if request.user.is_superuser:
            logger.debug(f"[SUPERUSER] Acceso de superusuario a {view_func.__name__}")
            
            # Intentar obtener de sesión
            empresa_id = request.session.get('empresa_activa')
            
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                    logger.debug(f"[SUPERUSER] Empresa desde sesión: {empresa.nombre}")
                except Empresa.DoesNotExist:
                    logger.warning(f"[SUPERUSER] Empresa ID {empresa_id} en sesión no existe")
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
                    logger.info(f"[SUPERUSER] Empresa asignada por defecto: {empresa.nombre}")
                else:
                    logger.error("[SUPERUSER] No hay empresas en el sistema")
                    messages.error(request, 'No hay empresas registradas en el sistema.')
                    return redirect('empresas:empresa_create')
            
            # Guardar en sesión de forma robusta
            if empresa:
                request.session['empresa_activa'] = empresa.id
                request.session.modified = True
                request.empresa = empresa
        
        # CASO 2: Usuario normal
        else:
            logger.debug(f"[USER] Acceso de usuario normal a {view_func.__name__}: {request.user.username}")
            
            try:
                # Obtener empresa del perfil
                if hasattr(request.user, 'perfil') and request.user.perfil:
                    empresa = request.user.perfil.empresa
                    
                    if not empresa:
                        logger.error(f"[USER] Usuario {request.user.username} sin empresa asignada")
                        messages.error(request, 'No tiene empresa asignada. Contacte al administrador.')
                        return redirect('logout')
                    
                    logger.debug(f"[USER] Empresa del perfil: {empresa.nombre}")
                    request.empresa = empresa
                else:
                    logger.error(f"[USER] Usuario {request.user.username} sin perfil")
                    messages.error(request, 'Usuario sin perfil configurado. Contacte al administrador.')
                    return redirect('logout')
                    
            except Exception as e:
                logger.exception(f"[USER] Error al obtener empresa para {request.user.username}: {e}")
                messages.error(request, 'Error al obtener información de empresa.')
                return redirect('logout')
        
        # Validar que se asignó empresa
        if not hasattr(request, 'empresa') or not request.empresa:
            logger.error(f"No se pudo asignar empresa para {request.user.username} en {view_func.__name__}")
            messages.error(request, 'No se pudo determinar la empresa. Contacte al administrador.')
            return redirect('logout')
        
        logger.debug(f"[OK] Empresa asignada: {request.empresa.nombre} para vista {view_func.__name__}")
        
        # Ejecutar vista
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def solo_superusuario(view_func):
    """
    Decorador que solo permite acceso a superusuarios.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            logger.warning(f"Acceso no autenticado a vista restringida: {view_func.__name__}")
            return redirect('login')
        
        if not request.user.is_superuser:
            logger.warning(f"Usuario {request.user.username} intentó acceder a vista de superusuario: {view_func.__name__}")
            messages.error(request, 'Acceso denegado. Solo administradores pueden realizar esta acción.')
            raise PermissionDenied("Acceso denegado")
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def requiere_empresa_json(view_func):
    """
    Decorador para vistas API que retornan JSON.
    Similar a requiere_empresa pero retorna JsonResponse en caso de error.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        from empresas.models import Empresa
        
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'No autenticado'}, status=401)
        
        empresa = None
        
        if request.user.is_superuser:
            empresa_id = request.session.get('empresa_activa')
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                except Empresa.DoesNotExist:
                    empresa = None
            
            if not empresa:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
                if not empresa:
                    empresa = Empresa.objects.exclude(nombre='').first()
                if not empresa:
                    empresa = Empresa.objects.first()
            
            if empresa:
                request.session['empresa_activa'] = empresa.id
                request.session.modified = True
                request.empresa = empresa
        else:
            try:
                if hasattr(request.user, 'perfil') and request.user.perfil:
                    empresa = request.user.perfil.empresa
                    if empresa:
                        request.empresa = empresa
            except:
                pass
        
        if not hasattr(request, 'empresa') or not request.empresa:
            return JsonResponse({'success': False, 'error': 'No se pudo determinar la empresa'}, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

