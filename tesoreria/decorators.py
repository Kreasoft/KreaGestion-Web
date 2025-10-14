from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def requiere_empresa(view_func):
    """Decorador que verifica que el usuario tenga empresa asociada"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        from empresas.models import Empresa
        
        if request.user.is_superuser:
            # Para superusuarios, obtener empresa de sesión o usar Kreasoft
            empresa_id = request.session.get('empresa_activa')
            
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                except Empresa.DoesNotExist:
                    empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
                    if not empresa:
                        empresa = Empresa.objects.exclude(nombre='').first()
                    if not empresa:
                        empresa = Empresa.objects.first()
            else:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
                if not empresa:
                    empresa = Empresa.objects.exclude(nombre='').first()
                if not empresa:
                    empresa = Empresa.objects.first()
            
            if empresa:
                request.session['empresa_activa'] = empresa.id
                request.empresa = empresa
        else:
            try:
                empresa = request.user.perfil.empresa
                if not empresa:
                    messages.error(request, 'Usuario no tiene empresa asociada.')
                    return redirect('dashboard')
                request.empresa = empresa
            except:
                messages.error(request, 'Usuario no tiene empresa asociada.')
                return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view








