from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def requiere_empresa(view_func):
    """Decorador que verifica que el usuario tenga empresa asociada"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            try:
                empresa = request.user.perfil.empresa
                if not empresa:
                    messages.error(request, 'Usuario no tiene empresa asociada.')
                    return redirect('dashboard')
            except:
                messages.error(request, 'Usuario no tiene empresa asociada.')
                return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view






