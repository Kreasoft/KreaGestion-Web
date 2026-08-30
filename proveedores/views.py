from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.forms import inlineformset_factory
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from .models import Proveedor, ContactoProveedor
from .forms import ProveedorForm, ContactoProveedorForm, ContactoProveedorInlineFormSet
from empresas.models import Empresa
from core.decorators import requiere_empresa


@login_required
@permission_required('proveedores.view_proveedor', raise_exception=True)
def proveedor_list(request):
    """Lista de proveedores con estadísticas"""
    # Obtener la empresa del usuario
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
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('dashboard')
            
        # Guardar empresa en sesión
        request.session['empresa_activa'] = empresa.id
    else:
        # Para usuarios normales, usar su empresa asociada
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Filtros
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    tipo_proveedor = request.GET.get('tipo_proveedor', '')
    
    # Query base
    proveedores = Proveedor.objects.filter(empresa=empresa)
    
    # Aplicar filtros
    if search:
        proveedores = proveedores.filter(
            Q(nombre__icontains=search) |
            Q(rut__icontains=search) |
            Q(email__icontains=search) |
            Q(razon_social__icontains=search)
        )
    
    if estado:
        proveedores = proveedores.filter(estado=estado)
    
    if tipo_proveedor:
        proveedores = proveedores.filter(tipo_proveedor=tipo_proveedor)
    
    # Ordenamiento
    proveedores = proveedores.order_by('nombre')
    
    # Paginación
    paginator = Paginator(proveedores, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    total_proveedores = Proveedor.objects.filter(empresa=empresa).count()
    proveedores_activos = Proveedor.objects.filter(empresa=empresa, estado='activo').count()
    proveedores_productos = Proveedor.objects.filter(empresa=empresa, tipo_proveedor='productos').count()
    proveedores_servicios = Proveedor.objects.filter(empresa=empresa, tipo_proveedor='servicios').count()
    proveedores_ambos = Proveedor.objects.filter(empresa=empresa, tipo_proveedor='ambos').count()
    
    # Calcular calificación promedio
    calificacion_promedio = Proveedor.objects.filter(empresa=empresa).aggregate(
        promedio=Sum('calificacion') / Count('calificacion')
    )['promedio'] or 0
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'estado': estado,
        'tipo_proveedor': tipo_proveedor,
        'total_proveedores': total_proveedores,
        'proveedores_activos': proveedores_activos,
        'proveedores_productos': proveedores_productos,
        'proveedores_servicios': proveedores_servicios,
        'proveedores_ambos': proveedores_ambos,
        'calificacion_promedio': round(calificacion_promedio, 1),
        'estados': Proveedor.ESTADO_CHOICES,
        'tipos_proveedor': Proveedor.TIPO_PROVEEDOR_CHOICES,
        'abrir_detalle_id': request.GET.get('ver', '').strip() if str(request.GET.get('ver', '')).isdigit() else '',
        'abrir_editar_id': request.GET.get('editar', '').strip() if str(request.GET.get('editar', '')).isdigit() else '',
        'abrir_nuevo': request.GET.get('nuevo') == '1',
    }
    
    return render(request, 'proveedores/proveedor_list.html', context)


def _empresa_usuario(request):
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                return Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                pass
        return Empresa.objects.filter(nombre__icontains='Kreasoft').first() or Empresa.objects.first()
    try:
        return request.user.perfil.empresa
    except Exception:
        return None


def _es_modal(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.GET.get('modal') == '1'
        or request.POST.get('modal') == '1'
    )


def _formset_contactos():
    return inlineformset_factory(
        Proveedor, ContactoProveedor,
        form=ContactoProveedorForm,
        formset=ContactoProveedorInlineFormSet,
        extra=1,
        can_delete=True,
        fields=['nombre', 'cargo', 'tipo_contacto', 'telefono', 'celular', 'email', 'observaciones', 'es_contacto_principal'],
    )


def _html_form_proveedor(request, form, formset, proveedor=None):
    action_url = (
        reverse('proveedores:proveedor_update', args=[proveedor.pk])
        if proveedor else reverse('proveedores:proveedor_create')
    )
    return render_to_string(
        'proveedores/_proveedor_form_modal_inner.html',
        {'form': form, 'formset': formset, 'proveedor': proveedor, 'action_url': action_url},
        request=request,
    )


