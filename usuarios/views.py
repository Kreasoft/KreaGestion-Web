from utilidades.utils import clean_id
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from .models import PerfilUsuario
from .forms import UsuarioCreateForm, UsuarioUpdateForm, GrupoForm
from empresas.models import Empresa
from core.decorators import requiere_empresa, requiere_permiso


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
    print(f"=== DEBUG LISTA USUARIOS ===")
    print(f"Empresa actual: {empresa.nombre} (ID: {empresa.id})")
    
    # Debug: mostrar todos los usuarios con perfil
    todos_usuarios = User.objects.filter(perfil__isnull=False).select_related('perfil')
    print(f"Total usuarios con perfil: {todos_usuarios.count()}")
    for u in todos_usuarios:
        print(f"  - {u.username} -> Empresa: {u.perfil.empresa.nombre} (ID: {u.perfil.empresa.id})")
    
    usuarios = User.objects.filter(perfil__empresa=empresa).select_related('perfil')
    print(f"Usuarios filtrados para empresa {empresa.nombre}: {usuarios.count()}")
    
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
        grupo_id = clean_id(request.POST.get('grupo_id'))
        
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


@login_required
@requiere_empresa
@requiere_permiso('auth.add_user', mensaje='No tienes permisos para crear usuarios. Solo los administradores pueden realizar esta acción.', redirect_url='usuarios:usuario_list')
def usuario_create(request):
    """Crear nuevo usuario"""
    import traceback
    from django.http import JsonResponse
    
    empresa, error = obtener_empresa_usuario(request)
    if error:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error}, status=400)
        messages.error(request, error)
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UsuarioCreateForm(request.POST)
        
        if form.is_valid():
            try:
                usuario = form.save()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Usuario "{usuario.username}" creado exitosamente.',
                        'redirect': False
                    })
                
                messages.success(request, f'Usuario "{usuario.username}" creado exitosamente.')
                return redirect('usuarios:usuario_list')
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'Error al crear usuario: {str(e)}'
                    }, status=400)
                print(f"Error al guardar: {str(e)}")
                print(traceback.format_exc())
                messages.error(request, f'Error al crear usuario: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                for field, field_errors in form.errors.items():
                    errors[field] = field_errors
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'error': 'Por favor corrige los errores en el formulario.'
                }, status=400)
            
            # Mostrar todos los errores del formulario
            print(f"Errores del formulario: {form.errors}")
            print(f"Non field errors: {form.non_field_errors()}")
            
            # Agregar mensaje general de error
            messages.error(request, 'Por favor corrige los errores en el formulario.')
            
            # Mostrar errores específicos de cada campo
            for field, errors in form.errors.items():
                field_label = form.fields[field].label if field in form.fields else field
                for error in errors:
                    messages.error(request, f'{field_label}: {error}')
    else:
        # Precargar la empresa actual
        form = UsuarioCreateForm(initial={'empresa': empresa})
        # Filtrar sucursales por la empresa
        if empresa:
            form.fields['sucursal'].queryset = empresa.sucursales.filter(estado='activa').order_by('nombre')
    
    context = {
        'form': form,
        'titulo': 'Crear Nuevo Usuario',
        'empresa': empresa,
    }
    
    # Si es AJAX, devolver solo el formulario
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'usuarios/usuario_form_modal.html', context)
    
    return render(request, 'usuarios/usuario_form.html', context)


@login_required
@requiere_empresa
@requiere_permiso('auth.change_user', mensaje='No tienes permisos para editar usuarios. Solo los administradores pueden realizar esta acción.', redirect_url='usuarios:usuario_list')
def usuario_edit(request, user_id):
    """Editar usuario existente"""
    from django.http import JsonResponse
    
    empresa, error = obtener_empresa_usuario(request)
    if error:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error}, status=400)
        messages.error(request, error)
        return redirect('dashboard')
    
    usuario = get_object_or_404(User, id=user_id)
    
    # Verificar que el usuario pertenece a la misma empresa
    if not usuario.is_superuser and usuario.perfil.empresa != empresa:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'No tienes permisos para editar este usuario.'}, status=403)
        messages.error(request, 'No tienes permisos para editar este usuario.')
        return redirect('usuarios:usuario_list')
    
    if request.method == 'POST':
        form = UsuarioUpdateForm(request.POST, instance=usuario)
        if form.is_valid():
            try:
                usuario = form.save()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Usuario "{usuario.username}" actualizado exitosamente.',
                        'redirect': False
                    })
                messages.success(request, f'Usuario "{usuario.username}" actualizado exitosamente.')
                return redirect('usuarios:usuario_list')
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'Error al actualizar usuario: {str(e)}'
                    }, status=400)
                messages.error(request, f'Error al actualizar usuario: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                for field, field_errors in form.errors.items():
                    errors[field] = field_errors
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'error': 'Por favor corrige los errores en el formulario.'
                }, status=400)
            
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UsuarioUpdateForm(instance=usuario)
        # Filtrar sucursales por la empresa del usuario
        if hasattr(usuario, 'perfil') and usuario.perfil.empresa:
            form.fields['sucursal'].queryset = usuario.perfil.empresa.sucursales.filter(estado='activa').order_by('nombre')
    
    context = {
        'form': form,
        'usuario': usuario,
        'titulo': 'Editar Usuario',
        'empresa': empresa,
    }
    
    # Si es AJAX, devolver solo el formulario
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'usuarios/usuario_form_modal.html', context)
    
    return render(request, 'usuarios/usuario_form.html', context)


