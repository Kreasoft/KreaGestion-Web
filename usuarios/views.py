from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import PerfilUsuario
from empresas.models import Empresa
from empresas.decorators import requiere_empresa


def obtener_empresa_usuario(request):
    """Obtener la empresa del usuario con lógica de sesión para superusuarios"""
    if request.user.is_superuser:
        # Para superusuarios, usar empresa de sesión o Kreasoft por defecto
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        
        if not empresa:
            empresa = Empresa.objects.first()
        
        if not empresa:
            return None, 'No hay empresas configuradas en el sistema.'
            
        # Guardar empresa en sesión
        request.session['empresa_activa'] = empresa.id
        return empresa, None
    else:
        # Para usuarios normales, usar su empresa asociada
        try:
            empresa = request.user.perfil.empresa
            return empresa, None
        except:
            return None, 'Usuario no tiene empresa asociada.'


@login_required
@requiere_empresa
def usuario_list(request):
    """Lista de usuarios de la empresa con control de roles"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    
    # Filtros
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    grupo = request.GET.get('grupo', '')
    
    # Query base - obtener usuarios que tienen perfil en esta empresa
    usuarios = User.objects.filter(perfil__empresa=empresa).select_related('perfil')
    
    # Aplicar filtros
    if search:
        usuarios = usuarios.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    
    if estado == 'activo':
        usuarios = usuarios.filter(perfil__es_activo=True, is_active=True)
    elif estado == 'inactivo':
        usuarios = usuarios.filter(Q(perfil__es_activo=False) | Q(is_active=False))
    
    if grupo:
        usuarios = usuarios.filter(groups__id=grupo)
    
    # Ordenamiento
    usuarios = usuarios.order_by('first_name', 'last_name', 'username')
    
    # Paginación
    paginator = Paginator(usuarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    stats = {
        'total_usuarios': User.objects.filter(perfil__empresa=empresa).count(),
        'usuarios_activos': User.objects.filter(perfil__empresa=empresa, perfil__es_activo=True, is_active=True).count(),
        'usuarios_inactivos': User.objects.filter(perfil__empresa=empresa).filter(Q(perfil__es_activo=False) | Q(is_active=False)).count(),
        'superusuarios': User.objects.filter(perfil__empresa=empresa, is_superuser=True).count(),
    }
    
    # Grupos disponibles para filtro
    grupos = Group.objects.all().order_by('name')
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'empresa': empresa,
        'grupos': grupos,
        'search': search,
        'estado': estado,
        'grupo': grupo,
        'titulo': 'Gestión de Usuarios',
    }
    
    return render(request, 'usuarios/usuario_list.html', context)


@login_required
@require_POST
def usuario_toggle_estado(request, user_id):
    """Activar/desactivar usuario"""
    try:
        usuario = get_object_or_404(User, id=user_id)
        
        # Verificar que el usuario pertenece a la misma empresa
        empresa, error = obtener_empresa_usuario(request)
        if error:
            return JsonResponse({'error': error}, status=400)
            
        if usuario.perfil.empresa != empresa:
            return JsonResponse({'success': False, 'message': 'No tienes permisos para modificar este usuario.'})
        
        # Cambiar estado
        if usuario.is_active:
            usuario.is_active = False
            usuario.perfil.es_activo = False
            estado = 'desactivado'
        else:
            usuario.is_active = True
            usuario.perfil.es_activo = True
            estado = 'activado'
        
        usuario.save()
        usuario.perfil.save()
        
        return JsonResponse({'success': True, 'message': f'Usuario {estado} correctamente.'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required
@require_POST
def usuario_asignar_grupo(request, user_id):
    """Asignar grupo a usuario"""
    try:
        usuario = get_object_or_404(User, id=user_id)
        grupo_id = request.POST.get('grupo_id')
        
        # Verificar que el usuario pertenece a la misma empresa
        empresa, error = obtener_empresa_usuario(request)
        if error:
            return JsonResponse({'error': error}, status=400)
            
        if usuario.perfil.empresa != empresa:
            return JsonResponse({'success': False, 'message': 'No tienes permisos para modificar este usuario.'})
        
        # Limpiar grupos actuales
        usuario.groups.clear()
        
        # Asignar nuevo grupo si se especifica
        if grupo_id and grupo_id != '':
            grupo = get_object_or_404(Group, id=grupo_id)
            usuario.groups.add(grupo)
            message = f'Usuario asignado al grupo "{grupo.name}" correctamente.'
        else:
            message = 'Grupo removido del usuario correctamente.'
        
        usuario.save()
        
        return JsonResponse({'success': True, 'message': message})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