@login_required
def proveedor_detail(request, pk):
    """La ficha se muestra como modal sobre la lista."""
    return redirect(f"{reverse('proveedores:proveedor_list')}?ver={pk}")


@login_required
@permission_required('proveedores.view_proveedor', raise_exception=True)
def ajax_proveedor_detail(request, pk):
    empresa = _empresa_usuario(request)
    if not empresa:
        return JsonResponse({'success': False, 'message': 'No hay empresa activa.'}, status=400)
    proveedor = get_object_or_404(Proveedor, pk=pk, empresa=empresa)
    contactos = [
        {
            'nombre': c.nombre,
            'cargo': c.cargo or '',
            'tipo': c.get_tipo_contacto_display(),
            'telefono': c.telefono or '',
            'celular': c.celular or '',
            'email': c.email or '',
            'principal': c.es_contacto_principal,
        }
        for c in proveedor.contactos.all().order_by('-es_contacto_principal', 'tipo_contacto', 'nombre')
    ]
    categorias = [
        cat.descripcion.strip() or ('Principal' if cat.es_categoria_principal else 'Categoría')
        for cat in proveedor.categorias.all().order_by('-es_categoria_principal')
        if (cat.descripcion or '').strip() or cat.es_categoria_principal
    ]
    return JsonResponse({
        'success': True,
        'proveedor': {
            'id': proveedor.pk,
            'nombre': proveedor.nombre or '',
            'razon_social': proveedor.razon_social or '',
            'rut': proveedor.get_rut_formateado(),
            'giro': proveedor.giro or '',
            'tipo': proveedor.get_tipo_proveedor_display(),
            'estado': proveedor.get_estado_display(),
            'estado_codigo': proveedor.estado,
            'direccion': proveedor.direccion or '',
            'comuna': proveedor.comuna or '',
            'ciudad': proveedor.ciudad or '',
            'region': proveedor.region or '',
            'fecha_alta': proveedor.fecha_alta.strftime('%d-%m-%Y') if proveedor.fecha_alta else '',
            'email': proveedor.email or '',
            'telefono': proveedor.telefono or '',
            'sitio_web': proveedor.sitio_web or '',
            'plazo_entrega': proveedor.plazo_entrega or '0',
            'condiciones_pago': proveedor.condiciones_pago or '',
            'descuento': str(proveedor.descuento_porcentaje or 0),
            'calificacion': proveedor.calificacion or 0,
            'estrellas': proveedor.get_calificacion_estrellas(),
            'observaciones_calidad': proveedor.observaciones_calidad or '',
            'observaciones': proveedor.observaciones or '',
            'edit_url': reverse('proveedores:proveedor_update', args=[proveedor.pk]),
        },
        'contactos': contactos,
        'categorias': categorias,
    })


@login_required
@permission_required('proveedores.add_proveedor', raise_exception=True)
def proveedor_create(request):
    """Crear nuevo proveedor"""
    # Obtener la empresa del usuario
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
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('proveedores:proveedor_list')
    else:
        # Para usuarios normales, usar su empresa asociada
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('proveedores:proveedor_list')
    
    ContactoFormSet = _formset_contactos()

    if request.method == 'POST':
        form = ProveedorForm(request.POST, empresa=empresa)
        formset = ContactoFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            proveedor = form.save(commit=False)
            proveedor.empresa = empresa
            proveedor.creado_por = request.user
            proveedor.save()
            formset.instance = proveedor
            formset.save()
            messages.success(request, f'Proveedor "{proveedor.nombre}" creado exitosamente.')
            if _es_modal(request):
                return JsonResponse({'success': True})
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('proveedores:proveedor_list')
        if _es_modal(request):
            return HttpResponse(_html_form_proveedor(request, form, formset), status=400)
    else:
        if not _es_modal(request):
            return redirect(f"{reverse('proveedores:proveedor_list')}?nuevo=1")
        form = ProveedorForm(empresa=empresa)
        formset = ContactoFormSet()

    return HttpResponse(_html_form_proveedor(request, form, formset))