@login_required
@requiere_permiso('auth.delete_user', mensaje='No tienes permisos para eliminar usuarios. Solo los administradores pueden realizar esta acción.', redirect_url='usuarios:usuario_list')
@require_POST
def usuario_delete(request, user_id):
    """Eliminar usuario"""
    try:
        usuario = get_object_or_404(User, id=user_id)
        
        # Verificar que el usuario pertenece a la misma empresa
        empresa, error = obtener_empresa_usuario(request)
        if error:
            return JsonResponse({'error': error}, status=400)
        
        # No permitir eliminar superusuarios
        if usuario.is_superuser:
            return JsonResponse({'success': False, 'message': 'No se pueden eliminar superusuarios.'})
            
        if usuario.perfil.empresa != empresa:
            return JsonResponse({'success': False, 'message': 'No tienes permisos para eliminar este usuario.'})
        
        # No permitir que el usuario se elimine a sí mismo
        if usuario == request.user:
            return JsonResponse({'success': False, 'message': 'No puedes eliminar tu propio usuario.'})
        
        username = usuario.username
        usuario.delete()
        
        return JsonResponse({'success': True, 'message': f'Usuario "{username}" eliminado correctamente.'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


# ========== GESTIÓN DE GRUPOS/ROLES ==========

@login_required
@requiere_empresa
@requiere_permiso('auth.view_group', mensaje='No tienes permisos para ver la lista de grupos. Contacta al administrador.', redirect_url='dashboard')
def grupo_list(request):
    """Lista de grupos/roles"""
    # Filtros
    search = request.GET.get('search', '')
    
    # Query base
    grupos = Group.objects.all()
    
    # Aplicar filtros
    if search:
        grupos = grupos.filter(name__icontains=search)
    
    # Ordenamiento
    grupos = grupos.order_by('name')
    
    # Paginación
    paginator = Paginator(grupos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    stats = {
        'total_grupos': Group.objects.count(),
        'usuarios_con_grupo': User.objects.filter(groups__isnull=False).distinct().count(),
        'usuarios_sin_grupo': User.objects.filter(groups__isnull=True).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'titulo': 'Gestión de Grupos/Roles',
    }
    
    return render(request, 'usuarios/grupo_list.html', context)


def traducir_permiso(permission):
    """Traduce el nombre de un permiso al español"""
    
    # Diccionario de traducciones para acciones
    acciones = {
        'add': 'Agregar',
        'change': 'Editar',
        'delete': 'Eliminar',
        'view': 'Ver',
    }
    
    # Diccionario de traducciones para modelos
    modelos = {
        # Artículos
        'articulo': 'Artículos',
        'categoriaarticulo': 'Categorías de Artículos',
        'impuestoespecifico': 'Impuestos Específicos',
        'stockarticulo': 'Stock de Artículos',
        'unidadmedida': 'Unidades de Medida',
        
        # Bodegas
        'bodega': 'Bodegas',
        
        # Clientes
        'cliente': 'Clientes',
        'contactocliente': 'Contactos de Clientes',
        
        # Compras
        'compra': 'Compras',
        'compradetalle': 'Detalles de Compras',
        'ordencompra': 'Órdenes de Compra',
        
        # Documentos
        'documento': 'Documentos',
        'tipodocumento': 'Tipos de Documentos',
        
        # Empresas
        'empresa': 'Empresas',
        'sucursal': 'Sucursales',
        
        # Inventario
        'inventario': 'Inventario',
        'ajusteinventario': 'Ajustes de Inventario',
        'movimientoinventario': 'Movimientos de Inventario',
        'cargainicial': 'Carga Inicial de Inventario',
        
        # Proveedores
        'proveedor': 'Proveedores',
        'contactoproveedor': 'Contactos de Proveedores',
        
        # Reportes
        'reporte': 'Reportes',
        
        # Tesorería
        'cuentacorriente': 'Cuentas Corrientes',
        'pago': 'Pagos',
        'cobro': 'Cobros',
        
        # Usuarios
        'perfilusuario': 'Perfiles de Usuario',
        
        # Ventas
        'venta': 'Ventas',
        'ventadetalle': 'Detalles de Ventas',
        'vendedor': 'Vendedores',
        'formapago': 'Formas de Pago',
        'estaciontrabajo': 'Estaciones de Trabajo',
        'cotizacion': 'Cotizaciones',
        
        # Caja
        'aperturacaja': 'Aperturas de Caja',
        'movimientocaja': 'Movimientos de Caja',
        'ventaprocesada': 'Ventas Procesadas',
        
        # Facturación Electrónica
        'archivocaf': 'Archivos CAF',
        'documentotributarioelectronico': 'Documentos Tributarios Electrónicos',
        
        # Pedidos
        'pedido': 'Pedidos',
        'pedidodetalle': 'Detalles de Pedidos',
        
        # Producción
        'ordenproduccion': 'Órdenes de Producción',
        'receta': 'Recetas',
        'materialreceta': 'Materiales de Receta',
        
        # Informes
        'informe': 'Informes',
    }
    
    # Extraer la acción del codename (add_, change_, delete_, view_)
    codename = permission.codename
    accion = None
    modelo = None
    
    for key in acciones.keys():
        if codename.startswith(key + '_'):
            accion = acciones[key]
            modelo = codename[len(key) + 1:]
            break
    
    # Obtener el nombre del modelo traducido
    modelo_traducido = modelos.get(modelo, permission.content_type.model.replace('_', ' ').title())
    
    if accion:
        return f"{accion} {modelo_traducido}"
    else:
        return permission.name


@login_required
@requiere_empresa
@requiere_permiso('auth.add_group', mensaje='No tienes permisos para crear grupos. Solo los administradores pueden realizar esta acción.', redirect_url='usuarios:grupo_list')
def grupo_create(request):
    """Crear nuevo grupo"""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    
    if request.method == 'POST':
        form = GrupoForm(request.POST)
        
        # Procesar permisos
        permisos_seleccionados = request.POST.getlist('permissions')
        
        if form.is_valid():
            try:
                grupo = form.save()
                
                # Asignar permisos al grupo
                for perm_id in permisos_seleccionados:
                    try:
                        permission = Permission.objects.get(id=perm_id)
                        grupo.permissions.add(permission)
                    except Permission.DoesNotExist:
                        pass
                
                messages.success(request, f'Grupo "{grupo.name}" creado exitosamente.')
                return redirect('usuarios:grupo_list')
            except Exception as e:
                messages.error(request, f'Error al crear grupo: {str(e)}')
    else:
        form = GrupoForm()
    
    # Obtener todos los permisos organizados por aplicación
    permisos_por_app = {}
    
    # Nombres de aplicaciones en español
    nombres_apps = {
        'articulos': 'Artículos',
        'bodegas': 'Bodegas',
        'caja': 'Caja',
        'clientes': 'Clientes',
        'compras': 'Compras',
        'documentos': 'Documentos',
        'empresas': 'Empresas',
        'facturacion_electronica': 'Facturación Electrónica',
        'informes': 'Informes',
        'inventario': 'Inventario',
        'pedidos': 'Pedidos',
        'produccion': 'Producción',
        'proveedores': 'Proveedores',
        'reportes': 'Reportes',
        'tesoreria': 'Tesorería',
        'utilidades': 'Utilidades',
        'usuarios': 'Usuarios',
        'ventas': 'Ventas'
    }
    
    # Obtener content types de las apps del sistema
    app_labels = [
        'articulos', 'bodegas', 'caja', 'clientes', 'compras', 'documentos',
        'empresas', 'facturacion_electronica', 'informes', 'inventario',
        'pedidos', 'produccion', 'proveedores', 'reportes', 
        'tesoreria', 'utilidades', 'usuarios', 'ventas'
    ]
    
    for app_label in app_labels:
        content_types = ContentType.objects.filter(app_label=app_label)
        permisos = Permission.objects.filter(content_type__in=content_types).order_by('content_type__model', 'codename')
        
        if permisos.exists():
            # Traducir cada permiso
            permisos_traducidos = []
            for permiso in permisos:
                permiso.nombre_traducido = traducir_permiso(permiso)
                permisos_traducidos.append(permiso)
            
            permisos_por_app[nombres_apps.get(app_label, app_label.title())] = permisos_traducidos
    
    context = {
        'form': form,
        'titulo': 'Crear Nuevo Grupo/Rol',
        'permisos_por_app': permisos_por_app,
        'permisos_actuales': [],
    }
    
    return render(request, 'usuarios/grupo_form.html', context)


@login_required
@requiere_empresa
@requiere_permiso('auth.change_group', mensaje='No tienes permisos para editar grupos. Solo los administradores pueden realizar esta acción.', redirect_url='usuarios:grupo_list')
def grupo_edit(request, grupo_id):
    """Editar grupo existente"""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    
    grupo = get_object_or_404(Group, id=grupo_id)
    
    if request.method == 'POST':
        form = GrupoForm(request.POST, instance=grupo)
        
        # Procesar permisos
        permisos_seleccionados = request.POST.getlist('permissions')
        
        if form.is_valid():
            try:
                grupo = form.save()
                
                # Actualizar permisos del grupo
                grupo.permissions.clear()
                for perm_id in permisos_seleccionados:
                    try:
                        permission = Permission.objects.get(id=perm_id)
                        grupo.permissions.add(permission)
                    except Permission.DoesNotExist:
                        pass
                
                messages.success(request, f'Grupo "{grupo.name}" actualizado exitosamente.')
                return redirect('usuarios:grupo_list')
            except Exception as e:
                messages.error(request, f'Error al actualizar grupo: {str(e)}')
    else:
        form = GrupoForm(instance=grupo)
    
    # Obtener todos los permisos organizados por aplicación
    permisos_por_app = {}
    
    # Nombres de aplicaciones en español
    nombres_apps = {
        'articulos': 'Artículos',
        'bodegas': 'Bodegas',
        'caja': 'Caja',
        'clientes': 'Clientes',
        'compras': 'Compras',
        'documentos': 'Documentos',
        'empresas': 'Empresas',
        'facturacion_electronica': 'Facturación Electrónica',
        'informes': 'Informes',
        'inventario': 'Inventario',
        'pedidos': 'Pedidos',
        'produccion': 'Producción',
        'proveedores': 'Proveedores',
        'reportes': 'Reportes',
        'tesoreria': 'Tesorería',
        'utilidades': 'Utilidades',
        'usuarios': 'Usuarios',
        'ventas': 'Ventas'
    }
    
    # Obtener content types de las apps del sistema
    app_labels = [
        'articulos', 'bodegas', 'caja', 'clientes', 'compras', 'documentos',
        'empresas', 'facturacion_electronica', 'informes', 'inventario',
        'pedidos', 'produccion', 'proveedores', 'reportes', 
        'tesoreria', 'utilidades', 'usuarios', 'ventas'
    ]
    
    for app_label in app_labels:
        content_types = ContentType.objects.filter(app_label=app_label)
        permisos = Permission.objects.filter(content_type__in=content_types).order_by('content_type__model', 'codename')
        
        if permisos.exists():
            # Traducir cada permiso
            permisos_traducidos = []
            for permiso in permisos:
                permiso.nombre_traducido = traducir_permiso(permiso)
                permisos_traducidos.append(permiso)
            
            permisos_por_app[nombres_apps.get(app_label, app_label.title())] = permisos_traducidos
    
    # Obtener permisos actuales del grupo
    permisos_actuales = grupo.permissions.values_list('id', flat=True)
    
    context = {
        'form': form,
        'grupo': grupo,
        'titulo': 'Editar Grupo/Rol',
        'permisos_por_app': permisos_por_app,
        'permisos_actuales': list(permisos_actuales),
    }
    
    return render(request, 'usuarios/grupo_form.html', context)


@login_required
@requiere_permiso('auth.delete_group', mensaje='No tienes permisos para eliminar grupos. Solo los administradores pueden realizar esta acción.', redirect_url='usuarios:grupo_list')
@require_POST
def grupo_delete(request, grupo_id):
    """Eliminar grupo"""
    try:
        grupo = get_object_or_404(Group, id=grupo_id)
        
        # Verificar si hay usuarios asignados al grupo
        usuarios_count = grupo.user_set.count()
        if usuarios_count > 0:
            return JsonResponse({
                'success': False, 
                'message': f'No se puede eliminar el grupo porque tiene {usuarios_count} usuario(s) asignado(s). Reasigna los usuarios primero.'
            })
        
        name = grupo.name
        grupo.delete()
        
        return JsonResponse({'success': True, 'message': f'Grupo "{name}" eliminado correctamente.'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
