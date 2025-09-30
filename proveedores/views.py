from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.forms import inlineformset_factory
from .models import Proveedor, ContactoProveedor
from .forms import ProveedorForm, ContactoProveedorForm, ContactoProveedorInlineFormSet
from empresas.models import Empresa
from empresas.decorators import requiere_empresa


@login_required
def proveedor_list(request):
    """Lista de proveedores con estadísticas"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        # Para superusuarios, usar la primera empresa disponible
        empresa = Empresa.objects.first()
        if not empresa:
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('dashboard')
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
    }
    
    return render(request, 'proveedores/proveedor_list.html', context)


@login_required
def proveedor_detail(request, pk):
    """Detalle de proveedor"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa = Empresa.objects.first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('proveedores:proveedor_list')
    
    proveedor = get_object_or_404(Proveedor, pk=pk, empresa=empresa)
    
    # Obtener contactos
    contactos = proveedor.contactos.all().order_by('-es_contacto_principal', 'tipo_contacto', 'nombre')
    
    # Obtener categorías
    categorias = proveedor.categorias.all().order_by('-es_categoria_principal')
    
    # Obtener evaluaciones (últimas 5)
    evaluaciones = proveedor.evaluaciones.all()[:5]
    
    context = {
        'proveedor': proveedor,
        'contactos': contactos,
        'categorias': categorias,
        'evaluaciones': evaluaciones,
    }
    
    return render(request, 'proveedores/proveedor_detail.html', context)


@login_required
def proveedor_create(request):
    """Crear nuevo proveedor"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        # Para superusuarios, usar la primera empresa disponible
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
    
    ContactoFormSet = inlineformset_factory(
        Proveedor, ContactoProveedor, 
        form=ContactoProveedorForm,
        formset=ContactoProveedorInlineFormSet,
        extra=1,
        can_delete=True,
        fields=['nombre', 'cargo', 'tipo_contacto', 'telefono', 'celular', 'email', 'observaciones', 'es_contacto_principal']
    )
    
    if request.method == 'POST':
        form = ProveedorForm(request.POST, empresa=empresa)
        formset = ContactoFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            proveedor = form.save(commit=False)
            proveedor.empresa = empresa
            proveedor.creado_por = request.user
            proveedor.save()
            
            # Guardar contactos
            formset.instance = proveedor
            formset.save()
            
            messages.success(request, f'Proveedor "{proveedor.nombre}" creado exitosamente.')
            return redirect('proveedores:proveedor_detail', pk=proveedor.pk)
    else:
        form = ProveedorForm(empresa=empresa)
        formset = ContactoFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'title': 'Crear Proveedor',
        'submit_text': 'Crear Proveedor',
    }
    
    return render(request, 'proveedores/proveedor_form.html', context)


@login_required
def proveedor_update(request, pk):
    """Editar proveedor"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa = Empresa.objects.first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('proveedores:proveedor_list')
    
    proveedor = get_object_or_404(Proveedor, pk=pk, empresa=empresa)
    
    ContactoFormSet = inlineformset_factory(
        Proveedor, ContactoProveedor, 
        form=ContactoProveedorForm,
        formset=ContactoProveedorInlineFormSet,
        extra=1,
        can_delete=True,
        fields=['nombre', 'cargo', 'tipo_contacto', 'telefono', 'celular', 'email', 'observaciones', 'es_contacto_principal']
    )
    
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor, empresa=empresa)
        formset = ContactoFormSet(request.POST, instance=proveedor)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            messages.success(request, f'Proveedor "{proveedor.nombre}" actualizado exitosamente.')
            return redirect('proveedores:proveedor_detail', pk=proveedor.pk)
    else:
        form = ProveedorForm(instance=proveedor, empresa=empresa)
        formset = ContactoFormSet(instance=proveedor)
    
    # Obtener contactos para mostrar en la lista
    contactos = proveedor.contactos.all().order_by('-es_contacto_principal', 'tipo_contacto', 'nombre')
    
    context = {
        'form': form,
        'formset': formset,
        'contactos': contactos,
        'proveedor': proveedor,
        'title': 'Editar Proveedor',
        'submit_text': 'Actualizar Proveedor',
    }
    
    return render(request, 'proveedores/proveedor_form.html', context)


@login_required
def proveedor_delete(request, pk):
    """Eliminar proveedor"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa = Empresa.objects.first()
    else:
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