@login_required
@permission_required('proveedores.change_proveedor', raise_exception=True)
def proveedor_update(request, pk):
    """Editar proveedor"""
    # Obtener la empresa del usuario
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
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('proveedores:proveedor_list')

        # Guardar empresa en sesión
        request.session['empresa_activa'] = empresa.id
    else:
        # Para usuarios normales, usar su empresa asociada
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('proveedores:proveedor_list')
    
    proveedor = get_object_or_404(Proveedor, pk=pk, empresa=empresa)
    ContactoFormSet = _formset_contactos()
    
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor, empresa=empresa)
        formset = ContactoFormSet(request.POST, instance=proveedor)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Proveedor "{proveedor.nombre}" actualizado exitosamente.')
            if _es_modal(request):
                return JsonResponse({'success': True})
            return redirect('proveedores:proveedor_list')
        if _es_modal(request):
            return HttpResponse(_html_form_proveedor(request, form, formset, proveedor), status=400)
    else:
        if not _es_modal(request):
            return redirect(f"{reverse('proveedores:proveedor_list')}?editar={pk}")
        form = ProveedorForm(instance=proveedor, empresa=empresa)
        formset = ContactoFormSet(instance=proveedor)
    
    return HttpResponse(_html_form_proveedor(request, form, formset, proveedor))


@login_required
@permission_required('proveedores.delete_proveedor', raise_exception=True)
def proveedor_delete(request, pk):
    """Eliminar proveedor"""
    # Obtener la empresa del usuario
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
    else:
        # Para usuarios normales, usar su empresa asociada
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('proveedores:proveedor_list')
    
    proveedor = get_object_or_404(Proveedor, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        nombre = proveedor.nombre
        proveedor.delete()
        messages.success(request, f'Proveedor "{nombre}" eliminado exitosamente.')
        return redirect('proveedores:proveedor_list')
    
    context = {
        'proveedor': proveedor,
    }
    
    return render(request, 'proveedores/proveedor_confirm_delete.html', context)


@login_required
@permission_required('proveedores.add_contactoproveedor', raise_exception=True)
def contacto_create(request, proveedor_id):
    """Crear contacto en modal"""
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    
    if request.method == 'POST':
        form = ContactoProveedorForm(request.POST)
        if form.is_valid():
            contacto = form.save(commit=False)
            contacto.proveedor = proveedor
            contacto.save()
            messages.success(request, 'Contacto agregado exitosamente.')
            return redirect('proveedores:proveedor_detail', pk=proveedor.id)
    else:
        form = ContactoProveedorForm()
    
    context = {
        'form': form,
        'proveedor': proveedor,
    }
    
    return render(request, 'proveedores/contacto_form_modal.html', context)


@login_required
@permission_required('proveedores.change_contactoproveedor', raise_exception=True)
def contacto_update(request, proveedor_id, contacto_id):
    """Editar contacto en modal"""
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    contacto = get_object_or_404(ContactoProveedor, id=contacto_id, proveedor=proveedor)
    
    if request.method == 'POST':
        form = ContactoProveedorForm(request.POST, instance=contacto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contacto actualizado exitosamente.')
            return redirect('proveedores:proveedor_detail', pk=proveedor.id)
    else:
        form = ContactoProveedorForm(instance=contacto)
    
    context = {
        'form': form,
        'proveedor': proveedor,
        'contacto': contacto,
    }
    
    return render(request, 'proveedores/contacto_form_modal.html', context)


@login_required
@permission_required('proveedores.delete_contactoproveedor', raise_exception=True)
def contacto_delete(request, proveedor_id, contacto_id):
    """Eliminar contacto"""
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    contacto = get_object_or_404(ContactoProveedor, id=contacto_id, proveedor=proveedor)
    
    if request.method == 'POST':
        nombre = contacto.nombre
        contacto.delete()
        messages.success(request, f'Contacto "{nombre}" eliminado exitosamente.')
        return redirect('proveedores:proveedor_detail', pk=proveedor.id)
    
    context = {
        'proveedor': proveedor,
        'contacto': contacto,
    }
    
    return render(request, 'proveedores/contacto_confirm_delete.html', context)