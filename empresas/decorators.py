from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def requiere_empresa(view_func):
    """
    Decorador que verifica que el usuario tenga una empresa seleccionada
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Superusuarios pueden acceder sin empresa
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not hasattr(request, 'empresa') or not request.empresa:
            messages.warning(request, 'Debes seleccionar una empresa para continuar.')
            return redirect('empresas:empresa_list')
        return view_func(request, *args, **kwargs)
    return wrapper
