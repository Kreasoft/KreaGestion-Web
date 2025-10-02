from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def requiere_empresa(view_func):
    """
    Decorador que verifica que el usuario tenga una empresa seleccionada
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        print(f"DEBUG - Decorador requiere_empresa ejecutándose para {view_func.__name__}")
        print(f"DEBUG - Usuario: {request.user}")
        print(f"DEBUG - hasattr empresa: {hasattr(request, 'empresa')}")
        if hasattr(request, 'empresa'):
            print(f"DEBUG - Empresa: {request.empresa}")
        
        # Superusuarios pueden acceder sin empresa
        if request.user.is_superuser:
            print("DEBUG - Usuario es superusuario, permitiendo acceso")
            return view_func(request, *args, **kwargs)
        
        if not hasattr(request, 'empresa') or not request.empresa:
            print("DEBUG - No hay empresa, redirigiendo")
            messages.warning(request, 'Debes seleccionar una empresa para continuar.')
            return redirect('empresas:empresa_list')
        
        print("DEBUG - Empresa válida, ejecutando vista")
        return view_func(request, *args, **kwargs)
    return wrapper
