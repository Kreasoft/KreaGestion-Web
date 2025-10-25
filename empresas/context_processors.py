from .models import Empresa

def empresa_context(request):
    context = {
        'empresa_actual': None,
        'todas_las_empresas': None
    }
    if request.user.is_authenticated:
        empresa_id = request.session.get('empresa_activa_id')
        if empresa_id:
            try:
                context['empresa_actual'] = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                pass
        
        if request.user.is_superuser:
            context['todas_las_empresas'] = list(Empresa.objects.values('id', 'nombre'))
            
    return context
